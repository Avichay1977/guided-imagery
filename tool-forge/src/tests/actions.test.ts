import { describe, expect, it } from 'vitest'
import { normalizeSpec } from '../engine/specSchema'
import { renderPrompt } from '../engine/requests'
import { runActionLocally } from '../engine/localActions'
import { draftEventLocally } from '../engine/scheduling'
import { eventIdFor } from '../engine/googleCalendar'
import { describeChanges, specsDiffer } from '../engine/versions'
import { DATE_CASES, EXTRACTION_CASES } from './corpus'
import type { CollectionItem, ToolSpec } from '../types'

function makeSpec(): ToolSpec {
  return normalizeSpec({
    name: 'כלי בדיקה',
    tagline: 't',
    icon: '🧪',
    systemPrompt: 's',
    fields: [
      { id: 'notes', label: 'הערות', type: 'longtext', required: true },
      { id: 'project', label: 'פרויקט', type: 'text' },
    ],
    controls: [
      { id: 'level', label: 'רמה', type: 'slider', min: 1, max: 5, step: 1, default: 3 },
      { id: 'flag', label: 'דגל', type: 'toggle', default: true },
    ],
    actions: [
      {
        id: 'go',
        label: 'פרק',
        capability: 'extract.items',
        prompt: 'רמה {{level}}, דגל {{flag}}, פרויקט {{project}}, הערות: {{notes}}',
        output: 'both',
        target: 'items',
        primary: true,
      },
    ],
    collections: [
      { id: 'items', label: 'רשימה', itemLabel: 'פריט', statuses: ['פתוח', 'בוצע'], hasTimecode: true },
    ],
  })
}

function makeItem(partial: Partial<CollectionItem>): CollectionItem {
  return {
    id: 'item_1',
    collectionId: 'items',
    title: 'פריט',
    status: 'פתוח',
    createdAt: new Date().toISOString(),
    ...partial,
  }
}

describe('renderPrompt', () => {
  const spec = makeSpec()

  it('מחליף ערכי שדות ובקרות', () => {
    const rendered = renderPrompt(spec.actions[0].prompt, spec, { notes: 'טקסט', project: 'שיר' }, {
      level: 4,
      flag: true,
    })
    expect(rendered).toContain('רמה 4')
    expect(rendered).toContain('פרויקט שיר')
    expect(rendered).toContain('הערות: טקסט')
  })

  it('מתרגם מתג למילים ולא ל-true/false', () => {
    expect(renderPrompt('{{flag}}', spec, {}, { flag: true })).toBe('דלוק')
    expect(renderPrompt('{{flag}}', spec, {}, { flag: false })).toBe('כבוי')
  })

  it('מסמן שדה שלא מולא במקום להשאיר חור', () => {
    expect(renderPrompt('{{project}}', spec, { project: '' }, {})).toBe('(לא הוזן)')
  })

  it('מוחק placeholder של מזהה שלא קיים במפרט', () => {
    expect(renderPrompt('לפני {{unknown_id}} אחרי', spec, {}, {})).toBe('לפני  אחרי')
  })
})

describe('runActionLocally — מצב הדגמה', () => {
  const spec = makeSpec()

  for (const testCase of EXTRACTION_CASES) {
    it(`${testCase.note}`, () => {
      const result = runActionLocally(spec, spec.actions[0], { notes: testCase.text }, {}, [])
      expect(result.items.length).toBeGreaterThanOrEqual(testCase.minItems)
      if (testCase.minItems === 0) expect(result.items).toHaveLength(0)
    })
  }

  it('מחלץ חותמת זמן לפריט כשהאוסף תומך בכך', () => {
    const result = runActionLocally(
      spec,
      spec.actions[0],
      { notes: 'בדקה 1:24 הווקאל נעלם' },
      {},
      [],
    )
    expect(result.items[0].at).toBe('1:24')
  })

  it('מסמן כל פריט כתוצר של מצב הדגמה', () => {
    const result = runActionLocally(spec, spec.actions[0], { notes: 'שורה אחת' }, {}, [])
    expect(result.items[0].tags).toContain('הדגמה')
  })
})

describe('draftEventLocally — המערכת לא מנחשת', () => {
  for (const testCase of DATE_CASES) {
    it(`${testCase.note}: "${testCase.text}"`, () => {
      const draft = draftEventLocally(makeItem({ title: testCase.text }))

      expect(new Date(draft.start).getTime()).not.toBeNaN()
      expect(new Date(draft.end).getTime()).toBeGreaterThan(new Date(draft.start).getTime())

      if (!testCase.hasDate) expect(draft.missing).toContain('תאריך')
      if (!testCase.hasTime) expect(draft.missing).toContain('שעה')

      // כשמשהו חסר, הביטחון חייב לרדת — זה מה שמפעיל את האזהרה בכרטיס
      if (!testCase.hasDate || !testCase.hasTime) {
        expect(draft.confidence).toBeLessThan(0.5)
      } else {
        expect(draft.confidence).toBeGreaterThanOrEqual(0.5)
      }
    })
  }

  it('מועד מוצע תמיד בעתיד', () => {
    for (const testCase of DATE_CASES) {
      const draft = draftEventLocally(makeItem({ title: testCase.text }))
      expect(new Date(draft.start).getTime()).toBeGreaterThan(Date.now() - 60_000)
    }
  })

  it('שומר את מקור המידע לצורך provenance', () => {
    const draft = draftEventLocally(makeItem({ title: 'פגישה', at: 'יום שני 10:00' }))
    expect(draft.source).toContain('יום שני 10:00')
  })
})

describe('eventIdFor — מניעת כפילות מבנית', () => {
  it('מייצר מזהה יציב לאותו פריט', () => {
    expect(eventIdFor('item_abc123')).toBe(eventIdFor('item_abc123'))
  })

  it('מייצר מזהים שונים לפריטים שונים', () => {
    expect(eventIdFor('item_a')).not.toBe(eventIdFor('item_b'))
  })

  it('עומד בדרישת התווים של Google (base32hex, אורך 5–1024)', () => {
    for (const id of ['item_1', 'פריט', 'x', 'item_ABC-999', '🎛️']) {
      const eventId = eventIdFor(id)
      expect(eventId).toMatch(/^[a-v0-9]{5,1024}$/)
    }
  })
})

describe('גרסאות', () => {
  it('מזהה שינוי אמיתי ומתעלם מחותמות זמן', () => {
    const a = makeSpec()
    const b = { ...a, updatedAt: new Date(Date.now() + 5000).toISOString() }
    expect(specsDiffer(a, b)).toBe(false)

    const c = { ...a, name: 'שם אחר' }
    expect(specsDiffer(a, c)).toBe(true)
  })

  it('מתאר בעברית מה השתנה', () => {
    const before = makeSpec()
    const after: ToolSpec = {
      ...before,
      name: 'שם חדש',
      actions: before.actions.filter((action) => action.id !== 'go'),
    }

    const changes = describeChanges(before, after)
    expect(changes.join(' ')).toContain('שם הכלי')
    expect(changes.join(' ')).toContain('הוסר כפתור: פרק')
  })

  it('מסמן שינוי ביכולת כשורה נפרדת', () => {
    const before = makeSpec()
    const after: ToolSpec = {
      ...before,
      actions: [{ ...before.actions[0], capability: 'classify' }],
    }
    expect(describeChanges(before, after).join(' ')).toContain('יכולת של "פרק"')
  })

  it('לעולם לא מחזיר רשימת שינויים ריקה', () => {
    const spec = makeSpec()
    expect(describeChanges(spec, spec).length).toBeGreaterThan(0)
  })
})
