import type { ToolSpec } from '../types'

/**
 * יומן שימוש — הבסיס שבלעדיו "מערכת שלומדת אותך" היא רק סיסמה.
 *
 * שתי החלטות שמכתיבות את הקובץ:
 *
 * 1. **הצעה, לא שינוי.** שום דבר כאן לא משנה את הממשק. הפונקציות מחזירות
 *    הצעות שהמשתמש מאשר או דוחה. זה ההבדל בין מערכת שמתפתחת איתך למערכת
 *    שמשנה לך דברים מתחת לידיים.
 * 2. **דפוס נטען רק כשיש מספיק ראיות.** שלוש פתיחות אינן הרגל. בלי הסף הזה
 *    המערכת הייתה "מגלה" דפוסים ביום הראשון וטועה בביטחון מלא — וזה בדיוק
 *    מה שגורם לאדם להפסיק להאמין להצעות.
 *
 * היומן מקומי לגמרי ואינו יוצא מהמכשיר.
 */

export type UsageKind = 'open' | 'run' | 'item'

export interface UsageEvent {
  at: string
  toolId: string
  kind: UsageKind
}

/** מספיק לכמה חודשים של שימוש אישי, וקטן מספיק ל-localStorage */
export const MAX_USAGE_EVENTS = 1000

/** מתחת לזה אין דפוס, יש צירוף מקרים */
export const MIN_EVENTS_FOR_PATTERN = 5

/** חלק מהפתיחות שחייב ליפול באותו חלק יום כדי לקרוא לזה הרגל */
export const PATTERN_DOMINANCE = 0.6

/** אחרי כמה ימים בלי שימוש מוצע לארכב */
export const IDLE_DAYS_FOR_RETIRE = 14

export interface DayPart {
  id: 'morning' | 'noon' | 'evening' | 'night'
  label: string
  from: number
  to: number
}

export const DAY_PARTS: DayPart[] = [
  { id: 'morning', label: 'בבוקר', from: 5, to: 11 },
  { id: 'noon', label: 'בצהריים', from: 11, to: 17 },
  { id: 'evening', label: 'בערב', from: 17, to: 23 },
  { id: 'night', label: 'בלילה', from: 23, to: 5 },
]

export function dayPartOf(date: Date): DayPart {
  const hour = date.getHours()
  return (
    DAY_PARTS.find((part) =>
      part.from < part.to ? hour >= part.from && hour < part.to : hour >= part.from || hour < part.to,
    ) ?? DAY_PARTS[3]
  )
}

export function appendUsage(log: UsageEvent[], event: UsageEvent): UsageEvent[] {
  return [event, ...log].slice(0, MAX_USAGE_EVENTS)
}

export interface ToolUsage {
  toolId: string
  /** כמה אירועים בסך הכול */
  total: number
  /** כמה פעמים הכלי נפתח — הבסיס לדפוס שעה */
  opens: number
  lastAt: string | null
  daysSinceLast: number | null
  /** חלק היום שבו הכלי נפתח לרוב, או null כשאין מספיק ראיות */
  habit: { part: DayPart; share: number } | null
}

function daysBetween(from: Date, to: Date): number {
  return Math.floor((to.getTime() - from.getTime()) / 86_400_000)
}

export function summarize(log: UsageEvent[], toolId: string, now = new Date()): ToolUsage {
  const mine = log.filter((event) => event.toolId === toolId)
  const opens = mine.filter((event) => event.kind === 'open')

  const times = mine
    .map((event) => new Date(event.at))
    .filter((date) => !Number.isNaN(date.getTime()))
    .sort((a, b) => b.getTime() - a.getTime())

  const last = times[0] ?? null

  // דפוס נבנה מפתיחות בלבד: הרצה או הוספת פריט קורות בתוך אותה פתיחה
  const counts = new Map<string, number>()
  for (const event of opens) {
    const date = new Date(event.at)
    if (Number.isNaN(date.getTime())) continue
    const part = dayPartOf(date)
    counts.set(part.id, (counts.get(part.id) ?? 0) + 1)
  }

  let habit: ToolUsage['habit'] = null
  const validOpens = [...counts.values()].reduce((sum, count) => sum + count, 0)
  if (validOpens >= MIN_EVENTS_FOR_PATTERN) {
    const [topId, topCount] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]
    const share = topCount / validOpens
    if (share >= PATTERN_DOMINANCE) {
      const part = DAY_PARTS.find((candidate) => candidate.id === topId)
      if (part) habit = { part, share }
    }
  }

  return {
    toolId,
    total: mine.length,
    opens: opens.length,
    lastAt: last ? last.toISOString() : null,
    daysSinceLast: last ? daysBetween(last, now) : null,
    habit,
  }
}

export interface Suggestion {
  id: string
  toolId: string
  kind: 'habit' | 'retire'
  /** מה מוצע, בגוף שני */
  text: string
  /** על סמך מה — כדי שאפשר יהיה לא להסכים */
  evidence: string
}

/**
 * ההצעות שהמערכת מרשה לעצמה להעלות. שתיים בלבד, ושתיהן הפיכות:
 * לספר על הרגל, ולהציע לארכב משהו שלא בשימוש.
 */
export function suggestionsFor(
  tools: ToolSpec[],
  log: UsageEvent[],
  now = new Date(),
): Suggestion[] {
  const suggestions: Suggestion[] = []

  for (const tool of tools) {
    const usage = summarize(log, tool.id, now)

    if (usage.habit) {
      suggestions.push({
        id: `habit_${tool.id}`,
        toolId: tool.id,
        kind: 'habit',
        text: `נראה שאתם פותחים את "${tool.name}" ${usage.habit.part.label}. שנקבע אותו ראשון?`,
        evidence: `${Math.round(usage.habit.share * 100)}% מתוך ${usage.opens} פתיחות`,
      })
    }

    // כלי שנוצר ולא נפתח מעולם נשפט לפי תאריך היצירה שלו
    const reference = usage.lastAt ?? tool.createdAt
    const idleDays = reference ? daysBetween(new Date(reference), now) : null
    if (idleDays !== null && idleDays >= IDLE_DAYS_FOR_RETIRE) {
      suggestions.push({
        id: `retire_${tool.id}`,
        toolId: tool.id,
        kind: 'retire',
        text: `לא השתמשתם ב"${tool.name}" ${idleDays} ימים. לארכב אותו?`,
        evidence: usage.lastAt ? 'לפי השימוש האחרון' : 'לא נפתח מאז שנוצר',
      })
    }
  }

  return suggestions
}

const STOP_WORDS = new Set([
  'אני',
  'צריך',
  'רוצה',
  'את',
  'של',
  'עם',
  'על',
  'לי',
  'זה',
  'עכשיו',
  'היום',
  'קצת',
  'שוב',
])

function words(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/["'׳״.,;:!?()\-–—]/g, ' ')
    .split(/\s+/)
    .filter((word) => word.length > 1 && !STOP_WORDS.has(word))
}

/**
 * התאמה בין "מה אני צריך עכשיו" לכלי קיים.
 *
 * מכוון להיות **שמרני**: עדיף לפתוח את מסך הבנייה מאשר לפתוח בביטחון את
 * הכלי הלא נכון. לכן נדרשות לפחות שתי מילים משותפות, או מילה אחת שמופיעה
 * בשם הכלי עצמו.
 */
export function matchTool(query: string, tools: ToolSpec[]): ToolSpec | null {
  const asked = words(query)
  if (asked.length === 0) return null

  let best: { tool: ToolSpec; score: number } | null = null

  for (const tool of tools) {
    const name = new Set(words(tool.name))
    const rest = new Set([
      ...words(tool.tagline),
      ...tool.fields.flatMap((field) => words(field.label)),
      ...tool.actions.flatMap((action) => words(action.label)),
      ...tool.collections.flatMap((collection) => words(collection.label)),
    ])

    let score = 0
    for (const word of new Set(asked)) {
      if (name.has(word)) score += 3
      else if (rest.has(word)) score += 1
    }

    if (score >= 2 && (!best || score > best.score)) best = { tool, score }
  }

  return best?.tool ?? null
}
