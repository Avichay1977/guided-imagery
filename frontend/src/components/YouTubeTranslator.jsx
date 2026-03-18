import { useState, useRef, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import './YouTubeTranslator.css'

function YouTubeTranslator({ onBack }) {
  const { t } = useTranslation()
  const [url, setUrl] = useState('')
  const [videoId, setVideoId] = useState(null)
  const [segments, setSegments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [currentSub, setCurrentSub] = useState('')
  const [currentOriginal, setCurrentOriginal] = useState('')
  const playerRef = useRef(null)
  const timerRef = useRef(null)

  // Load YouTube IFrame API
  useEffect(() => {
    if (window.YT) return
    const tag = document.createElement('script')
    tag.src = 'https://www.youtube.com/iframe_api'
    document.head.appendChild(tag)
  }, [])

  const initPlayer = useCallback((vidId) => {
    if (playerRef.current) {
      playerRef.current.destroy()
    }

    const waitForYT = () => {
      if (window.YT && window.YT.Player) {
        playerRef.current = new window.YT.Player('yt-player', {
          videoId: vidId,
          height: '100%',
          width: '100%',
          playerVars: {
            autoplay: 1,
            cc_load_policy: 0,
            modestbranding: 1,
            rel: 0,
          },
          events: {
            onStateChange: (e) => {
              if (e.data === window.YT.PlayerState.PLAYING) {
                timerRef.current = setInterval(() => {
                  setCurrentTime(playerRef.current.getCurrentTime())
                }, 200)
              } else {
                clearInterval(timerRef.current)
              }
            },
          },
        })
      } else {
        setTimeout(waitForYT, 200)
      }
    }
    waitForYT()
  }, [])

  // Update current subtitle based on time
  useEffect(() => {
    if (!segments.length) return
    const seg = segments.find(
      (s) => currentTime >= s.start && currentTime < s.start + s.duration
    )
    if (seg) {
      setCurrentSub(seg.text)
      setCurrentOriginal(seg.original || '')
    } else {
      setCurrentSub('')
      setCurrentOriginal('')
    }
  }, [currentTime, segments])

  // Cleanup
  useEffect(() => {
    return () => {
      clearInterval(timerRef.current)
      if (playerRef.current) playerRef.current.destroy()
    }
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!url.trim()) return

    setLoading(true)
    setError(null)
    setSegments([])
    setVideoId(null)

    try {
      // Step 1: Fetch captions
      const capRes = await fetch('/api/youtube/captions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_url: url, target_language: 'he' }),
      })

      if (!capRes.ok) throw new Error('Failed to fetch captions')
      const capData = await capRes.json()

      if (capData.error) throw new Error(capData.error)

      const vid = capData.video_id
      setVideoId(vid)

      // Start player immediately
      setTimeout(() => initPlayer(vid), 100)

      // Step 2: Translate if not already in Hebrew
      if (capData.source_language === 'he') {
        setSegments(capData.segments.map((s) => ({ ...s, original: s.text })))
      } else {
        const trRes = await fetch('/api/youtube/translate-captions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            segments: capData.segments,
            target_language: 'he',
          }),
        })

        if (!trRes.ok) throw new Error('Translation failed')
        const trData = await trRes.json()
        setSegments(trData.segments)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="yt-translator">
      <button className="btn btn-secondary yt-back-btn" onClick={onBack}>
        {t('youtube.back')}
      </button>

      <form className="yt-form card" onSubmit={handleSubmit}>
        <label className="form-label">{t('youtube.paste_url')}</label>
        <div className="yt-input-row">
          <input
            type="text"
            className="form-input yt-url-input"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            dir="ltr"
          />
          <button
            type="submit"
            className="btn btn-primary yt-go-btn"
            disabled={!url.trim() || loading}
          >
            {loading ? t('youtube.loading') : t('youtube.translate')}
          </button>
        </div>
      </form>

      {error && (
        <div className="error-card">
          <p className="error-message">{error}</p>
        </div>
      )}

      {videoId && (
        <div className="yt-player-wrapper">
          <div className="yt-player-container">
            <div id="yt-player" />
          </div>

          <div className="yt-subtitle-box">
            {currentSub ? (
              <>
                <p className="yt-subtitle-text">{currentSub}</p>
                {currentOriginal && currentOriginal !== currentSub && (
                  <p className="yt-subtitle-original">{currentOriginal}</p>
                )}
              </>
            ) : (
              <p className="yt-subtitle-placeholder">
                {segments.length
                  ? t('youtube.waiting')
                  : t('youtube.translating_captions')}
              </p>
            )}
          </div>
        </div>
      )}

      {videoId && segments.length > 0 && (
        <details className="yt-full-transcript card">
          <summary className="yt-transcript-toggle">
            {t('youtube.full_transcript')}
          </summary>
          <div className="yt-transcript-list">
            {segments.map((seg, i) => (
              <div
                key={i}
                className={`yt-transcript-line ${
                  currentTime >= seg.start &&
                  currentTime < seg.start + seg.duration
                    ? 'active'
                    : ''
                }`}
                onClick={() => {
                  if (playerRef.current) {
                    playerRef.current.seekTo(seg.start, true)
                  }
                }}
              >
                <span className="yt-transcript-time">
                  {Math.floor(seg.start / 60)}:
                  {Math.floor(seg.start % 60)
                    .toString()
                    .padStart(2, '0')}
                </span>
                <span className="yt-transcript-text">{seg.text}</span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

export default YouTubeTranslator
