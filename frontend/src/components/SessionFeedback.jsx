import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { saveOutcome } from '../lib/personalAdaptation'
import './SessionFeedback.css'

function SessionFeedback({ sessionId, intensityBefore }) {
  const { t } = useTranslation()
  const [intensityAfter, setIntensityAfter] = useState(
    Number.isFinite(intensityBefore) ? intensityBefore : 5,
  )
  const [helpfulness, setHelpfulness] = useState(3)
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    const ok = saveOutcome(sessionId, { intensityAfter, helpfulness })
    if (ok) setSaved(true)
  }

  if (saved) {
    return (
      <div className="session-feedback card session-feedback-saved">
        <strong>{t('feedback.saved_title')}</strong>
        <span>{t('feedback.saved_body')}</span>
      </div>
    )
  }

  return (
    <div className="session-feedback card">
      <div className="feedback-heading">
        <strong>{t('feedback.title')}</strong>
        <span>{t('feedback.subtitle')}</span>
      </div>

      <div className="feedback-field">
        <label htmlFor="intensity-after">
          {t('feedback.intensity_after')}
          <span className="feedback-value">{intensityAfter}/10</span>
        </label>
        <input
          id="intensity-after"
          type="range"
          min="0"
          max="10"
          step="1"
          value={intensityAfter}
          onChange={(event) => setIntensityAfter(Number(event.target.value))}
        />
      </div>

      <div className="feedback-field">
        <span>{t('feedback.helpfulness')}</span>
        <div className="feedback-score-row">
          {[1, 2, 3, 4, 5].map((score) => (
            <button
              key={score}
              type="button"
              className={`feedback-score ${helpfulness === score ? 'active' : ''}`}
              onClick={() => setHelpfulness(score)}
            >
              {score}
            </button>
          ))}
        </div>
      </div>

      <button type="button" className="btn btn-primary" onClick={handleSave}>
        {t('feedback.save')}
      </button>
      <p className="feedback-privacy">{t('feedback.privacy')}</p>
    </div>
  )
}

export default SessionFeedback
