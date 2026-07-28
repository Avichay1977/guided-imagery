import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import VolumeSlider from './VolumeSlider'
import './SessionForm.css'

const DURATIONS = [3, 5, 10, 15, 20]
const DEPTH_OPTIONS = ['light', 'medium', 'deep']

// These ids must match backend/focus_areas.py and config.py. A backend test
// reads this file's translation keys and fails if the two ever drift apart.
const AGE_OPTIONS = ['young_child', 'child', 'teen', 'adult', 'senior']
const FOCUS_OPTIONS = [
  'general', 'anxiety', 'panic', 'sleep', 'bfrb', 'anger',
  'focus', 'social', 'transitions', 'sensory', 'confidence', 'pain', 'grief',
]
const NEURO_OPTIONS = ['none', 'adhd', 'autism', 'audhd']
const PACE_OPTIONS = ['very_slow', 'slow', 'natural', 'brisk']

function SessionForm({ onSubmit }) {
  const { t } = useTranslation()
  const [topic, setTopic] = useState('')
  const [duration, setDuration] = useState(10)
  const [mode, setMode] = useState('imagery')
  const [depth, setDepth] = useState('medium')
  const [ageGroup, setAgeGroup] = useState('adult')
  const [focus, setFocus] = useState('general')
  const [neuroprofile, setNeuroprofile] = useState('none')
  const [pace, setPace] = useState('slow')
  const [bellsVolume, setBellsVolume] = useState(50)
  const [musicVolume, setMusicVolume] = useState(35)

  // A restless listener does better with a moving delivery than with long
  // silences, so suggest it — without overriding a deliberate choice.
  const suggestFasterPace =
    (neuroprofile === 'adhd' || neuroprofile === 'audhd') &&
    (pace === 'slow' || pace === 'very_slow')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!topic.trim()) return
    onSubmit({
      topic: topic.trim(),
      duration,
      mode,
      depth: mode === 'hypnosis' ? depth : 'standard',
      ageGroup,
      focus,
      neuroprofile,
      pace,
      bellsVolume,
      musicVolume,
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

      {/* What the session is working on — gives the model a clinical shape
          to follow, while the free-text topic below carries the specifics. */}
      <div className="form-group">
        <label className="form-label" htmlFor="focus-select">{t('form.focus_label')}</label>
        <select
          id="focus-select"
          className="form-input form-select"
          value={focus}
          onChange={(e) => setFocus(e.target.value)}
        >
          {FOCUS_OPTIONS.map((f) => (
            <option key={f} value={f}>{t(`form.focus_${f}`)}</option>
          ))}
        </select>
      </div>

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

      {/* Duration and age each get a full row: both now offer five choices,
          which do not fit side by side without wrapping awkwardly. */}
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

      {/* How the listener's brain works, which changes the script substantially:
          literal language, no assumed mental imagery, no demand for stillness. */}
      <div className="form-group">
        <label className="form-label">{t('form.neuro_label')}</label>
        <div className="neuro-options">
          {NEURO_OPTIONS.map((n) => (
            <button
              key={n}
              type="button"
              className={`age-btn ${neuroprofile === n ? 'active' : ''}`}
              onClick={() => setNeuroprofile(n)}
            >
              {t(`form.neuro_${n}`)}
            </button>
          ))}
        </div>
        <p className="field-hint">{t('form.neuro_hint')}</p>
      </div>

      {/* Delivery speed: drives the voice rate, the silences, and how much the
          model writes to fill the requested minutes. */}
      <div className="form-group">
        <label className="form-label">{t('form.pace_label')}</label>
        <div className="pace-options">
          {PACE_OPTIONS.map((p) => (
            <button
              key={p}
              type="button"
              className={`age-btn ${pace === p ? 'active' : ''}`}
              onClick={() => setPace(p)}
            >
              {t(`form.pace_${p}`)}
            </button>
          ))}
        </div>
        {suggestFasterPace && (
          <p className="field-hint field-hint-suggest">{t('form.pace_suggest')}</p>
        )}
      </div>

      {/* Ambience: bells ring on the script's pause markers, music bed sits under everything */}
      <VolumeSlider
        icon="🔔"
        label={t('form.bells_label')}
        offHint={t('form.bells_off')}
        loudHint={t('form.bells_loud')}
        value={bellsVolume}
        onChange={setBellsVolume}
      />

      <VolumeSlider
        icon="🎵"
        label={t('form.music_label')}
        offHint={t('form.music_off')}
        loudHint={t('form.music_loud')}
        value={musicVolume}
        onChange={setMusicVolume}
      />

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
