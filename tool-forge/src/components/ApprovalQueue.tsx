import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import type { PendingAction } from '../types'
import {
  DuplicateEventError,
  createEvent,
  deleteEvent,
  eventIdFor,
  isConnected,
} from '../engine/googleCalendar'
import { formatWhen, fromInputValue, toInputValue } from '../engine/scheduling'

/**
 * תור האישורים — הנקודה היחידה שבה משהו יוצא מהאפליקציה אל העולם.
 *
 * כל פעולה עוברת כאן: תצוגה מקדימה מלאה, מד ביטחון, מקור המידע, ואפשרות לתקן
 * את המועד לפני שמאשרים. אין נתיב עוקף — לחיצה על "הוסף ליומן" בלוח רק
 * מכניסה פריט לתור הזה.
 */
export function ApprovalQueue({ toolId }: { toolId: string }) {
  const { pending, updateAction, removeAction, settings, record } = useApp()
  const [busy, setBusy] = useState<string | null>(null)

  const queue = pending.filter((action) => action.toolId === toolId)
  if (queue.length === 0) return null

  const waiting = queue.filter((action) => action.status === 'pending')

  const edit = (action: PendingAction, patch: Partial<PendingAction['draft']>) => {
    updateAction(action.id, { draft: { ...action.draft, ...patch } })
  }

  const approve = async (action: PendingAction) => {
    setBusy(action.id)
    try {
      if (settings.simulate) {
        updateAction(action.id, { status: 'simulated', decidedAt: new Date().toISOString() })
        record({
          kind: 'action',
          message: `סימולציה: "${action.draft.summary}" ${formatWhen(action.draft.start)}`,
          detail: 'מצב סימולציה דלוק — לא נוצר אירוע ביומן.',
        })
        return
      }

      if (!isConnected()) {
        throw new Error('אין חיבור פעיל ליומן. התחברו בהגדרות ונסו שוב.')
      }

      const event = await createEvent({
        summary: action.draft.summary,
        description: [action.draft.description, `נוצר מ: ${action.draft.source}`]
          .filter(Boolean)
          .join('\n\n'),
        start: action.draft.start,
        end: action.draft.end,
        eventId: eventIdFor(action.itemId),
      })

      updateAction(action.id, {
        status: 'executed',
        eventId: event.id,
        eventLink: event.htmlLink,
        decidedAt: new Date().toISOString(),
        error: undefined,
      })
      record({
        kind: 'action',
        message: `נוצר אירוע ביומן: "${action.draft.summary}" ${formatWhen(action.draft.start)}`,
        detail: `מזהה אירוע ${event.id}`,
      })
    } catch (error) {
      const duplicate = error instanceof DuplicateEventError
      updateAction(action.id, {
        status: 'failed',
        error: error instanceof Error ? error.message : 'שגיאה לא ידועה',
        duplicateOf: duplicate ? (error as DuplicateEventError).eventId : undefined,
      })
      record({
        kind: duplicate ? 'warning' : 'error',
        message: duplicate
          ? `נמנעה יצירה כפולה: "${action.draft.summary}"`
          : `יצירת האירוע נכשלה: "${action.draft.summary}"`,
        detail: error instanceof Error ? error.message : undefined,
      })
    } finally {
      setBusy(null)
    }
  }

  const undo = async (action: PendingAction) => {
    if (!action.eventId) return
    setBusy(action.id)
    try {
      await deleteEvent(action.eventId)
      updateAction(action.id, { status: 'undone' })
      record({ kind: 'action', message: `בוטל אירוע: "${action.draft.summary}"` })
    } catch (error) {
      updateAction(action.id, {
        error: error instanceof Error ? error.message : 'הביטול נכשל',
      })
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="device rounded-xl p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-white">ממתין לאישור</h2>
        <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-300">
          {waiting.length}
        </span>
        <span
          className={`ms-auto rounded-full border px-2.5 py-0.5 text-[11px] ${
            settings.simulate
              ? 'border-amber-700/60 text-amber-300'
              : 'border-red-700/60 text-red-300'
          }`}
        >
          {settings.simulate ? 'מצב סימולציה — לא ייווצר אירוע אמיתי' : 'פעולות אמיתיות פעילות'}
        </span>
      </div>

      <ul className="space-y-3">
        {queue.map((action) => {
          const low = action.draft.confidence < 0.5
          const decided = action.status !== 'pending'

          return (
            <li key={action.id} className="rounded-lg border border-panel-700 bg-panel-950 p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-panel-200">📅 הוספה ליומן</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] ${
                    action.status === 'executed'
                      ? 'bg-signal-500 text-panel-950'
                      : action.status === 'simulated'
                        ? 'bg-amber-500/20 text-amber-300'
                        : action.status === 'failed'
                          ? 'bg-red-500/20 text-red-300'
                          : action.status === 'rejected' || action.status === 'undone'
                            ? 'bg-panel-800 text-panel-400'
                            : 'bg-panel-700 text-panel-200'
                  }`}
                >
                  {
                    {
                      pending: 'ממתין',
                      simulated: 'סימולציה',
                      executed: 'נוצר ביומן',
                      rejected: 'נדחה',
                      failed: 'נכשל',
                      undone: 'בוטל',
                    }[action.status]
                  }
                </span>

                <span className="ms-auto flex items-center gap-1.5 text-[11px] text-panel-400">
                  ביטחון
                  <span className="h-1.5 w-16 overflow-hidden rounded-full bg-panel-800">
                    <span
                      className={`block h-full ${low ? 'bg-amber-400' : 'bg-signal-400'}`}
                      style={{ width: `${Math.round(action.draft.confidence * 100)}%` }}
                    />
                  </span>
                  {Math.round(action.draft.confidence * 100)}%
                </span>
              </div>

              {decided ? (
                <div className="mt-2 text-sm text-panel-200">
                  {action.draft.summary}
                  <span className="text-panel-400"> · {formatWhen(action.draft.start)}</span>
                </div>
              ) : (
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  <label className="sm:col-span-2 block">
                    <span className="mb-1 block text-[11px] text-panel-400">כותרת האירוע</span>
                    <input
                      className="w-full rounded-lg border border-panel-700 bg-panel-900 px-2 py-1.5 text-sm text-panel-200 outline-none focus:border-signal-500"
                      value={action.draft.summary}
                      onChange={(e) => edit(action, { summary: e.target.value })}
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-[11px] text-panel-400">התחלה</span>
                    <input
                      type="datetime-local"
                      dir="ltr"
                      className="w-full rounded-lg border border-panel-700 bg-panel-900 px-2 py-1.5 text-sm text-panel-200 outline-none focus:border-signal-500"
                      value={toInputValue(action.draft.start)}
                      onChange={(e) => edit(action, { start: fromInputValue(e.target.value) })}
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-[11px] text-panel-400">סיום</span>
                    <input
                      type="datetime-local"
                      dir="ltr"
                      className="w-full rounded-lg border border-panel-700 bg-panel-900 px-2 py-1.5 text-sm text-panel-200 outline-none focus:border-signal-500"
                      value={toInputValue(action.draft.end)}
                      onChange={(e) => edit(action, { end: fromInputValue(e.target.value) })}
                    />
                  </label>
                </div>
              )}

              <p className="mt-2 text-[11px] text-panel-600">מקור: {action.draft.source}</p>

              {action.draft.missing && action.status === 'pending' && (
                <p className="mt-2 rounded-lg border border-amber-700/50 bg-amber-950/30 px-2 py-1.5 text-[11px] text-amber-200">
                  לא הצלחנו לקבוע מהטקסט: {action.draft.missing}. בדקו את המועד לפני אישור.
                </p>
              )}

              {action.duplicateOf && (
                <p className="mt-2 rounded-lg border border-amber-700/50 bg-amber-950/30 px-2 py-1.5 text-[11px] text-amber-200">
                  כבר קיים אירוע שנוצר מהפריט הזה — לא נוצר אירוע נוסף.
                </p>
              )}

              {action.error && !action.duplicateOf && (
                <p className="mt-2 text-[11px] text-red-300">{action.error}</p>
              )}

              <div className="mt-3 flex flex-wrap items-center gap-2">
                {action.status === 'pending' && (
                  <>
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => void approve(action)}
                      className="rounded-lg bg-signal-500 px-3 py-1.5 text-xs font-semibold text-panel-950 transition hover:bg-signal-400 disabled:opacity-40"
                    >
                      {busy === action.id
                        ? 'מבצע…'
                        : settings.simulate
                          ? 'אישור (סימולציה)'
                          : 'אישור והוספה ליומן'}
                    </button>
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => {
                        updateAction(action.id, {
                          status: 'rejected',
                          decidedAt: new Date().toISOString(),
                        })
                        record({ kind: 'info', message: `נדחתה פעולה: "${action.draft.summary}"` })
                      }}
                      className="rounded-lg border border-panel-700 px-3 py-1.5 text-xs text-panel-200"
                    >
                      דחייה
                    </button>
                  </>
                )}

                {action.status === 'executed' && (
                  <>
                    {action.eventLink && (
                      <a
                        href={action.eventLink}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-signal-300 hover:text-signal-400"
                      >
                        פתיחה ביומן ↗
                      </a>
                    )}
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => void undo(action)}
                      className="rounded-lg border border-panel-700 px-3 py-1.5 text-xs text-panel-200"
                    >
                      {busy === action.id ? 'מבטל…' : 'ביטול האירוע'}
                    </button>
                  </>
                )}

                {action.status === 'failed' && (
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() =>
                      updateAction(action.id, {
                        status: 'pending',
                        error: undefined,
                        duplicateOf: undefined,
                      })
                    }
                    className="rounded-lg border border-panel-700 px-3 py-1.5 text-xs text-panel-200"
                  >
                    נסה שוב
                  </button>
                )}

                <button
                  type="button"
                  className="ms-auto text-[11px] text-panel-600 transition hover:text-red-400"
                  onClick={() => removeAction(action.id)}
                >
                  הסרה מהתור
                </button>
              </div>
            </li>
          )
        })}
      </ul>

      {!settings.simulate && !isConnected() && (
        <p className="mt-3 text-[11px] text-panel-400">
          אין חיבור פעיל ליומן.{' '}
          <Link to="/settings" className="text-signal-300">
            התחברות בהגדרות
          </Link>
        </p>
      )}
    </section>
  )
}
