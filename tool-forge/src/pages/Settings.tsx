import { useRef, useState } from 'react'
import { useApp } from '../store/AppContext'
import { normalizeSpec, newId } from '../engine/specSchema'
import { CALENDAR_SCOPE, connect, disconnect, isConnected } from '../engine/googleCalendar'
import type { ToolSpec } from '../types'

export default function SettingsPage() {
  const { settings, updateSettings, engine, tools, saveTool, audit, record, clearAudit } = useApp()
  const [keyDraft, setKeyDraft] = useState(settings.apiKey)
  const [clientIdDraft, setClientIdDraft] = useState(settings.googleClientId)
  const [message, setMessage] = useState('')
  const [calendarError, setCalendarError] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [connected, setConnected] = useState(isConnected())
  const fileInput = useRef<HTMLInputElement>(null)

  const connectCalendar = async () => {
    setConnecting(true)
    setCalendarError('')
    try {
      updateSettings({ googleClientId: clientIdDraft.trim() })
      await connect(clientIdDraft)
      setConnected(true)
      record({ kind: 'info', message: 'התחברת ל-Google Calendar' })
    } catch (error) {
      setCalendarError(error instanceof Error ? error.message : 'ההתחברות נכשלה')
    } finally {
      setConnecting(false)
    }
  }

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
        <h2 className="text-sm font-semibold text-white">Google Calendar</h2>
        <p className="mt-2 text-sm leading-relaxed text-panel-400">
          הפעולה החיצונית היחידה שהמערכת יודעת לבצע: יצירת אירוע ביומן, ורק אחרי אישור מפורש
          שלכם. אין קריאה של היומן מעבר לבדיקת כפילות, ואין שליחת הודעות.
        </p>

        <div className="mt-4 flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${connected ? 'bg-signal-400' : 'bg-panel-600'}`}
            aria-hidden
          />
          <span className="text-sm text-panel-200">
            {connected ? 'מחובר ליומן' : 'לא מחובר'}
          </span>
        </div>

        <label className="mt-3 block">
          <span className="mb-1 block text-sm text-panel-200">Google OAuth Client ID</span>
          <input
            className="w-full rounded-lg border border-panel-700 bg-panel-950 px-3 py-2 font-mono text-xs text-panel-200 outline-none focus:border-signal-500"
            dir="ltr"
            placeholder="123456789-abc.apps.googleusercontent.com"
            value={clientIdDraft}
            onChange={(e) => setClientIdDraft(e.target.value)}
          />
        </label>

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={connecting || !clientIdDraft.trim()}
            onClick={() => void connectCalendar()}
            className="rounded-lg bg-signal-500 px-4 py-2 text-sm font-semibold text-panel-950 transition hover:bg-signal-400 disabled:opacity-40"
          >
            {connecting ? 'מתחבר…' : connected ? 'התחברות מחדש' : 'התחברות ליומן'}
          </button>
          {connected && (
            <button
              type="button"
              onClick={() => {
                disconnect()
                setConnected(false)
                record({ kind: 'info', message: 'החיבור ליומן נותק' })
              }}
              className="rounded-lg border border-panel-700 px-4 py-2 text-sm text-panel-200"
            >
              ניתוק
            </button>
          )}
        </div>

        {calendarError && <p className="mt-2 text-sm text-red-300">{calendarError}</p>}

        <label className="mt-4 flex items-start gap-2 text-sm text-panel-200">
          <input
            type="checkbox"
            className="mt-1"
            checked={!settings.simulate}
            onChange={(e) => {
              updateSettings({ simulate: !e.target.checked })
              record({
                kind: 'warning',
                message: e.target.checked
                  ? 'מצב סימולציה כובה — אישור ייצור אירוע אמיתי'
                  : 'מצב סימולציה הופעל',
              })
            }}
          />
          <span>
            לבצע פעולות אמיתיות ביומן
            <span className="block text-xs text-panel-400">
              כשזה כבוי (ברירת המחדל), אישור מריץ סימולציה בלבד ושום דבר לא נוגע ביומן.
            </span>
          </span>
        </label>

        <details className="mt-4 text-xs text-panel-400">
          <summary className="cursor-pointer text-panel-200">איך משיגים Client ID</summary>
          <ol className="mt-2 list-decimal space-y-1 pe-4 leading-relaxed">
            <li>
              ב-Google Cloud Console: יוצרים פרויקט, ומפעילים את <code>Google Calendar API</code>.
            </li>
            <li>
              במסך ההסכמה (OAuth consent screen) מוסיפים את ההרשאה <code dir="ltr">{CALENDAR_SCOPE}</code>{' '}
              ואת עצמכם כמשתמש בדיקה.
            </li>
            <li>
              יוצרים <code>OAuth client ID</code> מסוג <code>Web application</code>, ומוסיפים
              ל-Authorized JavaScript origins את הכתובת שממנה האפליקציה רצה (למשל{' '}
              <code dir="ltr">https://avichay1977.github.io</code>).
            </li>
            <li>מדביקים כאן את ה-Client ID. אין צורך ב-client secret — ואסור להשתמש בו בדפדפן.</li>
          </ol>
        </details>
      </section>

      <section className="device rounded-xl p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">היסטוריה</h2>
          {audit.length > 0 && (
            <button
              type="button"
              onClick={clearAudit}
              className="text-xs text-panel-600 transition hover:text-red-400"
            >
              ניקוי
            </button>
          )}
        </div>
        <p className="mt-1 text-xs text-panel-400">
          כל פעולה, אישור, דחייה וכישלון — לפי הסדר. זה מה שמאפשר לדעת מה קרה ולמה.
        </p>
        {audit.length === 0 ? (
          <p className="mt-3 text-xs text-panel-600">עדיין לא קרה כלום.</p>
        ) : (
          <ul className="mt-3 space-y-1.5">
            {audit.slice(0, 40).map((entry) => (
              <li key={entry.id} className="flex gap-2 text-xs">
                <span className="shrink-0 font-mono text-panel-600">
                  {new Date(entry.at).toLocaleTimeString('he-IL', {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
                <span
                  className={
                    entry.kind === 'error'
                      ? 'text-red-300'
                      : entry.kind === 'warning'
                        ? 'text-amber-300'
                        : entry.kind === 'action'
                          ? 'text-signal-300'
                          : 'text-panel-400'
                  }
                >
                  {entry.message}
                  {entry.detail && <span className="block text-panel-600">{entry.detail}</span>}
                </span>
              </li>
            ))}
          </ul>
        )}
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
