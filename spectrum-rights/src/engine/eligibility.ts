import { RIGHTS } from '../data/rights'
import type { ActionStatus, Eligibility, Profile, Right } from '../types'

export interface EvaluatedRight {
  right: Right
  eligibility: Eligibility
}

export function evaluateRights(profile: Profile): EvaluatedRight[] {
  return RIGHTS.map((right) => ({ right, eligibility: right.eligibility(profile) }))
    .filter((r) => r.eligibility !== 'no')
    .sort((a, b) => {
      if (a.eligibility !== b.eligibility) return a.eligibility === 'eligible' ? -1 : 1
      return a.right.priority - b.right.priority
    })
}

const DONE: ActionStatus[] = ['submitted', 'approved']

export interface NextAction {
  right: Right
  eligibility: Eligibility
  status: ActionStatus
  missingDocs: string[]
  instruction: string
}

export function nextBestAction(
  profile: Profile,
  actions: Record<string, ActionStatus>,
  ownedDocs: string[],
): NextAction | null {
  const open = evaluateRights(profile).filter(
    (r) => !DONE.includes(actions[r.right.id] ?? 'not_started'),
  )
  if (open.length === 0) return null

  const { right, eligibility } = open[0]
  const status = actions[right.id] ?? 'not_started'
  const missingDocs = right.requiredDocuments.filter((d) => !ownedDocs.includes(d))

  let instruction: string
  if (status === 'rejected') {
    instruction = 'הבקשה נדחתה — הצעד הבא הוא להכין ערר. יש מחולל מכתב ערעור מוכן.'
  } else if (status === 'need_docs') {
    instruction =
      missingDocs.length > 0
        ? 'ביקשו מסמכים נוספים. הצעד הבא: להשלים את המסמך החסר הראשון ברשימה.'
        : 'ביקשו מסמכים נוספים. הצעד הבא: לשלוח את המסמכים עם מכתב השלמת מסמכים.'
  } else if (missingDocs.length > 0) {
    instruction = 'הצעד הבא: להשיג מסמך אחד — רק את הראשון ברשימת החסרים. זה מספיק להיום.'
  } else {
    instruction = 'כל המסמכים קיימים. הצעד הבא: להגיש את הבקשה לפי שלבי הפעולה.'
  }

  return { right, eligibility, status, missingDocs, instruction }
}
