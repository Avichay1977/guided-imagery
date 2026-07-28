import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useSession } from './hooks/useSession'
import SessionForm from './components/SessionForm'
import ProgressLoader from './components/ProgressLoader'
import AudioPlayer from './components/AudioPlayer'
import AmbienceRemix from './components/AmbienceRemix'
import ScriptDisplay from './components/ScriptDisplay'
import LanguageToggle from './components/LanguageToggle'
import YouTubeTranslator from './components/YouTubeTranslator'
import MathCanvas from './components/MathCanvas/MathCanvas'

function App() {
  const { t, i18n } = useTranslation()
  const { state, progress, result, error, remixing, generate, remix, reset } = useSession()
  const [page, setPage] = useState('home') // home | youtube | math
  // Remembered so the remix panel opens on the settings this session was made with.
  const [mix, setMix] = useState({ bells: 0, music: 35 })

  useEffect(() => {
    document.documentElement.dir = i18n.dir()
    document.documentElement.lang = i18n.language
  }, [i18n, i18n.language])

  const handleGenerate = ({
    topic, duration, mode, depth, ageGroup, focus, neuroprofile, pace,
    bellsVolume, musicVolume,
  }) => {
    setMix({ bells: bellsVolume, music: musicVolume })
    generate({
      topic,
      durationMinutes: duration,
      language: i18n.language,
      mode,
      depth,
      ageGroup,
      focus,
      neuroprofile,
      pace,
      bellsVolume,
      musicVolume,
    })
  }

  return (
    <div className="app">
      <div className="app-bg" />

      <header className={`app-header ${page === 'math' ? 'app-main-hidden' : ''}`}>
        <LanguageToggle />
        <h1 className="app-title">
          {page === 'youtube' ? t('youtube.title') : t('app_title')}
        </h1>
        <p className="app-subtitle">
          {page === 'youtube' ? t('youtube.subtitle') : t('app_subtitle')}
        </p>
      </header>

      {page === 'math' && (
        <MathCanvas onBack={() => setPage('home')} />
      )}

      <main className={`app-main ${page === 'youtube' ? 'app-main-wide' : ''} ${page === 'math' ? 'app-main-hidden' : ''}`}>
        {page === 'youtube' ? (
          <YouTubeTranslator onBack={() => setPage('home')} />
        ) : page !== 'math' ? (
          <>
            {state === 'idle' && (
              <>
                <SessionForm onSubmit={handleGenerate} />
                <button
                  className="btn btn-secondary yt-nav-btn"
                  onClick={() => setPage('youtube')}
                >
                  {t('youtube.nav_button')}
                </button>
                <button
                  className="btn btn-secondary yt-nav-btn"
                  onClick={() => setPage('math')}
                  style={{ marginTop: '8px' }}
                >
                  Visual Math Canvas
                </button>
              </>
            )}

            {state === 'loading' && (
              <ProgressLoader progress={progress} />
            )}

            {state === 'error' && (
              <div className="error-card">
                <p className="error-message">{error || t('errors.generation_failed')}</p>
                <button className="btn btn-primary" onClick={reset}>
                  {t('form.generate')}
                </button>
              </div>
            )}

            {state === 'complete' && result && (
              <div className="result-section">
                {/* Keyed on the URL so a remix loads the new mix from the start */}
                <AudioPlayer key={result.audio_url} audioUrl={result.audio_url} />
                {result.session_id && (
                  /* Keyed per session so a new one starts from its own
                     settings instead of the previous session's remix */
                  <AmbienceRemix
                    key={result.session_id}
                    sessionId={result.session_id}
                    initialBells={mix.bells}
                    initialMusic={mix.music}
                    onRemix={remix}
                    busy={remixing}
                  />
                )}
                <ScriptDisplay script={result.script} />
                <button className="btn btn-secondary" onClick={reset}>
                  {t('player.new_session')}
                </button>
              </div>
            )}
          </>
        ) : null}
      </main>
    </div>
  )
}

export default App
