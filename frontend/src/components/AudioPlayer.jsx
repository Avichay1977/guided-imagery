import { useState, useRef, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import './AudioPlayer.css'

function AudioPlayer({ audioUrl }) {
  const { t } = useTranslation()
  const audioRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [currentTime, setCurrent] = useState(0)
  const [duration, setDuration] = useState(0)

  const formatTime = (sec) => {
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onLoaded = () => setDuration(audio.duration)
    const onTime = () => setCurrent(audio.currentTime)
    const onEnded = () => setPlaying(false)

    audio.addEventListener('loadedmetadata', onLoaded)
    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('ended', onEnded)

    return () => {
      audio.removeEventListener('loadedmetadata', onLoaded)
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('ended', onEnded)
    }
  }, [audioUrl])

  const togglePlay = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
    } else {
      audio.play()
    }
    setPlaying(!playing)
  }, [playing])

  const handleSeek = (e) => {
    const audio = audioRef.current
    if (!audio || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const isRtl = document.documentElement.dir === 'rtl'
    const x = isRtl
      ? rect.right - e.clientX
      : e.clientX - rect.left
    const ratio = x / rect.width
    audio.currentTime = ratio * duration
  }

  const progress = duration ? (currentTime / duration) * 100 : 0

  return (
    <div className="audio-player card">
      <audio ref={audioRef} src={audioUrl} preload="metadata" />

      <button className="play-btn" onClick={togglePlay}>
        {playing ? (
          <svg viewBox="0 0 24 24" fill="currentColor" width="32" height="32">
            <rect x="6" y="4" width="4" height="16" rx="1" />
            <rect x="14" y="4" width="4" height="16" rx="1" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" fill="currentColor" width="32" height="32">
            <path d="M8 5.14v14.72a1 1 0 001.5.86l11.5-7.36a1 1 0 000-1.72L9.5 4.28A1 1 0 008 5.14z" />
          </svg>
        )}
      </button>

      <div className="player-controls">
        <div className="seek-bar" onClick={handleSeek}>
          <div className="seek-fill" style={{ width: `${progress}%` }} />
          <div className="seek-thumb" style={{ insetInlineStart: `${progress}%` }} />
        </div>

        <div className="time-display">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>
    </div>
  )
}

export default AudioPlayer
