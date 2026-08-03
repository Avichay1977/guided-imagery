import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { DOMAIN_PATTERNS } from '../engine/patterns'
import { normalizeSpec, newId } from '../engine/specSchema'

export default function Home() {
  const { tools, saveTool, getState, deleteTool } = useApp()
  const navigate = useNavigate()

  const installTemplate = (patternId: string) => {
    const pattern = DOMAIN_PATTERNS.find((p) => p.id === patternId)
    if (!pattern) return
    const spec = normalizeSpec(pattern.build(), {
      id: newId('tool'),
      sourceBrief: pattern.sampleBrief,
      builtBy: 'local',
    })
    saveTool(spec)
    navigate(`/tool/${spec.id}`)
  }

  return (
    <div className="space-y-8">
      {tools.length === 0 && (
        <section className="device rounded-xl p-6">
          <h1 className="text-xl font-semibold text-white">כלי AI אישי, בלי לכתוב שורת קוד</h1>
          <p className="mt-3 text-sm leading-relaxed text-panel-400">
            אתם מתארים מה אתם רוצים לנהל או לבצע, והמערכת בונה לכם לוח שליטה מותאם — עם שדות
            קלט, סליידרים, כפתורי פעולה ורשימה שמצטברת. לא צ׳אט, מכשיר.
          </p>
          <Link
            to="/build"
            className="mt-5 inline-block rounded-lg bg-signal-500 px-4 py-2 text-sm font-semibold text-panel-950 transition hover:bg-signal-400"
          >
            תארו כלי ובנו אותו
          </Link>
        </section>
      )}

      {tools.length > 0 && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h1 className="text-lg font-semibold text-white">הכלים שלי</h1>
            <Link to="/build" className="text-sm text-signal-300 hover:text-signal-400">
              + כלי חדש
            </Link>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2">
            {tools.map((tool) => {
              const state = getState(tool.id)
              return (
                <li key={tool.id} className="device rounded-xl p-4">
                  <Link to={`/tool/${tool.id}`} className="block">
                    <div className="flex items-center gap-2">
                      <span className="text-2xl" aria-hidden>
                        {tool.icon}
                      </span>
                      <span className="font-semibold text-white">{tool.name}</span>
                    </div>
                    <p className="mt-2 text-xs leading-relaxed text-panel-400">{tool.tagline}</p>
                    <p className="mt-3 text-[11px] text-panel-600">
                      {tool.actions.length} פעולות · {state.items.length} פריטים ברשימה
                      {tool.builtBy === 'claude' ? ' · נבנה על ידי Claude' : ''}
                    </p>
                  </Link>
                  <button
                    type="button"
                    className="mt-3 text-[11px] text-panel-600 transition hover:text-red-400"
                    onClick={() => {
                      if (confirm(`למחוק את "${tool.name}" ואת כל הפריטים שלו?`)) deleteTool(tool.id)
                    }}
                  >
                    מחיקת הכלי
                  </button>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      <section>
        <h2 className="mb-1 text-lg font-semibold text-white">כלים מוכנים</h2>
        <p className="mb-3 text-sm text-panel-400">
          התקינו אחד כדי לראות איך נראה לוח שליטה, ואז שנו אותו או בנו משלכם.
        </p>
        <ul className="grid gap-3 sm:grid-cols-2">
          {DOMAIN_PATTERNS.map((pattern) => (
            <li key={pattern.id} className="rounded-xl border border-panel-800 bg-panel-900 p-4">
              <h3 className="text-sm font-semibold text-panel-200">{pattern.title}</h3>
              <p className="mt-2 text-xs leading-relaxed text-panel-400">{pattern.sampleBrief}</p>
              <button
                type="button"
                onClick={() => installTemplate(pattern.id)}
                className="mt-3 rounded-lg border border-panel-700 px-3 py-1.5 text-xs text-panel-200 transition hover:border-signal-500 hover:text-signal-300"
              >
                התקנה
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
