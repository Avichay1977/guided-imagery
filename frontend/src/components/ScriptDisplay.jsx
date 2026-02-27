import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import './ScriptDisplay.css'

function ScriptDisplay({ script }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  const cleanScript = script
    .replace(/\[(pause|short_pause|long_pause|breath)\]/g, '\n\u00B7 \u00B7 \u00B7\n')

  return (
    <div className="script-display">
      <button
        className="btn btn-secondary script-toggle"
        onClick={() => setOpen(!open)}
      >
        {open ? t('player.hide_script') : t('player.show_script')}
      </button>

      {open && (
        <div className="script-content card">
          <p className="script-text">{cleanScript}</p>
        </div>
      )}
    </div>
  )
}

export default ScriptDisplay
