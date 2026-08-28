import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { dismissFollowUp, saveDelayedOutcome } from '../lib/personalAdaptation'
import './SessionFeedback.css'

function DelayedOutcomeCheckIn({ followUp, onDone }) {
  const { t } = useTranslation()
  const [intensityLater, setIntensityLater] = useState(
    Number.isFinite(followUp?.intensityAfter) ? followUp.intensityAfter : 5,
  )
  const [saved, setSaved] = useState(false)

  if (!followUp) return null

  const handleSave = () => {
    const ok = saveDelayedOutcome(followUp.sessionId, { intensityLater })
    if (!ok) return
    setSaved(true)
    onDone?.()
  }

  const handleSkip = () => {
    dismissFollowUp(followUp.sessionId)
    onDone?.()
  }

  if (saved) {
    return (
      <div className="session-feedback card session-feedback-saved">
        <strong>{t('feedback.later_saved_title')}</strong>
        <span>{t('feedback.later_saved_body')}</span>
      </div>
    )
  }

  return (
    <div className="session-feedback card delayed-feedback">
      <div className="feedback-heading">
        <strong>{t('feedback.later_title')}</strong>
        <span>{t('feedback.later_subtitle')}</span>
      </div>

      <div className="feedback-field">
        <label htmlFor={`intensity-later-${followUp.sessionId}`}>
          {t('feedback.later_intensity')}
          <span className="feedback-value">{intensityLater}/10</span>
        </label>
        <input
          id={`intensity-later-${followUp.sessionId}`}
          type="range"
          min="0"
          max="10"
          step="1"
          value={intensityLater}
          onChange={(event) => setIntensityLater(Number(event.target.value))}
        />
      </div>

      <div className="feedback-actions">
        <button type="button" className="btn btn-primary" onClick={handleSave}>
          {t('feedback.later_save')}
        </button>
        <button type="button" className="btn btn-secondary" onClick={handleSkip}>
          {t('feedback.later_skip')}
        </button>
      </div>
      <p className="feedback-privacy">{t('feedback.later_privacy')}</p>
    </div>
  )
}

export default DelayedOutcomeCheckIn
