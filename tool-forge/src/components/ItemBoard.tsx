import { useState } from 'react'
import type { CollectionItem, SpecCollection } from '../types'

export function ItemBoard({
  collection,
  items,
  onUpdate,
  onDelete,
  onSchedule,
  schedulingId,
}: {
  collection: SpecCollection
  items: CollectionItem[]
  onUpdate: (itemId: string, patch: Partial<CollectionItem>) => void
  onDelete: (itemId: string) => void
  /** מכניס את הפריט לתור האישורים כאירוע יומן — לא מבצע דבר בעצמו */
  onSchedule?: (item: CollectionItem) => void
  schedulingId?: string | null
}) {
  const [filter, setFilter] = useState<string>('הכול')
  const [expanded, setExpanded] = useState<string | null>(null)

  const visible = filter === 'הכול' ? items : items.filter((item) => item.status === filter)

  return (
    <section className="device rounded-xl p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-white">{collection.label}</h2>
        <span className="rounded-full bg-panel-800 px-2 py-0.5 text-xs text-panel-400">
          {items.length}
        </span>
        <div className="ms-auto flex flex-wrap gap-1">
          {['הכול', ...collection.statuses].map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => setFilter(status)}
              className={`rounded-full px-2.5 py-0.5 text-[11px] transition ${
                filter === status
                  ? 'bg-panel-600 text-white'
                  : 'bg-panel-900 text-panel-400 hover:text-panel-200'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <p className="py-6 text-center text-sm text-panel-400">
          {items.length === 0
            ? (collection.emptyText ?? `אין ${collection.itemLabel} עדיין`)
            : `אין ${collection.itemLabel} בסטטוס "${filter}"`}
        </p>
      ) : (
        <ul className="space-y-2">
          {visible.map((item) => (
            <li key={item.id} className="rounded-lg border border-panel-700 bg-panel-950 p-3">
              <div className="flex items-start gap-2">
                {item.at && (
                  <span className="mt-0.5 shrink-0 rounded bg-panel-800 px-1.5 py-0.5 font-mono text-[11px] text-signal-300">
                    {item.at}
                  </span>
                )}
                <button
                  type="button"
                  className="flex-1 text-start text-sm text-panel-200"
                  onClick={() => setExpanded(expanded === item.id ? null : item.id)}
                >
                  {item.title}
                </button>
                <button
                  type="button"
                  aria-label="מחיקה"
                  className="shrink-0 text-panel-600 transition hover:text-red-400"
                  onClick={() => onDelete(item.id)}
                >
                  ✕
                </button>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                {collection.statuses.map((status) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => onUpdate(item.id, { status })}
                    className={`rounded-full px-2 py-0.5 text-[11px] transition ${
                      item.status === status
                        ? 'bg-signal-500 text-panel-950'
                        : 'bg-panel-800 text-panel-400 hover:text-panel-200'
                    }`}
                  >
                    {status}
                  </button>
                ))}
                {item.tags?.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-panel-700 px-2 py-0.5 text-[11px] text-panel-400"
                  >
                    {tag}
                  </span>
                ))}

                {onSchedule && (
                  <button
                    type="button"
                    disabled={schedulingId !== null && schedulingId !== undefined}
                    onClick={() => onSchedule(item)}
                    className="ms-auto rounded-full border border-panel-700 px-2 py-0.5 text-[11px] text-panel-200 transition hover:border-signal-500 hover:text-signal-300 disabled:opacity-40"
                  >
                    {schedulingId === item.id ? 'מכין…' : '📅 הוסף ליומן'}
                  </button>
                )}
              </div>

              {expanded === item.id && item.detail && (
                <p className="mt-2 whitespace-pre-wrap border-t border-panel-800 pt-2 text-xs leading-relaxed text-panel-400">
                  {item.detail}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
