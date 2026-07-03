import type { ActionStatus, Eligibility } from '../types'

export const STATUS_LABELS: Record<ActionStatus, string> = {
  not_started: 'לא התחלתי',
  in_progress: 'בתהליך',
  submitted: 'הגשתי',
  need_docs: 'ביקשו עוד מסמכים',
  approved: 'אושר',
  rejected: 'נדחה',
}

const STATUS_STYLES: Record<ActionStatus, string> = {
  not_started: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-amber-100 text-amber-800',
  submitted: 'bg-blue-100 text-blue-800',
  need_docs: 'bg-orange-100 text-orange-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
}

export function StatusBadge({ status }: { status: ActionStatus }) {
  return (
    <span className={`rounded-full px-3 py-1 text-xs font-medium ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}

export function EligibilityBadge({ eligibility }: { eligibility: Eligibility }) {
  if (eligibility === 'eligible') {
    return (
      <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-800">
        נראה שמגיע לך
      </span>
    )
  }
  return (
    <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800">
      ייתכן שמגיע — כדאי לבדוק
    </span>
  )
}
