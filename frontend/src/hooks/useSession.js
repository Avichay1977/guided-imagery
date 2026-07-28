import { useState, useCallback, useRef } from 'react'

export function useSession() {
  const [state, setState] = useState('idle') // idle | loading | complete | error
  const [progress, setProgress] = useState({ message: '', percent: 0 })
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [remixing, setRemixing] = useState(false)
  const abortRef = useRef(null)

  const generate = useCallback(async ({ topic, durationMinutes, language, mode, depth, ageGroup, bellsVolume, musicVolume }) => {
    setState('loading')
    setProgress({ message: '', percent: 0 })
    setError(null)
    setResult(null)

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const response = await fetch('/api/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          duration_minutes: durationMinutes,
          language,
          mode: mode || 'imagery',
          depth: depth || 'standard',
          age_group: ageGroup || 'adults',
          bells_volume: bellsVolume ?? 50,
          music_volume: musicVolume ?? 35,
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        let currentEvent = null
        for (const line of lines) {
          if (line.startsWith('event:')) {
            currentEvent = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            try {
              const data = JSON.parse(line.slice(5).trim())

              if (currentEvent === 'complete') {
                setResult(data)
                setState('complete')
              } else if (currentEvent === 'error') {
                setError(data.message)
                setState('error')
              } else if (currentEvent === 'progress') {
                setProgress({ message: data.message, percent: data.percent })
              }
            } catch {
              // skip malformed JSON
            }
            currentEvent = null
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message)
        setState('error')
      }
    }
  }, [])

  // Re-mix a finished session at a new ambience setting. The narration is kept
  // server-side, so this never regenerates the script or the narration —
  // it swaps the audio in place and leaves the rest of the result alone.
  const remix = useCallback(async ({ sessionId, bellsVolume, musicVolume }) => {
    setRemixing(true)
    try {
      const response = await fetch('/api/remix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          bells_volume: bellsVolume,
          music_volume: musicVolume,
        }),
      })
      if (!response.ok) return false

      const data = await response.json()
      setResult((prev) => (prev ? { ...prev, audio_url: data.audio_url } : prev))
      return true
    } catch {
      return false
    } finally {
      setRemixing(false)
    }
  }, [])

  const reset = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
    }
    setState('idle')
    setProgress({ message: '', percent: 0 })
    setResult(null)
    setError(null)
    setRemixing(false)
  }, [])

  return { state, progress, result, error, remixing, generate, remix, reset }
}
