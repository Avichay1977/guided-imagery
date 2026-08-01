import { useRef, useState } from 'react'
import { useApp } from '../store/AppContext'
import { normalizeSpec, newId } from '../engine/specSchema'
import type { ToolSpec } from '../types'

export default function SettingsPage() {
  const { settings, updateSettings, engine, tools, saveTool } = useApp()
  const [keyDraft, setKeyDraft] = useState(settings.apiKey)
  const [message, setMessage] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)

  const exportTools = () => {
    const blob = new Blob([JSON.stringify(tools, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'tool-forge-tools.json'
    link.click()
    URL.revokeObjectURL(url)
  }

  const importTools = async (file: File) => {
    try {
      const parsed: unknown = JSON.parse(await file.text())
      const list = Array.isArray(parsed) ? parsed : [parsed]
      let count = 0
      for (const raw of list) {
        const partial = (raw ?? {}) as Partial<ToolSpec>
        saveTool(normalizeSpec(partial, { id: newId('tool'), sourceBrief: partial.sourceBrief }))
        count += 1
      }
      setMessage(`יובאו ${count} כלים.`)
    } catch (err) {
      setMessage(`הייבוא נכשל: ${err instanceof Error ? err.message : 'קובץ לא תקין'}`)
    }
  }

  return (
    <div className="space-y-5">
      <section className="device rounded-xl p-5">
        <h1 className="text-lg font-semibold text-white">חיבור ל-Claude</h1>
        <p className="mt-2 text-sm leading-relaxed text-panel-400">
          בלי מפתח, האפליקציה עובדת ב<strong className="text-panel-200">מצב הדגמה</strong>: הכפתורים
          מפרקים את הקלט לפי כללים פשוטים, כדי שאפשר יהיה להרגיש את הזרימה. עם מפתח, כל פעולה רצה
          מול המודל ומחזירה תוצאה אמיתית.
        </p>

        <label className="mt-4 block">
          <span className="mb-1 block text-sm text-panel-200">מפתח API של Anthropic</span>
          <input
            className="w-full rounded-lg border border-panel-700 bg-panel-950 px-3 py-2 font-mono text-sm text-panel-200 outline-none focus:border-signal-500"
            type="password"
            dir="ltr"
            placeholder="sk-ant-…"
            value={keyDraft}
            onChange={(e) => setKeyDraft(e.target.value)}
          />
        </label>

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              updateSettings({ apiKey: keyDraft.trim() })
              setMessage(keyDraft.trim() ? 'המפתח נשמר בדפדפן.' : 'המפתח נמחק.')
            }}
            className="rounded-lg bg-signal-500 px-4 py-2 text-sm font-semibold text-panel-950 transition hover:bg-signal-400"
          >
            שמירת מפתח
          </button>
          <button
            type="button"
            onClick={() => {
              setKeyDraft('')
              updateSettings({ apiKey: '' })
              setMessage('המפתח נמחק מהדפדפן.')
            }}
            className="rounded-lg border border-panel-700 px-4 py-2 text-sm text-panel-200"
          >
            מחיקת מפתח
          </button>
        </div>

        <label className="mt-4 flex items-center gap-2 text-sm text-panel-200">
          <input
            type="checkbox"
            checked={settings.engine === 'demo'}
            onChange={(e) => updateSettings({ engine: e.target.checked ? 'demo' : 'auto' })}
          />
          להישאר במצב הדגמה גם כשיש מפתח
        </label>

        <p className="mt-3 text-xs text-panel-400">
          מצב נוכחי:{' '}
          <span className={engine === 'claude' ? 'text-signal-300' : 'text-amber-300'}>
            {engine === 'claude' ? 'פעולות רצות מול Claude' : 'פעולות רצות מקומית (הדגמה)'}
          </span>
        </p>

        <p className="mt-4 rounded-lg border border-amber-700/50 bg-amber-950/30 p-3 text-xs leading-relaxed text-amber-200">
          המפתח נשמר ב-localStorage של הדפדפן ונשלח ישירות מהדפדפן ל-Anthropic. זה מתאים לשימוש
          אישי על מחשב שלכם. אל תשתמשו במפתח משותף או ארגוני, ואל תפרסמו את הכלי הזה עם מפתח מוטמע
          — למוצר שמשרת משתמשים אחרים צריך שרת ביניים שמחזיק את המפתח.
        </p>
      </section>

      <section className="device rounded-xl p-5">
        <h2 className="text-sm font-semibold text-white">הכלים שלי</h2>
        <p className="mt-2 text-xs leading-relaxed text-panel-400">
          הכול נשמר בדפדפן הזה בלבד. ייצאו קובץ כדי לגבות או להעביר כלי למכשיר אחר.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={exportTools}
            disabled={tools.length === 0}
            className="rounded-lg border border-panel-700 px-4 py-2 text-sm text-panel-200 disabled:opacity-40"
          >
            ייצוא ({tools.length})
          </button>
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            className="rounded-lg border border-panel-700 px-4 py-2 text-sm text-panel-200"
          >
            ייבוא מקובץ
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="application/json"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void importTools(file)
              e.target.value = ''
            }}
          />
        </div>
      </section>

      {message && <p className="text-sm text-signal-300">{message}</p>}
    </div>
  )
}
