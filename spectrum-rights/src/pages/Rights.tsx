import { Link } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { evaluateRights } from '../engine/eligibility'
import { EligibilityBadge, StatusBadge } from '../components/StatusBadge'
import type { RightCategory } from '../types'

const CATEGORY_LABELS: Record<RightCategory, string> = {
  allowance: 'קצבאות וביטוח לאומי',
  health: 'בריאות וטיפולים',
  municipal: 'עירייה, מים וחשמל',
  tax: 'מס הכנסה',
  education: 'חינוך',
  transport: 'תחבורה',
}

export default function Rights() {
  const { profile, actions } = useApp()
  if (!profile) return null

  const evaluated = evaluateRights(profile)
  const categories = Array.from(new Set(evaluated.map((r) => r.right.category)))

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-calm-800">הזכויות שלך</h1>
      {categories.map((cat) => (
        <section key={cat}>
          <h2 className="mb-2 text-sm font-bold text-gray-400">{CATEGORY_LABELS[cat]}</h2>
          <div className="flex flex-col gap-3">
            {evaluated
              .filter((r) => r.right.category === cat)
              .map(({ right, eligibility }) => (
                <Link
                  key={right.id}
                  to={`/rights/${right.id}`}
                  className="rounded-2xl border border-calm-100 bg-white p-4 transition hover:border-calm-600"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold">{right.title}</span>
                    <StatusBadge status={actions[right.id] ?? 'not_started'} />
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-gray-500">
                    {right.shortDescription}
                  </p>
                  <div className="mt-2">
                    <EligibilityBadge eligibility={eligibility} />
                  </div>
                </Link>
              ))}
          </div>
        </section>
      ))}
    </div>
  )
}
