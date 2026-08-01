import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { makeItem, resolveControlValues, useApp } from '../store/AppContext'
import { FieldInput } from '../components/FieldInput'
import { ControlWidget } from '../components/ControlWidget'
import { ItemBoard } from '../components/ItemBoard'
import { ApprovalQueue } from '../components/ApprovalQueue'
import { PermissionsPanel } from '../components/PermissionsPanel'
import { getCapability } from '../engine/capabilities'
import { runActionLocally } from '../engine/localActions'
import { describeApiError, renderPrompt, runActionWithClaude } from '../engine/claude'
import { draftEventLocally, draftEventWithClaude, formatWhen } from '../engine/scheduling'
import { findDuplicate, isConnected } from '../engine/googleCalendar'
import { newId, normalizeSpec } from '../engine/specSchema'
import type { CollectionItem, SpecAction } from '../types'

export default function Console() {
  const { toolId = '' } = useParams()
  const {
    tools,
    engine,
    settings,
    connection,
    getState,
    setFieldValue,
    setControlValue,
    addItems,
    updateItem,
    deleteItem,
    clearItems,
    addLog,
    saveTool,
    queueAction,
    record,
  } = useApp()

  const spec = tools.find((t) => t.id === toolId)
  const state = getState(toolId)

  const [output, setOutput] = useState('')
  const [error, setError] = useState('')
  const [running, setRunning] = useState<string | null>(null)
  const [specDraft, setSpecDraft] = useState('')
  const [specError, setSpecError] = useState('')
  const [scheduling, setScheduling] = useState<string | null>(null)

  const controlValues = useMemo(
    () => (spec ? resolveControlValues(spec, state.controlValues) : {}),
    [spec, state.controlValues],
  )

  if (!spec) {
    return (
      <div className="device rounded-xl p-6 text-center">
        <p className="text-sm text-panel-400">הכלי הזה לא קיים (או נמחק).</p>
        <Link to="/" className="mt-3 inline-block text-sm text-signal-300">
          חזרה לכלים שלי
        </Link>
      </div>
    )
  }

  const run = async (action: SpecAction) => {
    const missing = spec.fields.filter((f) => f.required && !(state.fieldValues[f.id] ?? '').trim())
    if (missing.length > 0) {
      setError(`חסר: ${missing.map((f) => f.label).join(', ')}`)
      return
    }

    setRunning(action.id)
    setError('')

    try {
      const result =
        engine === 'claude'
          ? await runActionWithClaude(
              spec,
              action,
              state.fieldValues,
              controlValues,
              state.items,
              connection!,
            )
          : runActionLocally(spec, action, state.fieldValues, controlValues, state.items)

      const targetCollection =
        spec.collections.find((c) => c.id === action.target) ?? spec.collections[0]

      if (result.items.length > 0 && targetCollection) {
        addItems(
          spec.id,
          result.items.map((item) =>
            makeItem(targetCollection.id, item, targetCollection.statuses[0]),
          ),
        )
      }

      setOutput(result.text)
      addLog(spec.id, {
        id: newId('run'),
        toolId: spec.id,
        actionId: action.id,
        actionLabel: action.label,
        text: result.text,
        itemCount: result.items.length,
        engine: engine === 'claude' ? 'claude' : 'demo',
        createdAt: new Date().toISOString(),
      })
    } catch (err) {
      setError(describeApiError(err))
    } finally {
      setRunning(null)
    }
  }

  /**
   * "הוסף ליומן" לא מוסיף ליומן. הוא מכין טיוטה, בודק אם כבר קיים אירוע חופף,
   * ומכניס את הכול לתור האישורים. רק אישור מפורש שם שם משהו בפועל.
   */
  const schedule = async (item: CollectionItem) => {
    if (!spec) return
    setScheduling(item.id)
    setError('')
    try {
      const draft =
        engine === 'claude'
          ? await draftEventWithClaude(item, connection!).catch(() => draftEventLocally(item))
          : draftEventLocally(item)

      let duplicateOf: string | undefined
      if (!settings.simulate && isConnected()) {
        const existing = await findDuplicate(draft.summary, draft.start).catch(() => null)
        if (existing) duplicateOf = existing.id
      }

      queueAction({
        id: newId('act'),
        toolId: spec.id,
        itemId: item.id,
        type: 'calendar.createEvent',
        draft,
        status: 'pending',
        duplicateOf,
        createdAt: new Date().toISOString(),
      })
      record({
        kind: 'info',
        message: `הוכנה טיוטת אירוע: "${draft.summary}" ${formatWhen(draft.start)}`,
        detail: `ממתין לאישור · מקור: ${draft.source}`,
      })
    } catch (err) {
      setError(describeApiError(err))
    } finally {
      setScheduling(null)
    }
  }

  const openSpecEditor = () => {
    setSpecError('')
    setSpecDraft(
      JSON.stringify(
        {
          name: spec.name,
          tagline: spec.tagline,
          icon: spec.icon,
          systemPrompt: spec.systemPrompt,
          fields: spec.fields,
          controls: spec.controls,
          actions: spec.actions,
          collections: spec.collections,
        },
        null,
        2,
      ),
    )
  }

  const saveSpecDraft = () => {
    try {
      const parsed = JSON.parse(specDraft)
      saveTool(
        normalizeSpec(parsed, {
          id: spec.id,
          createdAt: spec.createdAt,
          sourceBrief: spec.sourceBrief,
          builtBy: spec.builtBy,
        }),
      )
      setSpecDraft('')
      setSpecError('')
    } catch (err) {
      setSpecError(err instanceof Error ? err.message : 'JSON לא תקין')
    }
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-3">
        <span className="text-3xl" aria-hidden>
          {spec.icon}
        </span>
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold text-white">{spec.name}</h1>
          <p className="text-xs text-panel-400">{spec.tagline}</p>
        </div>
        <span
          className={`ms-auto rounded-full border px-2.5 py-0.5 text-[11px] ${
            engine === 'claude'
              ? 'border-signal-500 text-signal-300'
              : 'border-amber-700/60 text-amber-300'
          }`}
        >
          {engine === 'claude' ? 'Claude' : 'הדגמה'}
        </span>
      </header>

      <section className="device rounded-xl p-4">
        <div className="space-y-3">
          {spec.fields.map((field) => (
            <FieldInput
              key={field.id}
              field={field}
              value={state.fieldValues[field.id] ?? ''}
              onChange={(value) => setFieldValue(spec.id, field.id, value)}
            />
          ))}
        </div>

        {spec.controls.length > 0 && (
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {spec.controls.map((control) => (
              <ControlWidget
                key={control.id}
                control={control}
                value={controlValues[control.id]}
                onChange={(value) => setControlValue(spec.id, control.id, value)}
              />
            ))}
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-2 border-t border-panel-800 pt-4">
          {spec.actions.map((action) => (
            <button
              key={action.id}
              type="button"
              disabled={running !== null}
              onClick={() => run(action)}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                action.primary
                  ? 'bg-signal-500 text-panel-950 hover:bg-signal-400'
                  : 'border border-panel-700 text-panel-200 hover:border-panel-600'
              }`}
            >
              <span aria-hidden>{action.icon} </span>
              {running === action.id ? 'מריץ…' : action.label}
            </button>
          ))}
        </div>

        {error && <p className="mt-3 text-sm text-red-300">{error}</p>}
      </section>

      {output && (
        <section className="device rounded-xl p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">פלט</h2>
            <button
              type="button"
              className="text-xs text-panel-400 transition hover:text-signal-300"
              onClick={() => navigator.clipboard?.writeText(output)}
            >
              העתקה
            </button>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-panel-200">{output}</p>
        </section>
      )}

      <ApprovalQueue toolId={spec.id} />

      {spec.collections.map((collection) => (
        <ItemBoard
          key={collection.id}
          collection={collection}
          items={state.items.filter((item) => item.collectionId === collection.id)}
          onUpdate={(itemId, patch) => updateItem(spec.id, itemId, patch)}
          onDelete={(itemId) => deleteItem(spec.id, itemId)}
          onSchedule={(item) => void schedule(item)}
          schedulingId={scheduling}
        />
      ))}

      <details className="rounded-xl border border-panel-800 bg-panel-900 p-4">
        <summary className="cursor-pointer text-sm text-panel-200">מתחת למכסה המנוע</summary>

        <div className="mt-4 space-y-4 text-xs text-panel-400">
          <div>
            <h3 className="mb-2 text-panel-200">מה הכלי הזה רשאי לעשות</h3>
            <PermissionsPanel spec={spec} />
          </div>

          <div>
            <h3 className="mb-1 text-panel-200">היכולות שמאחורי הכפתורים</h3>
            <ul className="space-y-1">
              {spec.actions.map((action) => {
                const capability = getCapability(action.capability)
                return (
                  <li key={action.id}>
                    <span className="text-panel-200">{action.label}</span>
                    {' → '}
                    <code className="text-signal-300">{action.capability}</code>
                    {capability && <span className="text-panel-600"> · {capability.label}</span>}
                  </li>
                )
              })}
            </ul>
          </div>

          <div>
            <h3 className="mb-1 text-panel-200">הפרומפט שיישלח בכל פעולה</h3>
            <ul className="space-y-2">
              {spec.actions.map((action) => (
                <li key={action.id} className="rounded-lg bg-panel-950 p-2">
                  <div className="text-panel-200">{action.label}</div>
                  <pre className="mt-1 overflow-x-auto whitespace-pre-wrap font-sans leading-relaxed">
                    {renderPrompt(action.prompt, spec, state.fieldValues, controlValues)}
                  </pre>
                </li>
              ))}
            </ul>
          </div>

          {state.log.length > 0 && (
            <div>
              <h3 className="mb-1 text-panel-200">הרצות אחרונות</h3>
              <ul className="space-y-1">
                {state.log.slice(0, 8).map((entry) => (
                  <li key={entry.id}>
                    {new Date(entry.createdAt).toLocaleString('he-IL')} · {entry.actionLabel} ·{' '}
                    {entry.itemCount} פריטים · {entry.engine === 'claude' ? 'Claude' : 'הדגמה'}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h3 className="mb-1 text-panel-200">עריכת המפרט</h3>
            {specDraft ? (
              <>
                <textarea
                  className="min-h-64 w-full resize-y rounded-lg border border-panel-700 bg-panel-950 p-2 font-mono text-[11px] text-panel-200 outline-none focus:border-signal-500"
                  dir="ltr"
                  value={specDraft}
                  onChange={(e) => setSpecDraft(e.target.value)}
                />
                {specError && <p className="mt-1 text-red-300">{specError}</p>}
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    onClick={saveSpecDraft}
                    className="rounded-lg bg-signal-500 px-3 py-1.5 text-xs font-semibold text-panel-950"
                  >
                    שמירה
                  </button>
                  <button
                    type="button"
                    onClick={() => setSpecDraft('')}
                    className="rounded-lg border border-panel-700 px-3 py-1.5 text-xs"
                  >
                    ביטול
                  </button>
                </div>
              </>
            ) : (
              <button
                type="button"
                onClick={openSpecEditor}
                className="rounded-lg border border-panel-700 px-3 py-1.5 text-xs text-panel-200 transition hover:border-signal-500"
              >
                פתיחת ה-JSON של הלוח
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={() => {
              if (confirm('לרוקן את כל הפריטים ברשימות של הכלי?')) clearItems(spec.id)
            }}
            className="text-panel-600 transition hover:text-red-400"
          >
            ריקון הרשימות
          </button>
        </div>
      </details>
    </div>
  )
}
