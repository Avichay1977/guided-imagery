import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { buildSpecLocally } from '../engine/localBuilder'
import { buildSpecWithClaude, describeApiError } from '../engine/claude'
import { DOMAIN_PATTERNS } from '../engine/patterns'
import { SpecPreview } from '../components/SpecPreview'
import type { ToolSpec } from '../types'

export default function Build() {
  const { engine, settings, saveTool } = useApp()
  const navigate = useNavigate()

  const [brief, setBrief] = useState('')
  const [spec, setSpec] = useState<ToolSpec | null>(null)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const build = async () => {
    if (!brief.trim()) return
    setBusy(true)
    setError('')
    setSpec(null)

    if (engine === 'claude') {
      try {
        const built = await buildSpecWithClaude(brief, settings.apiKey)
        setSpec(built)
        setNote('הלוח נבנה על ידי Claude לפי התיאור שלכם.')
        setBusy(false)
        return
      } catch (err) {
        setError(`${describeApiError(err)} — בינתיים נבנה לוח מהתבניות המקומיות.`)
      }
    }

    const { spec: local, match } = buildSpecLocally(brief)
    setSpec(local)
    setNote(
      match.pattern
        ? `נבנה מהתבנית "${match.pattern.title}" (זוהו: ${match.matched.slice(0, 4).join(', ')}). חברו מפתח API כדי שהלוח ייבנה במיוחד עבורכם.`
        : 'לא זוהה תחום מוכר, ולכן נבנה לוח כללי: קלט → רשימה → תגובה. חברו מפתח API כדי לקבל לוח מותאם.',
    )
    setBusy(false)
  }

  const save = () => {
    if (!spec) return
    saveTool(spec)
    navigate(`/tool/${spec.id}`)
  }

  return (
    <div className="space-y-6">
      <section className="device rounded-xl p-5">
        <h1 className="text-lg font-semibold text-white">מה אתם רוצים לנהל?</h1>
        <p className="mt-2 text-sm leading-relaxed text-panel-400">
          כתבו במשפט או שניים מה נכנס לכלי, מה אתם רוצים לקבל ממנו, ומה חשוב שיישמר. ככל
          שהתיאור קונקרטי יותר — הלוח שייבנה מדויק יותר.
        </p>

        <textarea
          className="mt-4 min-h-36 w-full resize-y rounded-lg border border-panel-700 bg-panel-950 px-3 py-2 text-sm leading-relaxed text-panel-200 outline-none placeholder:text-panel-600 focus:border-signal-500"
          placeholder="למשל: אני מוזיקאי. אני מקבל הערות מלקוחות על מיקסים, רוצה להפוך אותן לרשימת תיקונים לפי זמן בטראק, לקבל טיוטת תשובה ללקוח ולשמור הכול לפי פרויקט."
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
        />

        <div className="mt-3 flex flex-wrap gap-1.5">
          {DOMAIN_PATTERNS.slice(0, 4).map((pattern) => (
            <button
              key={pattern.id}
              type="button"
              onClick={() => setBrief(pattern.sampleBrief)}
              className="rounded-full border border-panel-700 px-2.5 py-1 text-[11px] text-panel-400 transition hover:border-signal-500 hover:text-signal-300"
            >
              {pattern.title}
            </button>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            disabled={busy || !brief.trim()}
            onClick={build}
            className="rounded-lg bg-signal-500 px-4 py-2 text-sm font-semibold text-panel-950 transition hover:bg-signal-400 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? 'בונה…' : 'בנה לי לוח שליטה'}
          </button>
          <span className="text-xs text-panel-400">
            {engine === 'claude' ? 'ייבנה על ידי Claude' : 'ייבנה ממנוע התבניות המקומי'}
          </span>
          {engine !== 'claude' && (
            <Link to="/settings" className="text-xs text-signal-300 hover:text-signal-400">
              חיבור מפתח API
            </Link>
          )}
        </div>
      </section>

      {error && (
        <p className="rounded-lg border border-amber-700/50 bg-amber-950/40 px-3 py-2 text-sm text-amber-200">
          {error}
        </p>
      )}

      {spec && (
        <section className="space-y-3">
          {note && <p className="text-xs text-panel-400">{note}</p>}
          <SpecPreview spec={spec} />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={save}
              className="rounded-lg bg-signal-500 px-4 py-2 text-sm font-semibold text-panel-950 transition hover:bg-signal-400"
            >
              שמור והפעל
            </button>
            <button
              type="button"
              onClick={build}
              disabled={busy}
              className="rounded-lg border border-panel-700 px-4 py-2 text-sm text-panel-200 transition hover:border-panel-600 disabled:opacity-40"
            >
              נסה שוב
            </button>
          </div>
        </section>
      )}
    </div>
  )
}
