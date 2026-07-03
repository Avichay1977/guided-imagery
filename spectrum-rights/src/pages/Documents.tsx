import { useRef, useState } from 'react'
import { useApp } from '../store/AppContext'
import { DOC_TYPES, docLabel } from '../data/docTypes'
import { evaluateRights } from '../engine/eligibility'

export default function Documents() {
  const { profile, docs, addDoc, removeDoc, ownedDocTypes } = useApp()
  const fileInput = useRef<HTMLInputElement>(null)
  const [pendingType, setPendingType] = useState<string>(DOC_TYPES[0].id)
  const [busy, setBusy] = useState(false)

  const neededDocs = profile
    ? Array.from(
        new Set(evaluateRights(profile).flatMap(({ right }) => right.requiredDocuments)),
      )
    : []
  const missingDocs = neededDocs.filter((d) => !ownedDocTypes.includes(d))

  async function onFilesSelected(files: FileList | null) {
    if (!files || files.length === 0) return
    setBusy(true)
    try {
      for (const file of Array.from(files)) {
        await addDoc({
          id: `${file.name}-${file.size}-${file.lastModified}`,
          name: file.name,
          docType: pendingType,
          mimeType: file.type,
          blob: file,
          addedAt: new Date().toISOString(),
        })
      }
    } finally {
      setBusy(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  function download(docId: string) {
    const doc = docs.find((d) => d.id === docId)
    if (!doc) return
    const url = URL.createObjectURL(doc.blob)
    const a = document.createElement('a')
    a.href = url
    a.download = doc.name
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-bold text-calm-800">תיק המסמכים</h1>
        <p className="mt-1 text-sm text-gray-500">
          המסמכים נשמרים רק במכשיר שלך (בדפדפן) — הם לא נשלחים לשום שרת.
        </p>
      </header>

      {missingDocs.length > 0 && (
        <section className="rounded-2xl bg-amber-50 p-4">
          <h2 className="font-bold text-amber-900">מסמכים שעוד חסרים לבקשות שלך:</h2>
          <ul className="mt-2 flex flex-col gap-1 text-sm text-amber-900">
            {missingDocs.map((d) => (
              <li key={d}>⬜ {docLabel(d)}</li>
            ))}
          </ul>
        </section>
      )}

      <section className="rounded-2xl border border-calm-100 bg-white p-4">
        <h2 className="font-bold text-calm-800">העלאת מסמך</h2>
        <label className="mt-3 block text-sm text-gray-600" htmlFor="doc-type">
          איזה סוג מסמך זה?
        </label>
        <select
          id="doc-type"
          value={pendingType}
          onChange={(e) => setPendingType(e.target.value)}
          className="mt-1 w-full rounded-xl border-2 border-calm-100 bg-white p-3"
        >
          {DOC_TYPES.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label}
            </option>
          ))}
        </select>
        <input
          ref={fileInput}
          type="file"
          accept=".pdf,image/*"
          multiple
          className="hidden"
          onChange={(e) => onFilesSelected(e.target.files)}
        />
        <button
          onClick={() => fileInput.current?.click()}
          disabled={busy}
          className="mt-3 w-full rounded-xl bg-calm-700 p-3 font-bold text-white disabled:opacity-50"
        >
          {busy ? 'שומר…' : '📎 בחירת קובץ (PDF או תמונה)'}
        </button>
      </section>

      <section>
        <h2 className="mb-2 font-bold text-calm-800">מסמכים שהעלית ({docs.length})</h2>
        {docs.length === 0 ? (
          <p className="rounded-2xl bg-calm-50 p-4 text-sm text-gray-500">
            עדיין אין מסמכים. אפשר לצלם עכשיו את האבחון — ולהעלות. אם יש יותר מקובץ אחד, אפשר
            להעלות את כולם.
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {docs.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center gap-3 rounded-2xl border border-calm-100 bg-white p-3"
              >
                <span className="text-2xl" aria-hidden="true">
                  {doc.mimeType.startsWith('image/') ? '🖼️' : '📄'}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{doc.name}</p>
                  <p className="text-xs text-gray-400">{docLabel(doc.docType)}</p>
                </div>
                <button onClick={() => download(doc.id)} className="text-sm text-calm-700 underline">
                  הורדה
                </button>
                <button
                  onClick={() => {
                    if (confirm(`למחוק את "${doc.name}"?`)) removeDoc(doc.id)
                  }}
                  className="text-sm text-red-400"
                  aria-label={`מחיקת ${doc.name}`}
                >
                  🗑️
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
