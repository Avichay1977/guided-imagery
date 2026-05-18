import { useRef, useState, useCallback } from 'react'

const BUFFER_SIZE = 300        // 10 seconds at 30fps
const SAMPLE_RATE = 30         // fps
const DFT_INTERVAL = 90        // recalculate every 3 seconds
const MIN_BPM = 45
const MAX_BPM = 180
const BASELINE_MIN_CONFIDENCE = 0.4
const BASELINE_MIN_SAMPLES = 150

/**
 * Compute DFT magnitude² for a specific bin k over N samples.
 * magnitude² = (Σ x[n]·cos(2πkn/N))² + (Σ x[n]·sin(2πkn/N))²
 */
function dftBinMagnitudeSq(signal, k) {
  const N = signal.length
  let cosSum = 0
  let sinSum = 0
  const twopiKoverN = (2 * Math.PI * k) / N
  for (let n = 0; n < N; n++) {
    cosSum += signal[n] * Math.cos(twopiKoverN * n)
    sinSum += signal[n] * Math.sin(twopiKoverN * n)
  }
  return cosSum * cosSum + sinSum * sinSum
}

/**
 * Estimate heart rate from a green-channel signal buffer.
 * Returns { bpm, confidence } or null if insufficient data.
 */
function estimateHR(signal) {
  const N = signal.length
  if (N < 2) return null

  // Convert BPM bounds to DFT bin indices
  // bin k corresponds to frequency k * SAMPLE_RATE / N (Hz)
  // BPM = freq * 60 → bin = BPM / 60 * N / SAMPLE_RATE
  const kMin = Math.ceil((MIN_BPM / 60) * N / SAMPLE_RATE)
  const kMax = Math.floor((MAX_BPM / 60) * N / SAMPLE_RATE)

  if (kMin >= kMax) return null

  // Compute magnitude² for each bin in the HR band
  const magnitudes = []
  for (let k = kMin; k <= kMax; k++) {
    magnitudes.push({ k, mag2: dftBinMagnitudeSq(signal, k) })
  }

  // Find peak bin
  let peak = magnitudes[0]
  for (const entry of magnitudes) {
    if (entry.mag2 > peak.mag2) peak = entry
  }

  // Compute total band power
  const totalPower = magnitudes.reduce((sum, e) => sum + e.mag2, 0)
  if (totalPower === 0) return null

  // Confidence: ratio of peak to total, scaled by 2.5, clamped to [0,1]
  const confidence = Math.min(1, (peak.mag2 / totalPower) * 2.5)

  // Dominant frequency → BPM
  const dominantFreqHz = (peak.k * SAMPLE_RATE) / N
  const bpm = Math.round(dominantFreqHz * 60)

  return { bpm, confidence }
}

/**
 * Extract mean green channel value from the center 50% ROI of a video frame.
 * Draws the current video frame onto canvas and reads pixel data.
 */
function extractGreenMean(video, canvas) {
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  const vw = video.videoWidth || canvas.width
  const vh = video.videoHeight || canvas.height

  // Draw video frame
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height)

  // Center 50% ROI
  const roiX = Math.floor(canvas.width * 0.25)
  const roiY = Math.floor(canvas.height * 0.25)
  const roiW = Math.floor(canvas.width * 0.5)
  const roiH = Math.floor(canvas.height * 0.5)

  const imageData = ctx.getImageData(roiX, roiY, roiW, roiH)
  const data = imageData.data
  let greenSum = 0
  const pixelCount = roiW * roiH

  for (let i = 0; i < data.length; i += 4) {
    greenSum += data[i + 1] // green channel
  }

  return greenSum / pixelCount
}

export function useRPPG() {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const rafRef = useRef(null)
  const signalBufferRef = useRef([])
  const frameCountRef = useRef(0)
  const metricsRef = useRef({ bpm: null, confidence: 0, samples: 0 })

  const [status, setStatus] = useState('idle')
  const [metrics, setMetrics] = useState({ bpm: null, confidence: 0, samples: 0 })
  const [baseline, setBaseline] = useState(null)
  const baselineCapturedRef = useRef(false)

  const processFrame = useCallback(() => {
    const video = videoRef.current
    const canvas = canvasRef.current

    if (!video || !canvas || video.readyState < 2) {
      rafRef.current = requestAnimationFrame(processFrame)
      return
    }

    // Extract green channel mean
    const greenMean = extractGreenMean(video, canvas)
    const buffer = signalBufferRef.current

    // Add to sliding window buffer
    buffer.push(greenMean)
    if (buffer.length > BUFFER_SIZE) {
      buffer.shift()
    }

    frameCountRef.current += 1
    const samples = buffer.length

    // Run DFT every DFT_INTERVAL frames
    let currentBpm = metricsRef.current.bpm
    let currentConfidence = metricsRef.current.confidence

    if (frameCountRef.current % DFT_INTERVAL === 0 && samples >= DFT_INTERVAL) {
      const result = estimateHR(buffer)
      if (result) {
        currentBpm = result.bpm
        currentConfidence = result.confidence
      }
    }

    const newMetrics = { bpm: currentBpm, confidence: currentConfidence, samples }
    metricsRef.current = newMetrics
    setMetrics({ ...newMetrics })

    // Auto-capture baseline: first reading with confidence ≥ 0.4 and ≥ 150 samples
    if (
      !baselineCapturedRef.current &&
      currentBpm !== null &&
      currentConfidence >= BASELINE_MIN_CONFIDENCE &&
      samples >= BASELINE_MIN_SAMPLES
    ) {
      baselineCapturedRef.current = true
      setBaseline(currentBpm)
    }

    // Update status to active once we have enough samples for a reading
    if (samples >= DFT_INTERVAL && frameCountRef.current >= DFT_INTERVAL) {
      setStatus(s => s === 'warming' ? 'active' : s)
    }

    rafRef.current = requestAnimationFrame(processFrame)
  }, [])

  const start = useCallback(async () => {
    if (status !== 'idle' && status !== 'denied' && status !== 'error') return

    setStatus('requesting')

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 320 },
          height: { ideal: 240 },
          frameRate: { ideal: 30 },
        },
        audio: false,
      })

      streamRef.current = stream

      const video = videoRef.current
      if (video) {
        video.srcObject = stream
        await video.play()
      }

      // Reset state
      signalBufferRef.current = []
      frameCountRef.current = 0
      baselineCapturedRef.current = false
      metricsRef.current = { bpm: null, confidence: 0, samples: 0 }
      setMetrics({ bpm: null, confidence: 0, samples: 0 })
      setBaseline(null)
      setStatus('warming')

      // Start processing loop
      rafRef.current = requestAnimationFrame(processFrame)
    } catch (err) {
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setStatus('denied')
      } else {
        setStatus('error')
      }
    }
  }, [status, processFrame])

  const stop = useCallback(() => {
    // Cancel animation frame
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }

    // Stop camera stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }

    // Clear video source
    const video = videoRef.current
    if (video) {
      video.srcObject = null
    }

    signalBufferRef.current = []
    frameCountRef.current = 0
    setStatus('idle')
    setMetrics({ bpm: null, confidence: 0, samples: 0 })
  }, [])

  return {
    videoRef,
    canvasRef,
    status,
    metrics,
    baseline,
    start,
    stop,
  }
}
