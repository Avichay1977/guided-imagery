import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useSession } from './hooks/useSession'
import SessionForm from './components/SessionForm'
import ProgressLoader from './components/ProgressLoader'
import AudioPlayer from './components/AudioPlayer'
import ScriptDisplay from './components/ScriptDisplay'
import LanguageToggle from './components/LanguageToggle'

function App() {
  const { t, i18n } = useTranslation()
  const { state, progress, result, error, generate, reset } = useSession()

  useEffect(() => {
    document.documentElement.dir = i18n.dir()
    document.documentElement.lang = i18n.language
  }, [i18n, i18n.language])

  const handleGenerate = ({ topic, duration, mode, depth, ageGroup, bellsVolume }) => {
    generate({
      topic,
      durationMinutes: duration,
      language: i18n.language,
      mode,
      depth,
      ageGroup,
      bellsVolume,
    })
  }

  return (
    <div className="app">
      <div className="app-bg" />

      <header className="app-header">
        <LanguageToggle />
        <h1 className="app-title">{t('app_title')}</h1>
        <p className="app-subtitle">{t('app_subtitle')}</p>
      </header>

      <main className="app-main">
        {state === 'idle' && (
          <SessionForm onSubmit={handleGenerate} />
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
            <AudioPlayer audioUrl={result.audio_url} />
            <ScriptDisplay script={result.script} />
            <button className="btn btn-secondary" onClick={reset}>
              {t('player.new_session')}
            </button>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
