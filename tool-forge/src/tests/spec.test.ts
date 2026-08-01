import { describe, expect, it } from 'vitest'
import { normalizeSpec, permissionsFor } from '../engine/specSchema'
import { inferCapability } from '../engine/capabilities'
import { buildSpecLocally, pickPattern } from '../engine/localBuilder'
import { PATTERN_CASES } from './corpus'

/**
 * הבדיקות שמגנות על הכלל המרכזי: מפרט שמגיע ממקור לא בטוח לא יכול להרחיב
 * את מה שהאפליקציה יודעת לעשות.
 */

const base = {
  name: 'כלי',
  tagline: 'תיאור',
  icon: '🎛️',
  systemPrompt: 'הקשר',
  fields: [{ id: 'input', label: 'קלט', type: 'longtext', required: true }],
  controls: [],
  collections: [{ id: 'items', label: 'רשימה', itemLabel: 'פריט', statuses: ['פתוח', 'בוצע'] }],
}

describe('normalizeSpec — אכיפת קטלוג היכולות', () => {
  it('דוחה פעולה שמבקשת יכולת שלא קיימת בקטלוג', () => {
    const spec = normalizeSpec({
      ...base,
      actions: [
        { id: 'ok', label: 'סדר', capability: 'extract.items', prompt: 'x', output: 'both' },
        { id: 'evil', label: 'שלח מייל', capability: 'email.send', prompt: 'y', output: 'text' },
      ],
    })

    expect(spec.actions.map((a) => a.id)).toEqual(['ok'])
  })

  it('לא מתרגם יכולת לא מוכרת ליכולת הקרובה אליה', () => {
    const spec = normalizeSpec({
      ...base,
      actions: [{ id: 'x', label: 'משהו', capability: 'extract.itemz', prompt: 'p', output: 'both' }],
    })

    // נופל לפעולת ברירת המחדל, לא ל"extract.items" שנתבקשה בשגיאת כתיב
    expect(spec.actions).toHaveLength(1)
    expect(spec.actions[0].id).toBe('process')
  })

  it('לא מאפשר ליכולת שמשנה את העולם להיות כפתור בלוח', () => {
    const spec = normalizeSpec({
      ...base,
      actions: [
        { id: 'cal', label: 'הוסף ליומן', capability: 'calendar.createEvent', prompt: 'p', output: 'text' },
        { id: 'ok', label: 'נסח', capability: 'compose.text', prompt: 'p', output: 'text' },
      ],
    })

    expect(spec.actions.map((a) => a.id)).toEqual(['ok'])
  })

  it('קובע את סוג הפלט לפי היכולת ולא לפי מה שהמודל הצהיר', () => {
    const spec = normalizeSpec({
      ...base,
      actions: [
        { id: 'a', label: 'נסח', capability: 'compose.text', prompt: 'p', output: 'items' },
        { id: 'b', label: 'פרק', capability: 'extract.items', prompt: 'p', output: 'text' },
      ],
    })

    expect(spec.actions.find((a) => a.id === 'a')?.output).toBe('text')
    expect(spec.actions.find((a) => a.id === 'b')?.output).toBe('both')
  })

  it('מסיק יכולת רק כשהיא חסרה לגמרי — מפרט שנשמר לפני הקטלוג', () => {
    const spec = normalizeSpec({
      ...base,
      actions: [
        { id: 'organize', label: 'סדר', prompt: 'p', output: 'both', target: 'items' },
        { id: 'respond', label: 'נסח תשובה', prompt: 'p', output: 'text' },
      ],
    })

    expect(spec.actions.find((a) => a.id === 'organize')?.capability).toBe('extract.items')
    expect(spec.actions.find((a) => a.id === 'respond')?.capability).toBe('compose.text')
  })

  it('תמיד נשאר עם פעולה אחת לפחות ועם כפתור ראשי יחיד', () => {
    const spec = normalizeSpec({ ...base, actions: [] })
    expect(spec.actions.length).toBeGreaterThan(0)
    expect(spec.actions.filter((a) => a.primary)).toHaveLength(1)
  })

  it('שורד קלט זבל לחלוטין', () => {
    for (const junk of [null, undefined, 42, 'טקסט', [], { actions: 'לא מערך' }]) {
      const spec = normalizeSpec(junk)
      expect(spec.fields.length).toBeGreaterThan(0)
      expect(spec.actions.length).toBeGreaterThan(0)
      expect(spec.collections.length).toBeGreaterThan(0)
    }
  })

  it('מנקה ערכי בקרה חריגים לטווח חוקי', () => {
    const spec = normalizeSpec({
      ...base,
      actions: [{ id: 'a', label: 'x', capability: 'compose.text', prompt: 'p', output: 'text' }],
      controls: [
        { id: 's', label: 'סליידר', type: 'slider', min: 5, max: 1, step: 0, default: 99 },
        { id: 'c', label: 'בורר', type: 'choice', options: [], default: 'לא קיים' },
      ],
    })

    const slider = spec.controls.find((c) => c.id === 's')!
    expect(slider.max).toBeGreaterThan(slider.min!)
    expect(Number(slider.default)).toBeLessThanOrEqual(slider.max!)
    expect(slider.step).toBeGreaterThan(0)

    const choice = spec.controls.find((c) => c.id === 'c')!
    expect(choice.options!.length).toBeGreaterThan(0)
    expect(choice.options).toContain(choice.default)
  })
})

describe('permissionsFor — ההרשאות נגזרות מהיכולות', () => {
  it('כלי שרק מנסח טקסט לא מקבל הרשאת כתיבה לרשימות', () => {
    const spec = normalizeSpec({
      ...base,
      collections: [],
      actions: [{ id: 'a', label: 'נסח', capability: 'compose.text', prompt: 'p', output: 'text' }],
    })
    // normalizeSpec מוסיף אוסף ברירת מחדל, ולכן בודקים ישירות על מפרט בלי אוסף
    const withoutCollections = { ...spec, collections: [] }
    expect(permissionsFor(withoutCollections)).not.toContain('write.list')
    expect(permissionsFor(withoutCollections)).toContain('draft.text')
  })

  it('כלי עם חילוץ פריטים מקבל הרשאת כתיבה לרשימות', () => {
    const spec = normalizeSpec({
      ...base,
      actions: [{ id: 'a', label: 'פרק', capability: 'extract.items', prompt: 'p', output: 'both' }],
    })
    expect(permissionsFor(spec)).toContain('write.list')
  })
})

describe('inferCapability', () => {
  it('פלט פריטים תמיד מוביל לחילוץ או סיווג, לא לתכנון', () => {
    expect(inferCapability({ output: 'both', label: 'סדר' })).toBe('extract.items')
    expect(inferCapability({ output: 'items', label: 'סווג הוצאות' })).toBe('classify')
  })

  it('רמזי תווית פועלים רק על פלט טקסט', () => {
    expect(inferCapability({ output: 'text', label: 'תמונת מצב' })).toBe('summarize')
    expect(inferCapability({ output: 'text', label: 'הצע שיבוץ' })).toBe('plan')
    expect(inferCapability({ output: 'text', label: 'נסח תשובה' })).toBe('compose.text')
  })
})

describe('בחירת תבנית במנוע המקומי', () => {
  for (const testCase of PATTERN_CASES) {
    it(`${testCase.note}: "${testCase.brief.slice(0, 30)}…"`, () => {
      const match = pickPattern(testCase.brief)
      expect(match.pattern?.id ?? null).toBe(testCase.expected)
    })
  }

  it('כל תבנית מייצרת מפרט תקין שעובר את הקטלוג', () => {
    for (const testCase of PATTERN_CASES) {
      const { spec } = buildSpecLocally(testCase.brief)
      expect(spec.actions.length).toBeGreaterThan(0)
      expect(spec.actions.every((a) => a.capability)).toBe(true)
      expect(spec.sourceBrief).toBe(testCase.brief)
    }
  })
})
