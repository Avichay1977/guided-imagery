import { useTranslation } from 'react-i18next'
import './LanguageToggle.css'

function LanguageToggle() {
  const { i18n } = useTranslation()
  const current = i18n.language

  const toggle = (lang) => {
    i18n.changeLanguage(lang)
  }

  return (
    <div className="lang-toggle">
      <button
        className={`lang-btn ${current === 'he' ? 'active' : ''}`}
        onClick={() => toggle('he')}
      >
        עב
      </button>
      <button
        className={`lang-btn ${current === 'en' ? 'active' : ''}`}
        onClick={() => toggle('en')}
      >
        EN
      </button>
    </div>
  )
}

export default LanguageToggle
