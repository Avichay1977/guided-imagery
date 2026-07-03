import { NavLink } from 'react-router-dom'

const tabs = [
  { to: '/', label: 'בית', icon: '🏠' },
  { to: '/rights', label: 'זכויות', icon: '✅' },
  { to: '/documents', label: 'מסמכים', icon: '📁' },
  { to: '/letters', label: 'מכתבים', icon: '✉️' },
]

export function NavBar() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-10 border-t border-calm-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-lg">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.to === '/'}
            className={({ isActive }) =>
              `flex flex-1 flex-col items-center gap-1 py-3 text-sm ${
                isActive ? 'font-bold text-calm-700' : 'text-gray-500'
              }`
            }
          >
            <span aria-hidden="true" className="text-xl">
              {tab.icon}
            </span>
            {tab.label}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
