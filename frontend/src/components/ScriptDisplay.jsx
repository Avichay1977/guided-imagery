import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import './ScriptDisplay.css'

function ScriptDisplay({ script }) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [translatedScript, setTranslatedScript] = useState(null)
  const [translating, setTranslating] = useState(false)
  const [showTranslation, setShowTranslation] = useState(false)

  const cleanText = (text) =>
    text.replace(/\[(pause|short_pause|long_pause|breath)\]/g, '\n\u00B7 \u00B7 \u00B7\n')

  const otherLang = i18n.language === 'he' ? 'en' : 'he'

  const handleTranslate = useCallback(async () => {
    if (translatedScript) {
      setShowTranslation(!showTranslation)
      return
    }

    setTranslating(true)
    try {
      const res = await fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: script,
          source_language: i18n.language,
          target_language: otherLang,
        }),
      })
      if (!res.ok) throw new Error('Translation failed')
      const data = await res.json()
      setTranslatedScript(data.translated_text)
      setShowTranslation(true)
    } catch {
      setTranslatedScript(null)
    } finally {
      setTranslating(false)
    }
  }, [script, i18n.language, otherLang, translatedScript, showTranslation])

  const translationLabel = otherLang === 'he' ? 'עברית' : 'English'

  return (
    <div className="script-display">
      <div className="script-buttons">
        <button
          className="btn btn-secondary script-toggle"
          onClick={() => setOpen(!open)}
        >
          {open ? t('player.hide_script') : t('player.show_script')}
        </button>

        {open && (
          <button
            className={`btn btn-secondary script-toggle translate-btn ${showTranslation ? 'active' : ''}`}
            onClick={handleTranslate}
            disabled={translating}
          >
            {translating
              ? t('player.translating')
              : showTranslation
                ? t('player.hide_translation')
                : `${t('player.show_translation')} (${translationLabel})`}
          </button>
        )}
      </div>

      {open && (
        <div className={`script-content card ${showTranslation ? 'bilingual' : ''}`}>
          {showTranslation && translatedScript ? (
            <div className="bilingual-view">
              <div className="script-column original">
                <div className="column-label">{i18n.language === 'he' ? 'עברית' : 'English'}</div>
                <p className="script-text">{cleanText(script)}</p>
              </div>
              <div className="script-divider" />
              <div className={`script-column translation ${otherLang === 'he' ? 'rtl' : 'ltr'}`}>
                <div className="column-label">{translationLabel}</div>
                <p className="script-text">{cleanText(translatedScript)}</p>
              </div>
            </div>
          ) : (
            <p className="script-text">{cleanText(script)}</p>
          )}
        </div>
      )}
    </div>
  )
}

export default ScriptDisplay
