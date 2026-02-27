import { useTranslation } from 'react-i18next'
import './ProgressLoader.css'

function ProgressLoader({ progress }) {
  const { t } = useTranslation()

  return (
    <div className="progress-loader card">
      <div className="breath-circle">
        <div className="breath-inner" />
      </div>

      <p className="progress-message">
        {progress.message || t('form.generating')}
      </p>

      <div className="progress-bar-container">
        <div
          className="progress-bar-fill"
          style={{ width: `${progress.percent || 0}%` }}
        />
      </div>

      <span className="progress-percent">{progress.percent || 0}%</span>
    </div>
  )
}

export default ProgressLoader
