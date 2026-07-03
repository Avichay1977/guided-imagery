import { Link, useNavigate, useParams } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { getRight } from '../data/rights'
import { docLabel } from '../data/docTypes'
import { STATUS_LABELS, EligibilityBadge } from '../components/StatusBadge'
import type { ActionStatus } from '../types'

const STATUS_ORDER: ActionStatus[] = [
  'not_started',
  'in_progress',
  'submitted',
  'need_docs',
  'approved',
  'rejected',
]

export default function RightDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { profile, actions, setActionStatus, ownedDocTypes } = useApp()
  const right = id ? getRight(id) : undefined

  if (!profile || !right) {
    return (
      <p className="p-4 text-gray-500">
        הזכות לא נמצאה. <Link to="/rights" className="underline">חזרה לרשימה</Link>
      </p>
    )
  }

  const eligibility = right.eligibility(profile)
  const status = actions[right.id] ?? 'not_started'
  const missing = right.requiredDocuments.filter((d) => !ownedDocTypes.includes(d))

  return (
    <div className="flex flex-col gap-5">
      <button onClick={() => navigate(-1)} className="self-start text-gray-400">
        → חזרה
      </button>

      <header>
        <h1 className="text-2xl font-bold text-calm-800">{right.title}</h1>
        <div className="mt-2">
          {eligibility === 'no' ? (
            <span className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-500">
              לפי הפרטים שמילאת — כנראה לא רלוונטי כרגע
            </span>
          ) : (
            <EligibilityBadge eligibility={eligibility} />
          )}
        </div>
        <p className="mt-3 leading-relaxed text-gray-600">{right.shortDescription}</p>
        {right.eligibilityNote && (
          <p className="mt-2 rounded-xl bg-calm-50 p-3 text-sm text-calm-800">
            💡 {right.eligibilityNote}
          </p>
        )}
      </header>

      <section className="rounded-2xl border border-calm-100 bg-white p-4">
        <h2 className="font-bold text-calm-800">הגשתי — מה עכשיו? עדכון סטטוס:</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {STATUS_ORDER.map((s) => (
            <button
              key={s}
              onClick={() => setActionStatus(right.id, s)}
              className={`rounded-full px-4 py-2 text-sm transition ${
                status === s
                  ? 'bg-calm-700 font-bold text-white'
                  : 'bg-calm-50 text-gray-600 hover:bg-calm-100'
              }`}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>
        {status === 'rejected' && (
          <div className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-900">
            נדחית? זה קורה הרבה, וערר משתלם ברוב המקרים. יש להגיש בתוך 90 יום.{' '}
            <Link to="/letters/appeal" className="font-bold underline">
              להכנת מכתב ערעור
            </Link>
          </div>
        )}
        {status === 'need_docs' && (
          <div className="mt-3 rounded-xl bg-orange-50 p-3 text-sm text-orange-900">
            ביקשו מסמכים נוספים? השלימו אותם ושלחו עם{' '}
            <Link to="/letters/ni_docs" className="font-bold underline">
              מכתב השלמת מסמכים
            </Link>
          </div>
        )}
      </section>

      <section className="rounded-2xl border border-calm-100 bg-white p-4">
        <h2 className="font-bold text-calm-800">מסמכים נדרשים</h2>
        <ul className="mt-3 flex flex-col gap-2">
          {right.requiredDocuments.map((doc) => {
            const owned = ownedDocTypes.includes(doc)
            return (
              <li
                key={doc}
                className={`flex items-center gap-2 rounded-xl p-3 text-sm ${
                  owned ? 'bg-green-50 text-green-900' : 'bg-amber-50 text-amber-900'
                }`}
              >
                <span aria-hidden="true">{owned ? '✅' : '⬜'}</span>
                {docLabel(doc)}
                {!owned && <span className="mr-auto text-xs font-medium">חסר</span>}
              </li>
            )
          })}
        </ul>
        {missing.length > 0 && (
          <Link to="/documents" className="mt-3 block text-sm font-medium text-calm-700 underline">
            העלאת מסמכים לתיק המסמכים
          </Link>
        )}
      </section>

      <section className="rounded-2xl border border-calm-100 bg-white p-4">
        <h2 className="font-bold text-calm-800">שלבי הפעולה</h2>
        <ol className="mt-3 flex flex-col gap-3">
          {right.steps.map((step, i) => (
            <li key={i} className="flex gap-3 text-sm leading-relaxed text-gray-700">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-calm-100 text-xs font-bold text-calm-700">
                {i + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
        <div className="mt-4 flex flex-col gap-2">
          {right.formUrl && (
            <a
              href={right.formUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-xl bg-calm-700 p-3 text-center font-bold text-white"
            >
              לטופס באתר הרשמי ↗
            </a>
          )}
          {right.letterTemplateId && (
            <Link
              to={`/letters/${right.letterTemplateId}`}
              className="rounded-xl border-2 border-calm-600 p-3 text-center font-bold text-calm-700"
            >
              ✉️ הכנת מכתב מוכן לשליחה
            </Link>
          )}
        </div>
      </section>

      <section className="rounded-2xl bg-calm-50 p-4 text-sm text-gray-600">
        <h2 className="font-bold text-calm-800">מקור המידע</h2>
        <p className="mt-2">
          <a href={right.source.url} target="_blank" rel="noreferrer" className="font-medium text-calm-700 underline">
            {right.source.name} ↗
          </a>
        </p>
        <p className="mt-1 text-xs text-gray-400">
          נבדק לאחרונה: {right.source.lastChecked} · רמת ביטחון:{' '}
          {right.source.confidence === 'high' ? 'גבוהה' : 'בינונית — מומלץ לאמת מול הגורם הרשמי'}
        </p>
      </section>
    </div>
  )
}
