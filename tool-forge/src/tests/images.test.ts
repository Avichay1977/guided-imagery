import { describe, expect, it } from 'vitest'
import { approximateBytes, isImageValue, parseDataUrl } from '../engine/images'
import { buildActionRequest, renderPrompt, type ContentBlock } from '../engine/requests'
import { normalizeSpec } from '../engine/specSchema'
import type { ToolSpec } from '../types'

/**
 * הכלל שנשמר כאן: **תמונה לא נכנסת לפרומפט כטקסט.**
 * ערך של שדה תמונה הוא data URL באורך מאות אלפי תווים; אם הוא ידלוף לתוך
 * המחרוזת של הפרומפט הוא יבזבז את החלון, יעלה כסף, ולא יובן. הוא חייב
 * לצאת כבלוק image ותו לא.
 */

const PNG =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='

function specWithImage(): ToolSpec {
  return normalizeSpec({
    name: 'בדיקת ציוד',
    tagline: 't',
    icon: '📷',
    systemPrompt: 's',
    fields: [
      { id: 'photo', label: 'תמונה', type: 'image' },
      { id: 'notes', label: 'הערות', type: 'longtext' },
    ],
    controls: [],
    actions: [
      {
        id: 'go',
        label: 'נתח',
        capability: 'extract.items',
        prompt: 'נתח את {{photo}} יחד עם {{notes}}',
        output: 'both',
      },
    ],
    collections: [{ id: 'items', label: 'ממצאים', itemLabel: 'ממצא', statuses: ['פתוח'] }],
  })
}

describe('זיהוי data URL', () => {
  it('מקבל את ארבעת הפורמטים שה-API תומך בהם', () => {
    for (const type of ['png', 'jpeg', 'gif', 'webp']) {
      expect(parseDataUrl(`data:image/${type};base64,AAAA`)?.mediaType).toBe(`image/${type}`)
    }
  })

  it('מנרמל image/jpg ל-image/jpeg', () => {
    // דפדפנים מייצרים לפעמים jpg; ה-API מכיר רק jpeg
    expect(parseDataUrl('data:image/jpg;base64,AAAA')?.mediaType).toBe('image/jpeg')
  })

  it('דוחה פורמט שה-API לא מקבל', () => {
    expect(parseDataUrl('data:image/svg+xml;base64,AAAA')).toBeNull()
    expect(parseDataUrl('data:application/pdf;base64,AAAA')).toBeNull()
  })

  it('טקסט רגיל אינו תמונה', () => {
    expect(isImageValue('בדקה 1:24 הווקאל נעלם')).toBe(false)
    expect(isImageValue('')).toBe(false)
    expect(isImageValue('https://example.com/a.png')).toBe(false)
  })

  it('מודד גודל base64 בקירוב סביר', () => {
    expect(approximateBytes('AAAA')).toBe(3)
  })
})

describe('בניית הבקשה עם תמונה', () => {
  const spec = specWithImage()

  it('התמונה יוצאת כבלוק image ולא כטקסט', () => {
    const request = buildActionRequest(
      spec,
      spec.actions[0],
      { photo: PNG, notes: 'הכבל השני נראה שרוף' },
      {},
      [],
    )

    const content = request.messages[0].content as ContentBlock[]
    expect(Array.isArray(content)).toBe(true)

    const image = content.find((block) => block.type === 'image')
    expect(image).toBeDefined()
    expect(image).toMatchObject({ source: { type: 'base64', media_type: 'image/png' } })

    // הבדיקה שבאמת חשובה: ה-base64 לא נמצא בשום מקום בטקסט
    const text = content
      .filter((block): block is Extract<ContentBlock, { type: 'text' }> => block.type === 'text')
      .map((block) => block.text)
      .join('\n')
    expect(text).not.toContain('base64')
    expect(text).not.toContain(PNG.slice(30, 60))
    expect(text).toContain('הכבל השני נראה שרוף')
  })

  it('הפרומפט מזכיר את התמונה במילים במקום להטמיע אותה', () => {
    expect(renderPrompt('{{photo}}', spec, { photo: PNG }, {})).toBe('(התמונה המצורפת)')
  })

  it('בלי תמונה הבקשה נשארת מחרוזת פשוטה', () => {
    const request = buildActionRequest(spec, spec.actions[0], { notes: 'רק טקסט' }, {}, [])
    expect(typeof request.messages[0].content).toBe('string')
  })

  it('שדה תמונה ריק לא מייצר בלוק ריק', () => {
    const request = buildActionRequest(spec, spec.actions[0], { photo: '', notes: 'א' }, {}, [])
    expect(typeof request.messages[0].content).toBe('string')
  })

  it('ערך זבל בשדה תמונה לא נשלח כתמונה', () => {
    const request = buildActionRequest(
      spec,
      spec.actions[0],
      { photo: 'לא תמונה בכלל', notes: 'א' },
      {},
      [],
    )
    expect(typeof request.messages[0].content).toBe('string')
  })
})

describe('שדה תמונה במפרט', () => {
  it('נשמר כשהמודל מבקש אותו', () => {
    const spec = specWithImage()
    expect(spec.fields.find((field) => field.id === 'photo')?.type).toBe('image')
  })
})
