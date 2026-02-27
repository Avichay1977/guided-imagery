import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import './SessionForm.css'

const DURATIONS = [3, 5, 10, 15, 20]
const DEPTH_OPTIONS = ['light', 'medium', 'deep']
const AGE_OPTIONS = ['children', 'teens', 'adults']

function SessionForm({ onSubmit }) {
  const { t } = useTranslation()
  const [topic, setTopic] = useState('')
  const [duration, setDuration] = useState(10)
  const [mode, setMode] = useState('imagery')
  const [depth, setDepth] = useState('medium')
  const [ageGroup, setAgeGroup] = useState('adults')
  const [bellsVolume, setBellsVolume] = useState(50)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!topic.trim()) return
    onSubmit({
      topic: topic.trim(),
      duration,
      mode,
      depth: mode === 'hypnosis' ? depth : 'standard',
      ageGroup,
      bellsVolume,
    })
  }

  return (
    <form className="session-form card" onSubmit={handleSubmit}>
      {/* Mode Selector */}
      <div className="form-group">
        <label className="form-label">{t('form.mode_label')}</label>
        <div className="mode-selector">
          <button
            type="button"
            className={`mode-btn ${mode === 'imagery' ? 'active' : ''}`}
            onClick={() => setMode('imagery')}
          >
            <span className="mode-icon">🌿</span>
            <span className="mode-text">{t('form.mode_imagery')}</span>
          </button>
          <button
            type="button"
            className={`mode-btn ${mode === 'hypnosis' ? 'active' : ''}`}
            onClick={() => setMode('hypnosis')}
          >
            <span className="mode-icon">🌀</span>
            <span className="mode-text">{t('form.mode_hypnosis')}</span>
          </button>
        </div>
      </div>

      {/* Depth Selector - only for hypnosis */}
      {mode === 'hypnosis' && (
        <div className="form-group depth-group">
          <label className="form-label">{t('form.depth_label')}</label>
          <div className="depth-options">
            {DEPTH_OPTIONS.map((d) => (
              <button
                key={d}
                type="button"
                className={`depth-btn ${depth === d ? 'active' : ''}`}
                onClick={() => setDepth(d)}
              >
                <span className="depth-name">{t(`form.depth_${d}`)}</span>
                <span className="depth-desc">{t(`form.depth_${d}_desc`)}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Topic - free prompt */}
      <div className="form-group">
        <label className="form-label">{t('form.topic_label')}</label>
        <textarea
          className="form-input form-textarea"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder={t('form.topic_placeholder')}
          rows={3}
        />
      </div>

      {/* Duration + Age Group in one row */}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">{t('form.duration_label')}</label>
          <div className="duration-options">
            {DURATIONS.map((d) => (
              <button
                key={d}
                type="button"
                className={`duration-btn ${duration === d ? 'active' : ''}`}
                onClick={() => setDuration(d)}
              >
                {d} {t('form.minutes')}
              </button>
            ))}
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">{t('form.age_label')}</label>
          <div className="age-options">
            {AGE_OPTIONS.map((a) => (
              <button
                key={a}
                type="button"
                className={`age-btn ${ageGroup === a ? 'active' : ''}`}
                onClick={() => setAgeGroup(a)}
              >
                {t(`form.age_${a}`)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Bells Volume */}
      <div className="form-group bells-group">
        <label className="form-label">
          <span className="bells-icon">🔔</span>
          {t('form.bells_label')}
          <span className="bells-value">{bellsVolume}%</span>
        </label>
        <input
          type="range"
          className="bells-slider"
          min="0"
          max="100"
          step="5"
          value={bellsVolume}
          onChange={(e) => setBellsVolume(Number(e.target.value))}
        />
        <div className="bells-hints">
          <span>{t('form.bells_off')}</span>
          <span>{t('form.bells_loud')}</span>
        </div>
      </div>

      <button
        type="submit"
        className="btn btn-primary"
        disabled={!topic.trim()}
      >
        {mode === 'hypnosis' ? t('form.generate_hypnosis') : t('form.generate')}
      </button>
    </form>
  )
}

export default SessionForm
