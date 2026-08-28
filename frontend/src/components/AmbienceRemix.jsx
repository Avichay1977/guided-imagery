import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import VolumeSlider from './VolumeSlider'
import './AmbienceRemix.css'

/**
 * Adjust the ambience of a finished session.
 *
 * The narration is kept server-side, so this re-mixes an existing recording
 * rather than generating a new one — no new script, no TTS, and the wait is
 * seconds instead of minutes.
 */
function AmbienceRemix({ sessionId, initialBells, initialMusic, onRemix, busy }) {
  const { t } = useTranslation()
  const [bells, setBells] = useState(initialBells)
  const [music, setMusic] = useState(initialMusic)
  const [applied, setApplied] = useState({ bells: initialBells, music: initialMusic })
  const [failed, setFailed] = useState(false)

  const dirty = bells !== applied.bells || music !== applied.music

  const handleApply = async () => {
    setFailed(false)
    const ok = await onRemix({ sessionId, bellsVolume: bells, musicVolume: music })
    if (ok) {
      setApplied({ bells, music })
    } else {
      setFailed(true)
    }
  }

  return (
    <div className="remix-card">
      <p className="remix-title">{t('form.remix_title')}</p>

      <VolumeSlider
        icon="🔔"
        label={t('form.bells_label')}
        offHint={t('form.bells_off')}
        loudHint={t('form.bells_loud')}
        value={bells}
        onChange={setBells}
        disabled={busy}
      />

      <VolumeSlider
        icon="🎵"
        label={t('form.music_label')}
        offHint={t('form.music_off')}
        loudHint={t('form.music_loud')}
        value={music}
        onChange={setMusic}
        disabled={busy}
      />

      <button
        className="btn btn-primary"
        onClick={handleApply}
        disabled={busy || !dirty}
      >
        {busy ? t('form.remix_applying') : t('form.remix_apply')}
      </button>

      {failed && <p className="remix-error">{t('form.remix_failed')}</p>}
      {!failed && !dirty && <p className="remix-hint">{t('form.remix_hint')}</p>}
    </div>
  )
}

export default AmbienceRemix
