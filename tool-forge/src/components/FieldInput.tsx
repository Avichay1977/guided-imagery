import { useRef, useState } from 'react'
import { fileToDataUrl } from '../engine/images'
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
  const fileInput = useRef<HTMLInputElement>(null)
  const [imageError, setImageError] = useState('')

  const pickImage = async (file: File | undefined) => {
    if (!file) return
    setImageError('')
    try {
      onChange(await fileToDataUrl(file))
    } catch (error) {
      setImageError(error instanceof Error ? error.message : 'לא הצלחנו לקרוא את התמונה.')
    }
  }

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

      {field.type === 'image' && (
        <div className="space-y-2">
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => void pickImage(e.target.files?.[0])}
          />

          {value ? (
            <div className="rounded-lg border border-panel-700 bg-panel-950 p-2">
              <img src={value} alt={field.label} className="max-h-56 w-full rounded object-contain" />
              <div className="mt-2 flex gap-3">
                <button
                  type="button"
                  onClick={() => fileInput.current?.click()}
                  className="text-[11px] text-panel-400 transition hover:text-signal-300"
                >
                  החלפה
                </button>
                <button
                  type="button"
                  onClick={() => onChange('')}
                  className="text-[11px] text-panel-600 transition hover:text-red-400"
                >
                  הסרה
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              className="w-full rounded-lg border border-dashed border-panel-700 px-3 py-6 text-sm text-panel-400 transition hover:border-signal-500 hover:text-signal-300"
            >
              📷 צילום או בחירת תמונה
            </button>
          )}

          {imageError && <p className="text-xs text-red-400">{imageError}</p>}
        </div>
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
