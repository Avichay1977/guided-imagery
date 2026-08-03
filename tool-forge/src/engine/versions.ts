import type { SpecAction, SpecCollection, SpecControl, SpecField, ToolSpec } from '../types'
import { getCapability } from './capabilities'

/**
 * גרסאות של כלי.
 *
 * כל שינוי במפרט שומר את הגרסה הקודמת, כך שאפשר לראות מה השתנה ולחזור אחורה.
 * זה נדרש כי המפרט ניתן לעריכה ידנית ולבנייה מחדש — בלי היסטוריה, טעות אחת
 * בעורך ה-JSON מוחקת כלי שעבד.
 */

export interface ToolVersion {
  id: string
  toolId: string
  /** מספר רץ, 1 הוא הגרסה הראשונה שנשמרה */
  version: number
  /** תצלום מלא של המפרט לפני השינוי */
  spec: ToolSpec
  at: string
  /** תיאור קריא של מה שהשתנה כדי להגיע לגרסה שאחריה */
  changes: string[]
}

/** האם שני מפרטים שונים בתוכן שמעניין אותנו (מתעלם מחותמות זמן). */
export function specsDiffer(a: ToolSpec, b: ToolSpec): boolean {
  return JSON.stringify(strip(a)) !== JSON.stringify(strip(b))
}

function strip(spec: ToolSpec) {
  const { id: _id, createdAt: _createdAt, updatedAt: _updatedAt, ...rest } = spec
  return rest
}

function byId<T extends { id: string }>(list: T[]): Map<string, T> {
  return new Map(list.map((item) => [item.id, item]))
}

function diffList<T extends { id: string; label: string }>(
  before: T[],
  after: T[],
  noun: string,
  describe: (item: T) => string = () => '',
): string[] {
  const changes: string[] = []
  const prev = byId(before)
  const next = byId(after)

  for (const [id, item] of next) {
    if (!prev.has(id)) changes.push(`נוסף ${noun}: ${item.label}${describe(item)}`)
  }
  for (const [id, item] of prev) {
    if (!next.has(id)) changes.push(`הוסר ${noun}: ${item.label}`)
  }
  for (const [id, item] of next) {
    const old = prev.get(id)
    if (!old) continue
    if (old.label !== item.label) changes.push(`שונה שם ${noun}: "${old.label}" ← "${item.label}"`)
    else if (JSON.stringify(old) !== JSON.stringify(item)) changes.push(`עודכן ${noun}: ${item.label}`)
  }
  return changes
}

/** תיאור קריא בעברית של ההבדל בין שני מפרטים. */
export function describeChanges(before: ToolSpec, after: ToolSpec): string[] {
  const changes: string[] = []

  if (before.name !== after.name) changes.push(`שם הכלי: "${before.name}" ← "${after.name}"`)
  if (before.tagline !== after.tagline) changes.push('עודכן תיאור הכלי')
  if (before.icon !== after.icon) changes.push(`אייקון: ${before.icon} ← ${after.icon}`)
  if (before.systemPrompt !== after.systemPrompt) changes.push('עודכן ההקשר הקבוע שנשלח למודל')

  changes.push(...diffList<SpecField>(before.fields, after.fields, 'שדה'))
  changes.push(...diffList<SpecControl>(before.controls, after.controls, 'בקרה'))
  changes.push(
    ...diffList<SpecAction>(before.actions, after.actions, 'כפתור', (action) => {
      const capability = getCapability(action.capability)
      return capability ? ` (${capability.label})` : ''
    }),
  )
  changes.push(...diffList<SpecCollection>(before.collections, after.collections, 'רשימה'))

  // שינוי ביכולת הוא החשוב ביותר — הוא משנה מה הכלי רשאי לעשות
  const prevActions = byId(before.actions)
  for (const action of after.actions) {
    const old = prevActions.get(action.id)
    if (old && old.capability !== action.capability) {
      changes.push(
        `יכולת של "${action.label}": ${getCapability(old.capability)?.label ?? old.capability} ← ${
          getCapability(action.capability)?.label ?? action.capability
        }`,
      )
    }
  }

  return changes.length > 0 ? changes : ['שינוי קל במפרט']
}

/** כמה גרסאות נשמרות לכל כלי לפני שהישנות נזרקות. */
export const MAX_VERSIONS_PER_TOOL = 20
