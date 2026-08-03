import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { DOMAIN_PATTERNS } from '../engine/patterns'
import { normalizeSpec, newId } from '../engine/specSchema'
import { matchTool, suggestionsFor } from '../engine/usage'

/**
 * המסך הריק.
 *
 * נקודת הכניסה אינה רשימת כלים אלא שורה אחת: מה צריך עכשיו. אם כבר יש כלי
 * שעונה על זה — הוא נפתח. אם אין — נבנה אחד. הרשימה עדיין כאן, אבל היא מה
 * שהצטבר, לא מה שמתחילים ממנו.
 */
export default function Home() {
  const { tools, saveTool, getState, deleteTool, usage, archived, setArchived, record } = useApp()
  const navigate = useNavigate()
  const [need, setNeed] = useState('')
  const [dismissed, setDismissed] = useState<string[]>([])

  const shelf = tools.filter((tool) => !archived.includes(tool.id))
  const suggestions = useMemo(
    () => suggestionsFor(shelf, usage).filter((item) => !dismissed.includes(item.id)),
    [shelf, usage, dismissed],
  )

  const go = () => {
    const text = need.trim()
    if (!text) return
    const match = matchTool(text, shelf)
    if (match) {
      navigate(`/tool/${match.id}`)
      return
    }
    navigate(`/build?brief=${encodeURIComponent(text)}`)
  }

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
      <section className="device rounded-xl p-6">
        <h1 className="text-xl font-semibold text-white">מה אתם צריכים עכשיו?</h1>
        <p className="mt-2 text-sm leading-relaxed text-panel-400">
          כתבו במשפט. אם כבר יש כלי שעושה את זה — הוא ייפתח. אם לא — ייבנה אחד.
        </p>

        <div className="mt-4 flex gap-2">
          <input
            className="min-w-0 flex-1 rounded-lg border border-panel-700 bg-panel-950 px-3 py-2.5 text-sm text-panel-200 outline-none placeholder:text-panel-600 focus:border-signal-500"
            placeholder="לתכנן את היום · לפרק הערות של לקוח · לעקוב אחרי לידים"
            value={need}
            onChange={(e) => setNeed(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') go()
            }}
          />
          <button
            type="button"
            onClick={go}
            disabled={!need.trim()}
            className="rounded-lg bg-signal-500 px-4 py-2 text-sm font-semibold text-panel-950 transition hover:bg-signal-400 disabled:opacity-40"
          >
            קדימה
          </button>
        </div>
      </section>

      {suggestions.length > 0 && (
        <section className="space-y-2">
          {suggestions.map((suggestion) => (
            <div
              key={suggestion.id}
              className="rounded-xl border border-amber-700/40 bg-amber-950/20 p-4"
            >
              <p className="text-sm text-amber-100">{suggestion.text}</p>
              <p className="mt-1 text-[11px] text-amber-200/60">על סמך: {suggestion.evidence}</p>
              <div className="mt-3 flex gap-2">
                {suggestion.kind === 'retire' && (
                  <button
                    type="button"
                    onClick={() => {
                      setArchived(suggestion.toolId, true)
                      record({ kind: 'action', message: `כלי אורכב לפי הצעה: ${suggestion.text}` })
                    }}
                    className="rounded-lg border border-amber-600/60 px-3 py-1.5 text-xs text-amber-100 transition hover:bg-amber-900/40"
                  >
                    לארכב
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setDismissed((prev) => [...prev, suggestion.id])}
                  className="rounded-lg px-3 py-1.5 text-xs text-amber-200/70 transition hover:text-amber-100"
                >
                  לא עכשיו
                </button>
              </div>
            </div>
          ))}
        </section>
      )}

      {shelf.length > 0 && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">הכלים שלי</h2>
            <Link to="/build" className="text-sm text-signal-300 hover:text-signal-400">
              + כלי חדש
            </Link>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2">
            {shelf.map((tool) => {
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
                  <div className="mt-3 flex gap-3">
                    <button
                      type="button"
                      className="text-[11px] text-panel-600 transition hover:text-panel-300"
                      onClick={() => setArchived(tool.id, true)}
                    >
                      ארכוב
                    </button>
                    <button
                      type="button"
                      className="text-[11px] text-panel-600 transition hover:text-red-400"
                      onClick={() => {
                        if (confirm(`למחוק את "${tool.name}" ואת כל הפריטים שלו?`))
                          deleteTool(tool.id)
                      }}
                    >
                      מחיקת הכלי
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      )}

      {archived.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-panel-300">בארכיון</h2>
          <p className="mb-3 text-xs text-panel-500">
            לא נמחק — רק ירד מהמדף. הפריטים והגרסאות נשמרו.
          </p>
          <ul className="flex flex-wrap gap-2">
            {tools
              .filter((tool) => archived.includes(tool.id))
              .map((tool) => (
                <li key={tool.id}>
                  <button
                    type="button"
                    onClick={() => setArchived(tool.id, false)}
                    className="rounded-full border border-panel-700 px-3 py-1.5 text-xs text-panel-400 transition hover:border-signal-500 hover:text-signal-300"
                  >
                    {tool.icon} {tool.name} — החזרה למדף
                  </button>
                </li>
              ))}
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
