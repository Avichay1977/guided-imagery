import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import VolumeSlider from './VolumeSlider'
import { getInterventionPlan, getRecommendation } from '../lib/personalAdaptation'
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
const INTERVENTION_CHOICES = ['auto', 'balanced', 'grounded', 'rehearsal']

function SessionForm({ onSubmit }) {
  const { t } = useTranslation()
  const initialRecommendation = getRecommendation('general')
  const initialInterventionPlan = getInterventionPlan('general', 5)
  const [topic, setTopic] = useState('')
  const [duration, setDuration] = useState(10)
  const [mode, setMode] = useState(initialRecommendation?.mode || 'imagery')
  const [depth, setDepth] = useState('medium')
  const [ageGroup, setAgeGroup] = useState('adult')
  const [focus, setFocus] = useState('general')
  const [neuroprofile, setNeuroprofile] = useState('none')
  const [pace, setPace] = useState(initialRecommendation?.pace || 'slow')
  const [interventionChoice, setInterventionChoice] = useState('auto')
  const [interventionPlan, setInterventionPlan] = useState(initialInterventionPlan)
  const [bellsVolume, setBellsVolume] = useState(0)
  const [musicVolume, setMusicVolume] = useState(35)
  const [intensityBefore, setIntensityBefore] = useState(5)
  const [paceTouched, setPaceTouched] = useState(false)
  const [modeTouched, setModeTouched] = useState(false)
  const [recommendation, setRecommendation] = useState(initialRecommendation)

  const handleFocusChange = (event) => {
    const nextFocus = event.target.value
    const learned = getRecommendation(nextFocus)
    setFocus(nextFocus)
    setRecommendation(learned)
    setInterventionPlan(getInterventionPlan(nextFocus, intensityBefore))

    // Learned settings are soft defaults only. Once the listener makes a
    // deliberate choice in this form, history no longer overrides it.
    if (learned?.pace && !paceTouched) setPace(learned.pace)
    if (learned?.mode && !modeTouched) setMode(learned.mode)
  }

  const handleIntensityChange = (event) => {
    const nextIntensity = Number(event.target.value)
    setIntensityBefore(nextIntensity)
    setInterventionPlan(getInterventionPlan(focus, nextIntensity))
  }

  // A restless listener does better with a moving delivery than with long
  // silences, so suggest it — without overriding a deliberate choice.
  const suggestFasterPace =
    (neuroprofile === 'adhd' || neuroprofile === 'audhd') &&
    (pace === 'slow' || pace === 'very_slow')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!topic.trim()) return

    // Re-read at submit time so the exact current intensity determines Auto,
    // even if the UI state changed immediately before the button was pressed.
    const activeInterventionPlan = getInterventionPlan(focus, intensityBefore)
    const interventionStyle = interventionChoice === 'auto'
      ? activeInterventionPlan.style
      : interventionChoice
    const interventionSource = interventionChoice === 'auto'
      ? (activeInterventionPlan.scope === 'context' ? 'context' : activeInterventionPlan.phase)
      : 'manual'

    onSubmit({
      topic: topic.trim(),
      duration,
      mode,
      depth: mode === 'hypnosis' ? depth : 'standard',
      ageGroup,
      focus,
      neuroprofile,
      pace,
      interventionStyle,
      interventionSource,
      bellsVolume,
      musicVolume,
      intensityBefore,
    })
  }

  return (
    <form className="session-form card" onSubmit={handleSubmit}>
      <div className="form-group">
        <label className="form-label">{t('form.mode_label')}</label>
        <div className="mode-selector">
          <button
            type="button"
            className={`mode-btn ${mode === 'imagery' ? 'active' : ''}`}
            onClick={() => {
              setMode('imagery')
              setModeTouched(true)
            }}
          >
            <span className="mode-icon">🌿</span>
            <span className="mode-text">{t('form.mode_imagery')}</span>
          </button>
          <button
            type="button"
            className={`mode-btn ${mode === 'hypnosis' ? 'active' : ''}`}
            onClick={() => {
              setMode('hypnosis')
              setModeTouched(true)
            }}
          >
            <span className="mode-icon">🌀</span>
            <span className="mode-text">{t('form.mode_hypnosis')}</span>
          </button>
        </div>
      </div>

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

      <div className="form-group">
        <label className="form-label" htmlFor="focus-select">{t('form.focus_label')}</label>
        <select
          id="focus-select"
          className="form-input form-select"
          value={focus}
          onChange={handleFocusChange}
        >
          {FOCUS_OPTIONS.map((f) => (
            <option key={f} value={f}>{t(`form.focus_${f}`)}</option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label className="form-label">{t('form.approach_label')}</label>
        <div className="pace-options">
          {INTERVENTION_CHOICES.map((choice) => (
            <button
              key={choice}
              type="button"
              className={`age-btn ${interventionChoice === choice ? 'active' : ''}`}
              onClick={() => setInterventionChoice(choice)}
            >
              {t(`form.approach_${choice}`)}
            </button>
          ))}
        </div>
        {interventionChoice === 'auto' ? (
          <p className="field-hint field-hint-suggest">
            {interventionPlan.phase === 'learned'
              ? t('form.approach_auto_learned', {
                  style: t(`form.approach_${interventionPlan.style}`),
                  count: interventionPlan.samples,
                })
              : t('form.approach_auto_explore', {
                  style: t(`form.approach_${interventionPlan.style}`),
                  count: interventionPlan.styleSamples,
                })}
          </p>
        ) : (
          <p className="field-hint">{t('form.approach_manual_hint')}</p>
        )}
      </div>

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

      <div className="form-group">
        <label className="form-label" htmlFor="intensity-before">
          {t('form.intensity_before')}
          <span className="bells-value">{intensityBefore}/10</span>
        </label>
        <input
          id="intensity-before"
          type="range"
          className="bells-slider"
          min="0"
          max="10"
          step="1"
          value={intensityBefore}
          onChange={handleIntensityChange}
        />
        <p className="field-hint">{t('form.intensity_hint')}</p>
      </div>

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

      <div className="form-group">
        <label className="form-label">{t('form.pace_label')}</label>
        <div className="pace-options">
          {PACE_OPTIONS.map((p) => (
            <button
              key={p}
              type="button"
              className={`age-btn ${pace === p ? 'active' : ''}`}
              onClick={() => {
                setPace(p)
                setPaceTouched(true)
              }}
            >
              {t(`form.pace_${p}`)}
            </button>
          ))}
        </div>
        {recommendation && (
          <p className="field-hint field-hint-suggest">
            {t('form.learned_from', { count: recommendation.samples })}
          </p>
        )}
        {suggestFasterPace && (
          <p className="field-hint field-hint-suggest">{t('form.pace_suggest')}</p>
        )}
      </div>

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
