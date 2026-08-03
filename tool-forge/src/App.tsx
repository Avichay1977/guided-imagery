import { Route, Routes } from 'react-router-dom'
import { NavBar } from './components/NavBar'
import Home from './pages/Home'
import Build from './pages/Build'
import Console from './pages/Console'
import SettingsPage from './pages/Settings'

export default function App() {
  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4">
      <NavBar />
      <main className="flex-1 pb-16">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/build" element={<Build />} />
          <Route path="/tool/:toolId" element={<Console />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>
      <footer className="border-t border-panel-800 py-6 text-center text-xs text-panel-400">
        בונה הכלים · הכלים והמפתח נשמרים בדפדפן שלכם בלבד
      </footer>
    </div>
  )
}
