import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import {
  ACTION_RESULT_JSON_SCHEMA,
  TOOL_SPEC_JSON_SCHEMA,
  normalizeSpec,
} from '../engine/specSchema'
import { EVENT_DRAFT_JSON_SCHEMA } from '../engine/scheduleSchema'
import { buildActionRequest, buildEventRequest, buildSpecRequest } from '../engine/requests'
import { callClaude, describeApiError } from '../engine/transport'
import {
  DuplicateEventError,
  __setCalendarApiBase,
  __setToken,
  createEvent,
  deleteEvent,
  eventIdFor,
  findDuplicate,
  isConnected,
} from '../engine/googleCalendar'

/**
 * בדיקות חוזה — הדבר הכי קרוב לקריאה אמיתית שאפשר בלי מפתח ובלי חשבון.
 *
 * שני שרתים מקומיים מחזירים בדיוק את המבנים שה-API האמיתי מחזיר, כולל מקרי
 * הכשל: סירוב של המודל, אסימון שפג, ומזהה אירוע תפוס. מה שנבדק כאן הוא הצד
 * שלנו — הבנייה, הפענוח והטיפול בשגיאות — שהוא גם הצד שיכול להיות שגוי.
 *
 * מה שבדיקות כאלה **לא** מוכיחות: שהמפתח שלכם תקף, ושהחשבון שלכם מורשה.
 */

// ── שרת שמדמה את Anthropic ─────────────────────────────────────────────
let anthropic: Server
let anthropicUrl = ''
let lastAnthropicBody: Record<string, unknown> = {}
let anthropicMode: 'ok' | 'refusal' | 'unauthorized' = 'ok'

// ── שרת שמדמה את Google Calendar ───────────────────────────────────────
let google: Server
let googleUrl = ''
let takenEventIds = new Set<string>()
let googleAuthValid = true
const deletedEvents: string[] = []

function listen(server: Server): Promise<string> {
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address() as AddressInfo
      resolve(`http://127.0.0.1:${port}`)
    })
  })
}

function readBody(req: import('node:http').IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    let data = ''
    req.on('data', (chunk) => (data += chunk))
    req.on('end', () => resolve(data))
  })
}

beforeAll(async () => {
  anthropic = createServer(async (req, res) => {
    lastAnthropicBody = JSON.parse((await readBody(req)) || '{}')

    if (anthropicMode === 'unauthorized') {
      res.writeHead(401, { 'content-type': 'application/json' })
      res.end(
        JSON.stringify({
          type: 'error',
          error: { type: 'authentication_error', message: 'invalid x-api-key' },
        }),
      )
      return
    }

    // מעטפת התשובה של Messages API, כולל stop_reason ו-usage
    res.writeHead(200, { 'content-type': 'application/json' })
    res.end(
      JSON.stringify({
        id: 'msg_test',
        type: 'message',
        role: 'assistant',
        model: 'claude-opus-5',
        content:
          anthropicMode === 'refusal'
            ? []
            : [{ type: 'text', text: JSON.stringify({ text: 'שלום', items: [] }) }],
        stop_reason: anthropicMode === 'refusal' ? 'refusal' : 'end_turn',
        stop_details: anthropicMode === 'refusal' ? { type: 'refusal', category: 'cyber' } : null,
        usage: { input_tokens: 10, output_tokens: 5 },
      }),
    )
  })
  anthropicUrl = await listen(anthropic)

  google = createServer(async (req, res) => {
    const url = new URL(req.url ?? '/', googleUrl)
    const json = (status: number, body: unknown) => {
      res.writeHead(status, { 'content-type': 'application/json' })
      res.end(JSON.stringify(body))
    }

    if (!googleAuthValid || !req.headers.authorization?.startsWith('Bearer ')) {
      json(401, {
        error: { code: 401, message: 'Request had invalid authentication credentials.', status: 'UNAUTHENTICATED' },
      })
      return
    }

    if (req.method === 'POST' && url.pathname.endsWith('/events')) {
      const body = JSON.parse((await readBody(req)) || '{}') as { id?: string; summary?: string }
      if (body.id && takenEventIds.has(body.id)) {
        // זה בדיוק מה ש-Google מחזיר על מזהה תפוס
        json(409, { error: { code: 409, message: 'The requested identifier already exists.' } })
        return
      }
      if (body.id) takenEventIds.add(body.id)
      json(200, {
        id: body.id ?? 'generated_id',
        summary: body.summary,
        htmlLink: 'https://calendar.google.com/event?eid=test',
      })
      return
    }

    if (req.method === 'GET' && url.pathname.endsWith('/events')) {
      json(200, {
        items: [
          {
            id: 'existing_1',
            summary: 'פגישה עם דנה',
            start: { dateTime: '2026-08-04T14:10:00+03:00' },
          },
          {
            id: 'far_away',
            summary: 'פגישה עם דנה',
            start: { dateTime: '2026-08-04T20:00:00+03:00' },
          },
        ],
      })
      return
    }

    if (req.method === 'DELETE') {
      deletedEvents.push(decodeURIComponent(url.pathname.split('/').pop() ?? ''))
      res.writeHead(204)
      res.end()
      return
    }

    json(404, { error: { code: 404, message: 'not found' } })
  })
  googleUrl = await listen(google)
  __setCalendarApiBase(googleUrl)
})

afterAll(() => {
  anthropic.close()
  google.close()
})

describe('סכימות structured outputs — הצורות שהמודל דוחה', () => {
  const schemas = {
    TOOL_SPEC: TOOL_SPEC_JSON_SCHEMA,
    ACTION_RESULT: ACTION_RESULT_JSON_SCHEMA,
    EVENT_DRAFT: EVENT_DRAFT_JSON_SCHEMA,
  }

  /** מגבלות structured outputs שמתועדות ב-API */
  const FORBIDDEN = [
    'minimum',
    'maximum',
    'exclusiveMinimum',
    'exclusiveMaximum',
    'multipleOf',
    'minLength',
    'maxLength',
    'pattern',
    'minItems',
    'maxItems',
    'uniqueItems',
  ]

  function walk(node: unknown, path: string, visit: (obj: Record<string, unknown>, path: string) => void) {
    if (!node || typeof node !== 'object') return
    if (Array.isArray(node)) {
      node.forEach((child, index) => walk(child, `${path}[${index}]`, visit))
      return
    }
    const obj = node as Record<string, unknown>
    visit(obj, path)
    for (const [key, value] of Object.entries(obj)) walk(value, `${path}.${key}`, visit)
  }

  for (const [name, schema] of Object.entries(schemas)) {
    it(`${name}: לא משתמשת במילות מפתח שאינן נתמכות`, () => {
      const found: string[] = []
      walk(schema, name, (obj, path) => {
        for (const key of FORBIDDEN) if (key in obj) found.push(`${path}.${key}`)
      })
      expect(found).toEqual([])
    })

    it(`${name}: לכל אובייקט יש additionalProperties:false וכל המאפיינים ב-required`, () => {
      const problems: string[] = []
      walk(schema, name, (obj, path) => {
        if (obj.type !== 'object') return
        if (obj.additionalProperties !== false) problems.push(`${path}: חסר additionalProperties:false`)
        const properties = Object.keys((obj.properties ?? {}) as Record<string, unknown>)
        const required = (obj.required ?? []) as string[]
        const missing = properties.filter((key) => !required.includes(key))
        if (missing.length) problems.push(`${path}: לא ב-required — ${missing.join(', ')}`)
      })
      expect(problems).toEqual([])
    })
  }
})

describe('בניית הבקשה — מה שנשלח בפועל', () => {
  it('שלוש הבקשות בנויות לפי מה שה-API מצפה לו', () => {
    const spec = normalizeSpec({
      name: 'x',
      tagline: 'y',
      icon: '🧪',
      systemPrompt: 'z',
      fields: [{ id: 'input', label: 'קלט', type: 'longtext' }],
      controls: [],
      actions: [{ id: 'a', label: 'פעולה', capability: 'extract.items', prompt: 'p', output: 'both' }],
      collections: [{ id: 'items', label: 'רשימה', itemLabel: 'פריט', statuses: ['פתוח'] }],
    })

    const requests = [
      buildSpecRequest('תיאור'),
      buildActionRequest(spec, spec.actions[0], { input: 'טקסט' }, {}, []),
      buildEventRequest({ title: 'פגישה' }, '2026-08-01T12:00:00', 'שבת', 'Asia/Jerusalem'),
    ]

    for (const request of requests) {
      expect(request.model).toBe('claude-opus-5')
      expect(request.max_tokens).toBeGreaterThan(0)
      expect(request.system.length).toBeGreaterThan(0)
      expect(request.messages).toHaveLength(1)
      expect(request.messages[0].role).toBe('user')
      expect(request.output_config.format.type).toBe('json_schema')
      expect(['low', 'medium', 'high']).toContain(request.output_config.effort)
    }
  })
})

describe('מסלול Anthropic מול שרת שמדמה את ה-API', () => {
  const connection = () => ({ mode: 'direct' as const, apiKey: 'sk-ant-test', baseUrl: anthropicUrl })

  it('שולח את הגוף שנבנה ומחזיר את הטקסט', async () => {
    anthropicMode = 'ok'
    const text = await callClaude(connection(), 'buildSpec', ['כלי לניהול לקוחות'])

    expect(JSON.parse(text)).toEqual({ text: 'שלום', items: [] })
    expect(lastAnthropicBody.model).toBe('claude-opus-5')
    expect((lastAnthropicBody.output_config as Record<string, unknown>).format).toBeDefined()
    expect(JSON.stringify(lastAnthropicBody)).toContain('כלי לניהול לקוחות')
  })

  it('סירוב של המודל הופך לשגיאה מובנת ולא לתשובה ריקה', async () => {
    anthropicMode = 'refusal'
    await expect(callClaude(connection(), 'buildSpec', ['x'])).rejects.toThrow('סירב')
  })

  it('401 מהשרת מתורגם להודעה על מפתח לא תקין', async () => {
    anthropicMode = 'unauthorized'
    try {
      await callClaude(connection(), 'buildSpec', ['x'])
      throw new Error('היה אמור להיכשל')
    } catch (error) {
      expect(describeApiError(error)).toContain('המפתח לא תקין')
    }
    anthropicMode = 'ok'
  })
})

describe('מסלול Google Calendar מול שרת שמדמה את ה-API', () => {
  beforeAll(() => {
    googleAuthValid = true
    takenEventIds = new Set()
    __setToken('test-token')
  })

  const draft = {
    summary: 'פגישה עם דנה',
    start: '2026-08-04T14:00:00',
    end: '2026-08-04T15:00:00',
  }

  it('יוצר אירוע ומחזיר מזהה וקישור', async () => {
    const event = await createEvent({ ...draft, eventId: eventIdFor('item_1') })
    expect(event.id).toBe(eventIdFor('item_1'))
    expect(event.htmlLink).toContain('calendar.google.com')
  })

  it('ניסיון שני עם אותו פריט נחסם על ידי Google ומזוהה ככפילות', async () => {
    await expect(createEvent({ ...draft, eventId: eventIdFor('item_1') })).rejects.toBeInstanceOf(
      DuplicateEventError,
    )
  })

  it('פריט אחר עובר בלי בעיה', async () => {
    const event = await createEvent({ ...draft, eventId: eventIdFor('item_2') })
    expect(event.id).toBe(eventIdFor('item_2'))
  })

  it('בדיקת חפיפה מוצאת רק אירוע שקרוב בזמן', async () => {
    const near = await findDuplicate('פגישה עם דנה', '2026-08-04T14:00:00+03:00')
    expect(near?.id).toBe('existing_1')

    const noMatch = await findDuplicate('משהו אחר לגמרי', '2026-08-04T14:00:00+03:00')
    expect(noMatch).toBeNull()
  })

  it('ביטול שולח DELETE על המזהה שנשמר', async () => {
    await deleteEvent(eventIdFor('item_2'))
    expect(deletedEvents).toContain(eventIdFor('item_2'))
  })

  it('401 מנתק את האסימון ומבקש התחברות מחדש', async () => {
    googleAuthValid = false
    await expect(createEvent({ ...draft, eventId: eventIdFor('item_3') })).rejects.toThrow('פגה')
    // האסימון נמחק מהזיכרון, ולכן הקריאה הבאה נעצרת עוד לפני הרשת
    expect(isConnected()).toBe(false)
    await expect(createEvent({ ...draft, eventId: eventIdFor('item_4') })).rejects.toThrow(
      'החיבור ל-Google פג',
    )
  })
})
