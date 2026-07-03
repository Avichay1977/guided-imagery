import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useApp } from './store/AppContext'
import { NavBar } from './components/NavBar'
import { Disclaimer } from './components/Disclaimer'
import Welcome from './pages/Welcome'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Rights from './pages/Rights'
import RightDetail from './pages/RightDetail'
import Documents from './pages/Documents'
import Letters from './pages/Letters'
import LetterEditor from './pages/LetterEditor'
import Focus from './pages/Focus'

export default function App() {
  const { profile } = useApp()
  const location = useLocation()
  const isFocus = location.pathname === '/focus'
  const isOnboarding = location.pathname === '/onboarding'

  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col">
      <main className="flex-1 px-4 pb-28 pt-4">
        <Routes>
          <Route path="/" element={profile ? <Dashboard /> : <Welcome />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/rights" element={profile ? <Rights /> : <Navigate to="/" replace />} />
          <Route
            path="/rights/:id"
            element={profile ? <RightDetail /> : <Navigate to="/" replace />}
          />
          <Route path="/documents" element={<Documents />} />
          <Route path="/letters" element={<Letters />} />
          <Route path="/letters/:id" element={<LetterEditor />} />
          <Route path="/focus" element={profile ? <Focus /> : <Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        {!isFocus && <Disclaimer />}
      </main>
      {!isFocus && !isOnboarding && profile && <NavBar />}
    </div>
  )
}
