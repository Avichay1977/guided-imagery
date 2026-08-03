import type { SpecField } from '../types'

const baseInput =
  'w-full rounded-lg border border-panel-700 bg-panel-950 px-3 py-2 text-sm text-panel-200 outline-none placeholder:text-panel-600 focus:border-signal-500'

export function FieldInput({
  field,
  value,
  onChange,
}: {
  field: SpecField
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="block">
      <span className="mb-1 flex items-center gap-1 text-sm text-panel-200">
        {field.label}
        {field.required && <span className="text-signal-400">*</span>}
      </span>

      {field.type === 'longtext' && (
        <textarea
          className={`${baseInput} min-h-32 resize-y leading-relaxed`}
          placeholder={field.placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}

      {field.type === 'select' && (
        <select className={baseInput} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">בחרו…</option>
          {field.options?.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      )}

      {(field.type === 'text' || field.type === 'number' || field.type === 'date') && (
        <input
          className={baseInput}
          type={field.type === 'text' ? 'text' : field.type}
          placeholder={field.placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </label>
  )
}
