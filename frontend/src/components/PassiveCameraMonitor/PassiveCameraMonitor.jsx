import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useRPPG } from '../../hooks/useRPPG'
import './PassiveCameraMonitor.css'

/**
 * PassiveCameraMonitor - floating widget for rPPG-based heart rate monitoring.
 * Props:
 *   phase: 'idle' | 'session' | 'complete'
 */
export default function PassiveCameraMonitor({ phase }) {
  const { t } = useTranslation()
  const { videoRef, canvasRef, status, metrics, baseline, start, stop } = useRPPG()
  const [collapsed, setCollapsed] = useState(false)
  const [privacyAcknowledged, setPrivacyAcknowledged] = useState(false)

  // Compute delta vs baseline when phase is complete
  const delta =
    phase === 'complete' && baseline != null && metrics.bpm != null
      ? metrics.bpm - baseline
      : null

  // Confidence color
  const confidenceColor =
    metrics.confidence >= 0.65 ? '#4caf50' :
    metrics.confidence >= 0.35 ? '#ff9800' :
    '#f44336'

  const handleStartClick = () => {
    if (!privacyAcknowledged) {
      setPrivacyAcknowledged(true)
      return
    }
    start()
  }

  // Silent failure — render nothing when denied
  if (status === 'denied') return null

  return (
    <div className={`pcm-wrapper ${collapsed && status === 'active' ? 'pcm-collapsed' : ''}`}>
      {/* Hidden video and canvas for processing — always in DOM when active */}
      <video
        ref={videoRef}
        muted
        playsInline
        style={{ display: 'none' }}
        aria-hidden="true"
      />
      <canvas
        ref={canvasRef}
        width={160}
        height={120}
        style={{ display: 'none' }}
        aria-hidden="true"
      />

      {/* IDLE: start button */}
      {status === 'idle' && (
        <div className="pcm-idle-area">
          {privacyAcknowledged ? (
            <button className="pcm-start-btn" onClick={start}>
              <span className="pcm-heart-icon">❤️</span>
              {t('monitor.start')}
            </button>
          ) : (
            <div className="pcm-privacy-prompt">
              <p className="pcm-privacy-text">{t('monitor.privacy')}</p>
              <button className="pcm-start-btn" onClick={handleStartClick}>
                <span className="pcm-heart-icon">❤️</span>
                {t('monitor.start')}
              </button>
            </div>
          )}
        </div>
      )}

      {/* REQUESTING / WARMING: pulsing calibrating indicator */}
      {(status === 'requesting' || status === 'warming') && (
        <div className="pcm-card pcm-calibrating">
          <span className="pcm-pulse-dot" />
          <span className="pcm-calibrating-text">{t('monitor.calibrating')}</span>
        </div>
      )}

      {/* ACTIVE: full floating card */}
      {status === 'active' && (
        <>
          {collapsed ? (
            /* Collapsed chip */
            <button
              className="pcm-chip"
              onClick={() => setCollapsed(false)}
              aria-label={t('monitor.expand')}
            >
              ❤️ {metrics.bpm != null ? `${metrics.bpm}` : '—'}
            </button>
          ) : (
            /* Expanded card */
            <div className="pcm-card pcm-expanded">
              <div className="pcm-card-header">
                <span className="pcm-hr-label">{t('monitor.heart_rate')}</span>
                <div className="pcm-header-actions">
                  <button
                    className="pcm-icon-btn"
                    onClick={() => setCollapsed(true)}
                    aria-label={t('monitor.collapse')}
                    title={t('monitor.collapse')}
                  >
                    ▾
                  </button>
                  <button
                    className="pcm-icon-btn pcm-close-btn"
                    onClick={stop}
                    aria-label="Stop"
                    title="Stop"
                  >
                    ×
                  </button>
                </div>
              </div>

              <div className="pcm-bpm-display">
                <span className="pcm-bpm-number pcm-pulse-anim">
                  {metrics.bpm != null ? metrics.bpm : '—'}
                </span>
                <span className="pcm-bpm-unit">bpm</span>
              </div>

              {/* Confidence bar */}
              <div className="pcm-signal-row">
                <span className="pcm-signal-label">{t('monitor.signal')}</span>
                <div className="pcm-confidence-track">
                  <div
                    className="pcm-confidence-fill"
                    style={{
                      width: `${Math.round(metrics.confidence * 100)}%`,
                      backgroundColor: confidenceColor,
                    }}
                  />
                </div>
              </div>

              {/* Delta vs baseline (complete phase only) */}
              {delta != null && (
                <div className={`pcm-delta ${delta <= 0 ? 'pcm-delta-down' : 'pcm-delta-up'}`}>
                  {delta <= 0
                    ? `↓${Math.abs(delta)} bpm`
                    : `↑${delta} bpm`}
                  <span className="pcm-delta-label"> {t('monitor.vs_baseline')}</span>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ERROR state: small retry button */}
      {status === 'error' && (
        <div className="pcm-card pcm-error">
          <button className="pcm-start-btn" onClick={start}>
            ❤️ {t('monitor.start')}
          </button>
        </div>
      )}
    </div>
  )
}
