import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useSession } from './hooks/useSession'
import SessionForm from './components/SessionForm'
import ProgressLoader from './components/ProgressLoader'
import AudioPlayer from './components/AudioPlayer'
import ScriptDisplay from './components/ScriptDisplay'
import LanguageToggle from './components/LanguageToggle'
import YouTubeTranslator from './components/YouTubeTranslator'
import MathCanvas from './components/MathCanvas/MathCanvas'

function App() {
  const { t, i18n } = useTranslation()
  const { state, progress, result, error, generate, reset } = useSession()
  const [page, setPage] = useState('home') // home | youtube | math

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
                <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', justifyContent: 'center' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setPage('math')}
                    style={{ background: 'linear-gradient(135deg, rgba(255,215,0,0.15), rgba(255,170,0,0.1))', border: '1px solid rgba(255,215,0,0.3)', color: '#ffd700', padding: '10px 20px', borderRadius: '12px', fontSize: '15px' }}
                  >
                    Visual Math Canvas
                  </button>
                  <button
                    className="btn btn-secondary yt-nav-btn"
                    onClick={() => setPage('youtube')}
                  >
                    {t('youtube.nav_button')}
                  </button>
                </div>
                <SessionForm onSubmit={handleGenerate} />
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
                <AudioPlayer audioUrl={result.audio_url} />
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
