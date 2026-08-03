import { describe, expect, it } from 'vitest'
import {
  IDLE_DAYS_FOR_RETIRE,
  MAX_USAGE_EVENTS,
  MIN_EVENTS_FOR_PATTERN,
  appendUsage,
  dayPartOf,
  matchTool,
  suggestionsFor,
  summarize,
  type UsageEvent,
} from '../engine/usage'
import { normalizeSpec } from '../engine/specSchema'
import type { ToolSpec } from '../types'

/**
 * מה שנבדק כאן הוא לא "האם נמצא דפוס" אלא **מתי מותר לטעון שנמצא דפוס**.
 * מערכת שמכריזה על הרגל אחרי שלוש פתיחות תטעה בביטחון מלא ביום הראשון,
 * וזה בדיוק מה שגורם לאדם להפסיק להאמין להצעות שלה.
 */

const NOW = new Date('2026-08-03T12:00:00')

function tool(partial: Partial<ToolSpec> & { name: string }): ToolSpec {
  return normalizeSpec(
    {
      tagline: 'תיאור',
      icon: '🧪',
      systemPrompt: 's',
      fields: [{ id: 'input', label: 'קלט', type: 'longtext' }],
      controls: [],
      actions: [{ id: 'a', label: 'פעולה', capability: 'extract.items', prompt: 'p', output: 'both' }],
      collections: [{ id: 'items', label: 'רשימה', itemLabel: 'פריט', statuses: ['פתוח'] }],
      ...partial,
    },
    { id: partial.id ?? `tool_${partial.name}`, createdAt: partial.createdAt ?? NOW.toISOString() },
  )
}

/** אירוע פתיחה לפני N ימים בשעה נתונה */
function open(toolId: string, daysAgo: number, hour: number): UsageEvent {
  const date = new Date(NOW)
  date.setDate(date.getDate() - daysAgo)
  date.setHours(hour, 0, 0, 0)
  return { at: date.toISOString(), toolId, kind: 'open' }
}

describe('חלקי היום', () => {
  it('כל שעה נופלת בדיוק לחלק אחד, כולל מעבר חצות', () => {
    for (let hour = 0; hour < 24; hour++) {
      const date = new Date(NOW)
      date.setHours(hour)
      expect(dayPartOf(date)).toBeDefined()
    }
    const midnight = new Date(NOW)
    midnight.setHours(1)
    expect(dayPartOf(midnight).id).toBe('night')
  })
})

describe('היומן עצמו', () => {
  it('חדש נכנס ראשון והישן נופל מהסוף', () => {
    let log: UsageEvent[] = []
    for (let i = 0; i < MAX_USAGE_EVENTS + 20; i++) {
      log = appendUsage(log, { at: new Date(NOW.getTime() + i).toISOString(), toolId: 't', kind: 'open' })
    }
    expect(log).toHaveLength(MAX_USAGE_EVENTS)
  })

  it('לא קורס על חותמת זמן פגומה', () => {
    const usage = summarize([{ at: 'לא תאריך', toolId: 't', kind: 'open' }], 't', NOW)
    expect(usage.total).toBe(1)
    expect(usage.lastAt).toBeNull()
    expect(usage.habit).toBeNull()
  })
})

describe('דפוס נטען רק כשיש ראיות', () => {
  it(`פחות מ-${MIN_EVENTS_FOR_PATTERN} פתיחות אינן הרגל`, () => {
    const log = Array.from({ length: MIN_EVENTS_FOR_PATTERN - 1 }, (_, i) => open('t', i, 7))
    expect(summarize(log, 't', NOW).habit).toBeNull()
  })

  it('פתיחות עקביות בבוקר נטענות כהרגל', () => {
    const log = Array.from({ length: 8 }, (_, i) => open('t', i, 7))
    const habit = summarize(log, 't', NOW).habit
    expect(habit?.part.id).toBe('morning')
    expect(habit?.share).toBe(1)
  })

  it('שימוש מפוזר על פני היום אינו הרגל גם כשיש הרבה ממנו', () => {
    const hours = [7, 13, 19, 8, 14, 20, 9, 15, 21]
    const log = hours.map((hour, i) => open('t', i, hour))
    expect(summarize(log, 't', NOW).habit).toBeNull()
  })

  it('הרצות והוספות פריטים לא מנפחות את הדפוס — רק פתיחות', () => {
    const log: UsageEvent[] = [
      ...Array.from({ length: 3 }, (_, i) => open('t', i, 7)),
      ...Array.from({ length: 20 }, (_, i) => ({
        at: new Date(NOW.getTime() - i * 1000).toISOString(),
        toolId: 't',
        kind: 'run' as const,
      })),
    ]
    expect(summarize(log, 't', NOW).habit).toBeNull()
  })
})

describe('הצעות', () => {
  it('כלי שנמצא בשימוש קבוע בבוקר מקבל הצעת קידום עם הראיה', () => {
    const spec = tool({ name: 'יומן בוקר' })
    const log = Array.from({ length: 6 }, (_, i) => open(spec.id, i, 7))
    const [suggestion] = suggestionsFor([spec], log, NOW)

    expect(suggestion.kind).toBe('habit')
    expect(suggestion.text).toContain('בבוקר')
    expect(suggestion.evidence).toContain('100%')
  })

  it(`כלי שלא נגעו בו ${IDLE_DAYS_FOR_RETIRE} ימים מוצע לארכוב`, () => {
    const spec = tool({ name: 'נשכח' })
    const log = [open(spec.id, IDLE_DAYS_FOR_RETIRE + 3, 10)]
    const suggestion = suggestionsFor([spec], log, NOW).find((s) => s.kind === 'retire')

    expect(suggestion).toBeDefined()
    expect(suggestion?.text).toContain('לארכב')
  })

  it('כלי חדש שנוצר היום לא מוצע לארכוב', () => {
    const spec = tool({ name: 'טרי' })
    expect(suggestionsFor([spec], [], NOW).some((s) => s.kind === 'retire')).toBe(false)
  })

  it('כלי שנוצר לפני חודש ומעולם לא נפתח כן מוצע לארכוב', () => {
    const old = new Date(NOW)
    old.setDate(old.getDate() - 30)
    const spec = tool({ name: 'לא נפתח', createdAt: old.toISOString() })
    const suggestion = suggestionsFor([spec], [], NOW).find((s) => s.kind === 'retire')

    expect(suggestion?.evidence).toContain('לא נפתח מאז שנוצר')
  })

  it('כלי בשימוש יומיומי לא מוצע לארכוב', () => {
    const spec = tool({ name: 'פעיל' })
    const log = Array.from({ length: 10 }, (_, i) => open(spec.id, i, 9))
    expect(suggestionsFor([spec], log, NOW).some((s) => s.kind === 'retire')).toBe(false)
  })
})

describe('התאמה בין "מה אני צריך" לכלי קיים', () => {
  const tools = [
    tool({
      name: 'קונסולת הערות מיקס',
      tagline: 'הערות מלקוח לרשימת תיקונים לפי זמן',
      collections: [{ id: 'items', label: 'תיקוני מיקס', itemLabel: 'תיקון', statuses: ['פתוח'] }],
    }),
    tool({
      name: 'מעקב לידים',
      tagline: 'לקוחות פוטנציאליים והצעות מחיר',
      collections: [{ id: 'items', label: 'לידים', itemLabel: 'ליד', statuses: ['פתוח'] }],
    }),
  ]

  it('פנייה שמתארת כלי קיים מוצאת אותו', () => {
    expect(matchTool('לפרק הערות של לקוח למיקס', tools)?.name).toBe('קונסולת הערות מיקס')
    expect(matchTool('לעקוב אחרי לידים', tools)?.name).toBe('מעקב לידים')
  })

  it('פנייה לנושא אחר לגמרי לא מתאימה בכוח', () => {
    expect(matchTool('לתכנן טיול לצפון', tools)).toBeNull()
  })

  it('מילת קישור אחת לא מספיקה כדי לפתוח כלי', () => {
    // "אני צריך את זה עכשיו" — אין בו שום תוכן, וכלי לא אמור להיפתח
    expect(matchTool('אני צריך את זה עכשיו', tools)).toBeNull()
  })

  it('בלי כלים בכלל מחזיר null ולא נופל', () => {
    expect(matchTool('משהו', [])).toBeNull()
  })
})
