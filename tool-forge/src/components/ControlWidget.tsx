import type { SpecControl } from '../types'

export function ControlWidget({
  control,
  value,
  onChange,
}: {
  control: SpecControl
  value: number | boolean | string
  onChange: (value: number | boolean | string) => void
}) {
  if (control.type === 'toggle') {
    const on = value === true
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-panel-700 bg-panel-900 px-3 py-2.5">
        <div>
          <div className="text-sm text-panel-200">{control.label}</div>
          {control.hint && <div className="text-xs text-panel-400">{control.hint}</div>}
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-label={control.label}
          onClick={() => onChange(!on)}
          className={`relative h-6 w-11 shrink-0 rounded-full transition ${
            on ? 'bg-signal-500' : 'bg-panel-700'
          }`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${
              on ? 'end-0.5' : 'end-[22px]'
            }`}
          />
        </button>
      </div>
    )
  }

  if (control.type === 'choice') {
    return (
      <div className="rounded-lg border border-panel-700 bg-panel-900 px-3 py-2.5">
        <div className="mb-2 text-sm text-panel-200">{control.label}</div>
        <div className="flex flex-wrap gap-1.5">
          {control.options?.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => onChange(option)}
              className={`rounded-full px-3 py-1 text-xs transition ${
                value === option
                  ? 'bg-signal-500 text-panel-950'
                  : 'bg-panel-800 text-panel-200 hover:bg-panel-700'
              }`}
            >
              {option}
            </button>
          ))}
        </div>
        {control.hint && <div className="mt-2 text-xs text-panel-400">{control.hint}</div>}
      </div>
    )
  }

  const min = control.min ?? 1
  const max = control.max ?? 5
  const numeric = typeof value === 'number' ? value : Number(value) || min

  return (
    <div className="rounded-lg border border-panel-700 bg-panel-900 px-3 py-2.5">
      <div className="mb-1 flex items-baseline justify-between">
        <span className="text-sm text-panel-200">{control.label}</span>
        <span className="font-mono text-sm text-signal-300">{numeric}</span>
      </div>
      <input
        type="range"
        className="w-full"
        min={min}
        max={max}
        step={control.step ?? 1}
        value={numeric}
        aria-label={control.label}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {/* ב-RTL הסליידר מתחיל מימין, ולכן ערך המינימום מופיע ראשון */}
      {(control.lowLabel || control.highLabel) && (
        <div className="flex justify-between text-[11px] text-panel-400">
          <span>{control.lowLabel}</span>
          <span>{control.highLabel}</span>
        </div>
      )}
      {control.hint && <div className="mt-1 text-xs text-panel-400">{control.hint}</div>}
    </div>
  )
}
