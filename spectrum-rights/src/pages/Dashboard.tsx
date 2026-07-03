import { Link } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { evaluateRights, nextBestAction } from '../engine/eligibility'
import { EligibilityBadge, StatusBadge } from '../components/StatusBadge'
import { docLabel } from '../data/docTypes'

export default function Dashboard() {
  const { profile, actions, ownedDocTypes, resetProfile } = useApp()
  if (!profile) return null

  const evaluated = evaluateRights(profile)
  const next = nextBestAction(profile, actions, ownedDocTypes)
  const eligibleCount = evaluated.filter((r) => r.eligibility === 'eligible').length
  const maybeCount = evaluated.length - eligibleCount

  return (
    <div className="flex flex-col gap-5">
      <header className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-calm-800">מה מגיע לי עכשיו?</h1>
          <p className="mt-1 text-gray-500">
            {eligibleCount} זכויות שנראה שמגיעות לך{maybeCount > 0 && `, ועוד ${maybeCount} לבדיקה`}
          </p>
        </div>
        <button
          onClick={() => {
            if (confirm('לאפס את השאלון ולהתחיל מחדש? המסמכים שהעלית יישמרו.')) resetProfile()
          }}
          className="text-sm text-gray-400 underline"
        >
          עדכון פרטים
        </button>
      </header>

      <Link
        to="/focus"
        className="rounded-2xl bg-calm-700 p-4 text-center text-lg font-bold text-white shadow-md transition hover:bg-calm-800"
      >
        אני מוצף — תן לי רק את הצעד הבא 🧘
      </Link>

      {next ? (
        <section className="rounded-2xl border-2 border-calm-200 bg-white p-4 shadow-sm">
          <h2 className="text-sm font-medium text-calm-600">המשימה הבאה שלך</h2>
          <div className="mt-1 flex items-center justify-between gap-2">
            <h3 className="text-lg font-bold">{next.right.title}</h3>
            <StatusBadge status={next.status} />
          </div>
          <p className="mt-2 leading-relaxed text-gray-600">{next.instruction}</p>
          {next.missingDocs.length > 0 && (
            <p className="mt-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
              המסמך הראשון שחסר: <strong>{docLabel(next.missingDocs[0])}</strong>
            </p>
          )}
          <Link
            to={`/rights/${next.right.id}`}
            className="mt-3 block rounded-xl bg-calm-600 p-3 text-center font-bold text-white"
          >
            לפרטים ולביצוע
          </Link>
        </section>
      ) : (
        <section className="rounded-2xl bg-green-50 p-4 text-center text-green-800">
          כל הבקשות הפתוחות הוגשו או אושרו. כל הכבוד! 🎉
        </section>
      )}

      <section>
        <h2 className="mb-3 text-lg font-bold text-calm-800">כל הזכויות שלך</h2>
        <div className="flex flex-col gap-3">
          {evaluated.map(({ right, eligibility }) => (
            <Link
              key={right.id}
              to={`/rights/${right.id}`}
              className="rounded-2xl border border-calm-100 bg-white p-4 transition hover:border-calm-600"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold">{right.title}</span>
                <StatusBadge status={actions[right.id] ?? 'not_started'} />
              </div>
              <div className="mt-2">
                <EligibilityBadge eligibility={eligibility} />
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
