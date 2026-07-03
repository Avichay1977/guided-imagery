import { Link } from 'react-router-dom'
import { LETTER_TEMPLATES } from '../data/letters'

export default function Letters() {
  return (
    <div className="flex flex-col gap-5">
      <header>
        <h1 className="text-2xl font-bold text-calm-800">מחולל המכתבים</h1>
        <p className="mt-1 text-sm text-gray-500">
          בוחרים מכתב, ממלאים פרטים פעם אחת — ומקבלים נוסח מוכן להעתקה או להורדה.
        </p>
      </header>
      <div className="flex flex-col gap-3">
        {LETTER_TEMPLATES.map((t) => (
          <Link
            key={t.id}
            to={`/letters/${t.id}`}
            className="rounded-2xl border border-calm-100 bg-white p-4 transition hover:border-calm-600"
          >
            <p className="font-bold">✉️ {t.title}</p>
            <p className="mt-1 text-sm text-gray-500">אל: {t.recipient}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
