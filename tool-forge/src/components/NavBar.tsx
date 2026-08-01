import { NavLink } from 'react-router-dom'
import { useApp } from '../store/AppContext'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 text-sm transition ${
    isActive ? 'bg-panel-700 text-white' : 'text-panel-400 hover:text-panel-200'
  }`

export function NavBar() {
  const { engine } = useApp()

  return (
    <header className="flex flex-wrap items-center gap-2 py-5">
      <NavLink to="/" className="ms-1 flex items-center gap-2 text-lg font-semibold text-white">
        <span aria-hidden>🎛️</span>
        בונה הכלים
      </NavLink>

      <nav className="flex items-center gap-1">
        <NavLink to="/" className={linkClass} end>
          הכלים שלי
        </NavLink>
        <NavLink to="/build" className={linkClass}>
          בניית כלי
        </NavLink>
        <NavLink to="/settings" className={linkClass}>
          הגדרות
        </NavLink>
      </nav>

      <NavLink
        to="/settings"
        className={`ms-auto rounded-full border px-3 py-1 text-xs ${
          engine === 'claude'
            ? 'border-signal-500 text-signal-300'
            : 'border-panel-700 text-panel-400'
        }`}
      >
        {engine === 'claude' ? 'מחובר ל-Claude' : 'מצב הדגמה'}
      </NavLink>
    </header>
  )
}
