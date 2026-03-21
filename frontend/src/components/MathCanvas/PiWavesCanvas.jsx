import { useEffect, useRef } from 'react'

export default function PiWavesCanvas() {
  const canvasRef = useRef(null)
  const animRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    let w, h
    const resize = () => {
      w = canvas.width = window.innerWidth
      h = canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    let t = 0

    const draw = (dt) => {
      t += dt
      ctx.clearRect(0, 0, w, h)

      const angle = t * 1.4 // rotation speed

      // --- Circle on the left ---
      const circR = Math.min(w * 0.15, h * 0.28)
      const circCx = w * 0.25
      const circCy = h * 0.5

      // Draw circle
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.arc(circCx, circCy, circR, 0, Math.PI * 2)
      ctx.stroke()

      // Axes through center
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)'
      ctx.beginPath()
      ctx.moveTo(circCx - circR - 15, circCy)
      ctx.lineTo(circCx + circR + 15, circCy)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(circCx, circCy - circR - 15)
      ctx.lineTo(circCx, circCy + circR + 15)
      ctx.stroke()

      // Rotating radius
      const px = circCx + Math.cos(angle) * circR
      const py = circCy - Math.sin(angle) * circR

      ctx.strokeStyle = 'rgba(255, 215, 0, 0.6)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(circCx, circCy)
      ctx.lineTo(px, py)
      ctx.stroke()

      // Arc showing angle
      ctx.strokeStyle = 'rgba(255, 215, 0, 0.3)'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.arc(circCx, circCy, circR * 0.25, 0, -angle, angle > 0)
      ctx.stroke()

      // Angle label
      const angDeg = ((angle * 180 / Math.PI) % 360 + 360) % 360
      ctx.fillStyle = 'rgba(255, 215, 0, 0.7)'
      ctx.font = '13px monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`${angDeg.toFixed(0)}\u00b0`, circCx + circR * 0.3, circCy - 8)

      // Point on circle
      ctx.shadowColor = 'rgba(0, 200, 255, 0.6)'
      ctx.shadowBlur = 12
      ctx.fillStyle = '#00c8ff'
      ctx.beginPath()
      ctx.arc(px, py, 7, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0

      // Horizontal dashed line from point to y-axis projection
      ctx.setLineDash([3, 4])
      ctx.strokeStyle = 'rgba(0, 200, 255, 0.3)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(px, py)
      ctx.lineTo(circCx - circR - 10, py)
      ctx.stroke()

      // sin value label on left
      const sinVal = Math.sin(angle)
      ctx.fillStyle = 'rgba(0, 200, 255, 0.7)'
      ctx.font = '12px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(`sin=${sinVal.toFixed(2)}`, circCx - circR - 14, py + 4)

      ctx.setLineDash([])

      // --- Connection line from circle point to wave start ---
      const waveLeft = w * 0.44
      const waveRight = w * 0.94
      const waveCy = h * 0.5
      const waveAmp = circR

      // Dashed connection
      ctx.setLineDash([4, 6])
      ctx.strokeStyle = 'rgba(0, 200, 255, 0.2)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(px, py)
      ctx.lineTo(waveLeft, waveCy - sinVal * waveAmp)
      ctx.stroke()
      ctx.setLineDash([])

      // --- Sine wave ---
      const waveW = waveRight - waveLeft

      // Center line
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(waveLeft, waveCy)
      ctx.lineTo(waveRight, waveCy)
      ctx.stroke()

      // Wave trail - shows history
      const trailLen = 4 * Math.PI // 2 full cycles
      ctx.beginPath()
      const waveSteps = 400
      for (let i = 0; i <= waveSteps; i++) {
        const frac = i / waveSteps
        const wAngle = angle - frac * trailLen
        const x = waveLeft + frac * waveW
        const y = waveCy - Math.sin(wAngle) * waveAmp
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }

      // Gradient stroke via fill
      ctx.strokeStyle = 'rgba(0, 200, 255, 0.7)'
      ctx.lineWidth = 2.5
      ctx.stroke()

      // Fade effect — draw diminishing opacity segments
      for (let seg = 1; seg <= 3; seg++) {
        ctx.beginPath()
        const startFrac = seg * 0.25
        const endFrac = (seg + 1) * 0.25
        const startI = Math.floor(startFrac * waveSteps)
        const endI = Math.min(Math.floor(endFrac * waveSteps), waveSteps)
        for (let i = startI; i <= endI; i++) {
          const frac = i / waveSteps
          const wAngle = angle - frac * trailLen
          const x = waveLeft + frac * waveW
          const y = waveCy - Math.sin(wAngle) * waveAmp
          if (i === startI) ctx.moveTo(x, y)
          else ctx.lineTo(x, y)
        }
        ctx.strokeStyle = `rgba(0, 200, 255, ${0.5 - seg * 0.12})`
        ctx.lineWidth = 2.5 - seg * 0.4
        ctx.stroke()
      }

      // Current point on wave (leftmost)
      ctx.shadowColor = 'rgba(0, 200, 255, 0.6)'
      ctx.shadowBlur = 12
      ctx.fillStyle = '#00c8ff'
      ctx.beginPath()
      ctx.arc(waveLeft, waveCy - sinVal * waveAmp, 6, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0

      // Wavelength marker
      const wavelenPx = (2 * Math.PI / trailLen) * waveW
      ctx.strokeStyle = 'rgba(255, 215, 0, 0.3)'
      ctx.lineWidth = 1
      const markerY = waveCy + waveAmp + 30
      ctx.beginPath()
      ctx.moveTo(waveLeft, markerY)
      ctx.lineTo(waveLeft + wavelenPx, markerY)
      ctx.stroke()
      // End caps
      for (const x of [waveLeft, waveLeft + wavelenPx]) {
        ctx.beginPath()
        ctx.moveTo(x, markerY - 4)
        ctx.lineTo(x, markerY + 4)
        ctx.stroke()
      }
      ctx.fillStyle = 'rgba(255, 215, 0, 0.5)'
      ctx.font = '12px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('2\u03c0 = one cycle', waveLeft + wavelenPx / 2, markerY + 16)

      // +1 / -1 labels
      ctx.fillStyle = 'rgba(255, 255, 255, 0.3)'
      ctx.font = '11px monospace'
      ctx.textAlign = 'right'
      ctx.fillText('+1', waveLeft - 8, waveCy - waveAmp + 4)
      ctx.fillText('-1', waveLeft - 8, waveCy + waveAmp + 4)
      ctx.fillText(' 0', waveLeft - 8, waveCy + 4)

      // Title
      ctx.fillStyle = '#ffd700'
      ctx.font = 'bold 22px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('\u03c0  Circle \u2192 Wave', w * 0.5, h * 0.06)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.font = '13px monospace'
      ctx.fillText('Rotation on circle generates sine wave in real-time', w * 0.5, h * 0.06 + 22)
    }

    let lastTime = performance.now()
    const loop = (now) => {
      const dt = Math.min((now - lastTime) / 1000, 0.05)
      lastTime = now
      draw(dt)
      animRef.current = requestAnimationFrame(loop)
    }
    animRef.current = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(animRef.current)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
}
