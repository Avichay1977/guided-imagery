import type { ToolSpec } from '../types'

/** תצוגה מקדימה של המפרט לפני שמירה — מה בדיוק ייבנה. */
export function SpecPreview({ spec }: { spec: ToolSpec }) {
  return (
    <div className="device rounded-xl p-5">
      <div className="flex items-center gap-3">
        <span className="text-3xl" aria-hidden>
          {spec.icon}
        </span>
        <div>
          <h2 className="font-semibold text-white">{spec.name}</h2>
          <p className="text-xs text-panel-400">{spec.tagline}</p>
        </div>
      </div>

      <dl className="mt-5 space-y-4 text-sm">
        <div>
          <dt className="mb-1 text-xs uppercase tracking-wide text-panel-600">קלטים</dt>
          <dd className="flex flex-wrap gap-1.5">
            {spec.fields.map((field) => (
              <span
                key={field.id}
                className="rounded-lg border border-panel-700 px-2 py-1 text-xs text-panel-200"
              >
                {field.label}
                <span className="text-panel-600"> · {field.type}</span>
              </span>
            ))}
          </dd>
        </div>

        {spec.controls.length > 0 && (
          <div>
            <dt className="mb-1 text-xs uppercase tracking-wide text-panel-600">בקרות</dt>
            <dd className="flex flex-wrap gap-1.5">
              {spec.controls.map((control) => (
                <span
                  key={control.id}
                  className="rounded-lg border border-panel-700 px-2 py-1 text-xs text-panel-200"
                >
                  {control.label}
                  <span className="text-panel-600"> · {control.type}</span>
                </span>
              ))}
            </dd>
          </div>
        )}

        <div>
          <dt className="mb-1 text-xs uppercase tracking-wide text-panel-600">פעולות</dt>
          <dd className="space-y-1.5">
            {spec.actions.map((action) => (
              <div key={action.id} className="rounded-lg bg-panel-950 px-3 py-2">
                <div className="text-xs text-panel-200">
                  <span aria-hidden>{action.icon} </span>
                  {action.label}
                  <span className="text-panel-600">
                    {' · '}
                    {action.output === 'text'
                      ? 'טקסט'
                      : action.output === 'items'
                        ? 'פריטים'
                        : 'טקסט + פריטים'}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-panel-600">
                  {action.prompt}
                </p>
              </div>
            ))}
          </dd>
        </div>

        <div>
          <dt className="mb-1 text-xs uppercase tracking-wide text-panel-600">זיכרון</dt>
          <dd className="flex flex-wrap gap-1.5">
            {spec.collections.map((collection) => (
              <span
                key={collection.id}
                className="rounded-lg border border-panel-700 px-2 py-1 text-xs text-panel-200"
              >
                {collection.label}
                <span className="text-panel-600"> · {collection.statuses.join(' / ')}</span>
              </span>
            ))}
          </dd>
        </div>
      </dl>
    </div>
  )
}
