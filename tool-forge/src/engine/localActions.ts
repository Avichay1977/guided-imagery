import type { CollectionItem, SpecAction, ToolSpec } from '../types'

export interface ActionResult {
  text: string
  items: Array<{ title: string; detail?: string; status?: string; at?: string; tags?: string[] }>
}

const TIMECODE = /\b(\d{1,2}:\d{2}(?::\d{2})?)\b/
const HEBREW_DAY = /(יום\s+(?:ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)|מחר|מחרתיים|היום|בערב|בבוקר)/
const AMOUNT = /(\d[\d,.]*)\s*(?:₪|ש"ח|ש״ח|שח|שקל)/

/** הטקסט הארוך ביותר שהמשתמש הזין — זה כמעט תמיד "החומר הגולמי". */
function primaryInput(spec: ToolSpec, values: Record<string, string>): string {
  const longest = spec.fields
    .map((f) => values[f.id] ?? '')
    .reduce((a, b) => (b.length > a.length ? b : a), '')
  return longest.trim()
}

/** פירוק לגושים: שורות, ואז משפטים, ואז חיבורים. */
function segments(text: string): string[] {
  return text
    .split(/\n+/)
    .flatMap((line) => line.split(/(?<=[.!?;])\s+/))
    .flatMap((part) => part.split(/\s+(?:וגם|בנוסף|חוץ מזה)\s+/))
    .map((s) => s.replace(/^[-•*\d.)\s]+/, '').trim())
    .filter((s) => s.length > 2)
}

function shorten(text: string, max = 80): string {
  if (text.length <= max) return text
  const cut = text.slice(0, max)
  const lastSpace = cut.lastIndexOf(' ')
  return `${cut.slice(0, lastSpace > 30 ? lastSpace : max)}…`
}

function controlSummary(spec: ToolSpec, controls: Record<string, number | boolean | string>): string {
  return spec.controls
    .map((c) => {
      const value = controls[c.id] ?? c.default
      if (c.type === 'toggle') return `${c.label}: ${value ? 'דלוק' : 'כבוי'}`
      return `${c.label}: ${value}`
    })
    .join(' · ')
}

/**
 * מצב הדגמה — מריץ את הפעולה בלי AI.
 *
 * זו לא תחליף אמיתי ל-Claude: הוא מפרק את הקלט לפריטים לפי סימני פיסוק,
 * מחלץ חותמות זמן וסכומים, ומרכיב טקסט תגובה שלדי. המטרה שלו היא שהכלי
 * ירגיש חי לפני שמחברים מפתח API — לא שהוא יחליף את החשיבה.
 */
export function runActionLocally(
  spec: ToolSpec,
  action: SpecAction,
  values: Record<string, string>,
  controls: Record<string, number | boolean | string>,
  existing: CollectionItem[],
): ActionResult {
  const raw = primaryInput(spec, values)
  const collection = spec.collections.find((c) => c.id === action.target) ?? spec.collections[0]
  const parts = segments(raw)

  const items =
    action.output === 'text'
      ? []
      : parts.slice(0, 12).map((part) => {
          const time = part.match(TIMECODE)?.[1] ?? part.match(HEBREW_DAY)?.[1]
          const amount = part.match(AMOUNT)?.[0]
          return {
            title: shorten(part),
            detail: [
              part.length > 80 ? part : '',
              amount ? `סכום שזוהה: ${amount}` : '',
              'נוצר במצב הדגמה — חברו מפתח API כדי לקבל ניתוח אמיתי.',
            ]
              .filter(Boolean)
              .join('\n'),
            status: collection?.statuses[0],
            at: collection?.hasTimecode ? time : undefined,
            tags: ['הדגמה'],
          }
        })

  if (action.output === 'items') {
    return { text: '', items }
  }

  const openCount = existing.filter((i) => i.status === collection?.statuses[0]).length
  const lines: string[] = []
  lines.push(`▪︎ מצב הדגמה — ${action.label}`)
  lines.push('')
  if (spec.controls.length) lines.push(`הגדרות הלוח: ${controlSummary(spec, controls)}`)
  if (raw) {
    lines.push('')
    lines.push('מה שזוהה בקלט:')
    parts.slice(0, 8).forEach((p, i) => lines.push(`${i + 1}. ${shorten(p, 110)}`))
    if (parts.length > 8) lines.push(`…ועוד ${parts.length - 8} שורות`)
  } else {
    lines.push('')
    lines.push('לא הוזן קלט — מלאו שדה ונסו שוב.')
  }
  if (existing.length) {
    lines.push('')
    lines.push(
      `ברשימה כרגע ${existing.length} ${collection?.itemLabel ?? 'פריטים'}, מתוכם ${openCount} ב"${collection?.statuses[0]}".`,
    )
  }
  lines.push('')
  lines.push(
    'כדי שהכפתור הזה יבצע את מה שהוא באמת מבטיח — פתחו הגדרות והזינו מפתח API של Anthropic.',
  )

  return { text: lines.join('\n'), items }
}
