import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import { AppProvider } from './store/AppContext'
import './index.css'

// רישום ה-service worker רק בבנייה — כדי שהתקנה על הטלפון תעבוד ושהאפליקציה
// תיפתח גם בלי רשת. בפיתוח הוא רק היה מטמין קבצים ישנים.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('sw.js', { scope: './' })
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <AppProvider>
        <App />
      </AppProvider>
    </HashRouter>
  </StrictMode>,
)
