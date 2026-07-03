import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { getLetter } from '../data/letters'
import { loadLetterDetails, saveLetterDetails } from '../store/storage'
import type { LetterDetails } from '../types'

const FIELDS: { key: keyof LetterDetails; label: string }[] = [
  { key: 'fullName', label: 'שם מלא (של הפונה)' },
  { key: 'idNumber', label: 'תעודת זהות (של הפונה)' },
  { key: 'childName', label: 'שם הילד/ה או הזכאי/ת' },
  { key: 'childIdNumber', label: 'ת.ז. הילד/ה או הזכאי/ת' },
  { key: 'address', label: 'כתובת' },
  { key: 'phone', label: 'טלפון' },
]

export default function LetterEditor() {
  const { id } = useParams()
  const { profile } = useApp()
  const template = id ? getLetter(id) : undefined
  const [details, setDetails] = useState<LetterDetails>(() => loadLetterDetails())
  const [copied, setCopied] = useState(false)

  const letterText = useMemo(
    () => (template ? template.build(details, profile) : ''),
    [template, details, profile],
  )

  if (!template) {
    return (
      <p className="p-4 text-gray-500">
        המכתב לא נמצא. <Link to="/letters" className="underline">חזרה לרשימה</Link>
      </p>
    )
  }

  function update(key: keyof LetterDetails, value: string) {
    const next = { ...details, [key]: value }
    setDetails(next)
    saveLetterDetails(next)
  }

  async function copy() {
    await navigator.clipboard.writeText(letterText)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  function download() {
    const blob = new Blob([letterText], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${template!.title}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col gap-5">
      <Link to="/letters" className="text-gray-400">
        → כל המכתבים
      </Link>
      <header>
        <h1 className="text-2xl font-bold text-calm-800">{template.title}</h1>
        <p className="mt-1 text-sm text-gray-500">אל: {template.recipient}</p>
      </header>

      <section className="rounded-2xl border border-calm-100 bg-white p-4">
        <h2 className="font-bold text-calm-800">הפרטים שלך</h2>
        <p className="mt-1 text-xs text-gray-400">
          נשמר במכשיר בלבד, וממלא אוטומטית את כל המכתבים הבאים.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3">
          {FIELDS.map((f) => (
            <label key={f.key} className="text-sm text-gray-600">
              {f.label}
              <input
                type="text"
                value={details[f.key]}
                onChange={(e) => update(f.key, e.target.value)}
                className="mt-1 w-full rounded-xl border-2 border-calm-100 p-3 focus:border-calm-600 focus:outline-none"
              />
            </label>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-calm-100 bg-white p-4">
        <h2 className="font-bold text-calm-800">המכתב המוכן</h2>
        <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-xl bg-calm-50 p-4 font-sans text-sm leading-relaxed">
          {letterText}
        </pre>
        <p className="mt-2 text-xs text-gray-400">
          שדות בסוגריים מרובעים [כאלה] צריך להשלים ידנית לפני שליחה.
        </p>
        <div className="mt-3 flex gap-2">
          <button onClick={copy} className="flex-1 rounded-xl bg-calm-700 p-3 font-bold text-white">
            {copied ? '✓ הועתק!' : '📋 העתקה'}
          </button>
          <button
            onClick={download}
            className="flex-1 rounded-xl border-2 border-calm-600 p-3 font-bold text-calm-700"
          >
            ⬇️ הורדה כקובץ
          </button>
        </div>
      </section>
    </div>
  )
}
