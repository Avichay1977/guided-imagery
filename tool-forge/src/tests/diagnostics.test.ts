import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { explainCalendarFailure, explainClaudeFailure, runDiagnostics } from '../engine/diagnostics'
import { __setCalendarApiBase, __setToken, disconnect } from '../engine/googleCalendar'
import { DEFAULT_SETTINGS } from '../store/storage'
import type { Settings } from '../types'

/**
 * בדיקת החיבור נועדה להפוך כשל סתום לתשובה מעשית, ולכן מה שצריך להיבדק כאן
 * הוא לא "האם נכשל" אלא **האם ההוראה שחוזרת נכונה**. כל תרחיש כאן הוא תקלה
 * אמיתית שקורית בהתקנה ראשונה: מפתח שלא הוגדר בשרת, אסימון שרת שגוי,
 * Calendar API שלא הופעל בפרויקט, ואסימון שפג.
 *
 * שני השרתים המקומיים מחזירים את אותם גופי תשובה שה-API האמיתי מחזיר.
 */

// ── שרת שמדמה את api/claude.ts ─────────────────────────────────────────
let toolforge: Server
let toolforgeUrl = ''
let serverMode: 'ok' | 'malformed' | 'no-key' | 'bad-token' = 'ok'
let lastServerBody: { kind?: string; args?: unknown[] } = {}
let lastServerToken: string | undefined

// ── שרת שמדמה את Google Calendar ───────────────────────────────────────
let google: Server
let googleUrl = ''
let googleMode: 'ok' | 'disabled' | 'scope' | 'expired' | 'origin' = 'ok'

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
  toolforge = createServer(async (req, res) => {
    lastServerBody = JSON.parse((await readBody(req)) || '{}')
    lastServerToken = req.headers['x-toolforge-token'] as string | undefined

    const json = (status: number, body: unknown) => {
      res.writeHead(status, { 'content-type': 'application/json' })
      res.end(JSON.stringify(body))
    }

    // גופי התשובה זהים לאלה של api/claude.ts
    if (serverMode === 'bad-token') return json(401, { error: 'אין הרשאה לשרת הזה' })
    if (serverMode === 'no-key') return json(500, { error: 'לשרת חסר ANTHROPIC_API_KEY' })
    if (serverMode === 'malformed') return json(200, { text: JSON.stringify({ okay: 1 }) })
    return json(200, { text: JSON.stringify({ ok: true }) })
  })
  toolforgeUrl = await listen(toolforge)

  google = createServer((_req, res) => {
    const json = (status: number, body: unknown) => {
      res.writeHead(status, { 'content-type': 'application/json' })
      res.end(JSON.stringify(body))
    }

    // ההודעות למטה מועתקות מהצורה שבה Google מחזירה אותן בפועל
    if (googleMode === 'disabled') {
      return json(403, {
        error: {
          code: 403,
          status: 'PERMISSION_DENIED',
          message:
            'Google Calendar API has not been used in project 123456 before or it is disabled.',
        },
      })
    }
    if (googleMode === 'scope') {
      return json(403, {
        error: {
          code: 403,
          status: 'PERMISSION_DENIED',
          message: 'Request had insufficient authentication scopes.',
        },
      })
    }
    if (googleMode === 'expired') {
      return json(401, {
        error: { code: 401, status: 'UNAUTHENTICATED', message: 'Invalid Credentials' },
      })
    }
    if (googleMode === 'origin') {
      return json(403, { error: { code: 403, message: 'Forbidden' } })
    }

    json(200, { items: [{ id: 'next_1', summary: 'פגישה' }] })
  })
  googleUrl = await listen(google)
  __setCalendarApiBase(googleUrl)
})

afterAll(() => {
  toolforge.close()
  google.close()
})

beforeEach(() => {
  serverMode = 'ok'
  googleMode = 'ok'
  disconnect()
})

function settings(overrides: Partial<Settings> = {}): Settings {
  return { ...DEFAULT_SETTINGS, ...overrides }
}

function find(results: Awaited<ReturnType<typeof runDiagnostics>>, id: string) {
  const result = results.find((entry) => entry.id === id)
  if (!result) throw new Error(`הבדיקה ${id} לא הופיעה בדוח`)
  return result
}

describe('runDiagnostics — מסלול אל Claude', () => {
  it('בלי מפתח ובלי שרת: מדווח מצב הדגמה ולא מציג כישלון', async () => {
    const results = await runDiagnostics(settings())
    expect(results.every((entry) => entry.status === 'skip')).toBe(true)
    expect(find(results, 'transport').detail).toContain('הדגמה')
  })

  it('דרך השרת: הקריאה עוברת, והלקוח לא שולח פרומפט אלא kind בלבד', async () => {
    const results = await runDiagnostics(
      settings({ serverUrl: toolforgeUrl, serverToken: 'secret' }),
    )

    expect(find(results, 'transport').status).toBe('ok')
    expect(find(results, 'claude.call').status).toBe('ok')
    expect(lastServerBody.kind).toBe('probe')
    expect(lastServerBody.args).toEqual([])
    expect(lastServerToken).toBe('secret')
  })

  it('תשובה שלא במבנה שביקשנו נספרת ככישלון ולא כהצלחה', async () => {
    serverMode = 'malformed'
    const check = find(await runDiagnostics(settings({ serverUrl: toolforgeUrl })), 'claude.call')

    expect(check.status).toBe('fail')
    expect(check.fix).toContain('structured outputs')
  })

  it('שרת בלי מפתח: מפנה למשתנה הסביבה, לא למפתח שבהגדרות', async () => {
    serverMode = 'no-key'
    const check = find(await runDiagnostics(settings({ serverUrl: toolforgeUrl })), 'claude.call')

    expect(check.status).toBe('fail')
    expect(check.fix).toContain('ANTHROPIC_API_KEY')
  })

  it('אסימון שרת שגוי: מפנה ל-TOOLFORGE_ACCESS_TOKEN ולא ל-Anthropic', async () => {
    serverMode = 'bad-token'
    const check = find(
      await runDiagnostics(settings({ serverUrl: toolforgeUrl, serverToken: 'wrong' })),
      'claude.call',
    )

    expect(check.status).toBe('fail')
    expect(check.fix).toContain('TOOLFORGE_ACCESS_TOKEN')
    expect(check.fix).not.toContain('sk-ant-')
  })

  it('כתובת שרת שאין בה שרת: נכשל ברשת ולא מתפרש כמפתח פסול', async () => {
    // 127.0.0.1:1 סגורה תמיד — כישלון חיבור אמיתי, לא מדומה
    const check = find(
      await runDiagnostics(settings({ serverUrl: 'http://127.0.0.1:1/api/claude' })),
      'claude.call',
    )

    expect(check.status).toBe('fail')
    expect(check.fix).toContain('CORS')
  })
})

describe('runDiagnostics — Google Calendar', () => {
  const withClient = { googleClientId: '123456.apps.googleusercontent.com' }

  it('בלי Client ID: מדלג ולא מנסה להתחבר', async () => {
    const results = await runDiagnostics(settings())
    expect(find(results, 'calendar.clientId').status).toBe('skip')
    expect(find(results, 'calendar.call').status).toBe('skip')
  })

  it('יש Client ID אבל אין אסימון: מבקש להתחבר, לא מדווח תקלה', async () => {
    const check = find(await runDiagnostics(settings(withClient)), 'calendar.call')
    expect(check.status).toBe('skip')
    expect(check.detail).toContain('התחברות ליומן')
  })

  it('חיבור תקין: קורא אירועים בלי לשנות כלום', async () => {
    __setToken('test-token')
    const check = find(await runDiagnostics(settings(withClient)), 'calendar.call')
    expect(check.status).toBe('ok')
    expect(check.detail).toContain('1')
  })

  it('Calendar API לא מופעל: מפנה להפעלה בקונסולה', async () => {
    __setToken('test-token')
    googleMode = 'disabled'
    const check = find(await runDiagnostics(settings(withClient)), 'calendar.call')

    expect(check.status).toBe('fail')
    expect(check.fix).toContain('Enable')
  })

  it('הרשאה חסרה: מפנה למסך ההסכמה ולהתחברות מחדש', async () => {
    __setToken('test-token')
    googleMode = 'scope'
    const check = find(await runDiagnostics(settings(withClient)), 'calendar.call')

    expect(check.status).toBe('fail')
    expect(check.fix).toContain('calendar.events')
  })

  it('אסימון פג: מסביר שהוא בזיכרון בלבד', async () => {
    __setToken('test-token')
    googleMode = 'expired'
    const check = find(await runDiagnostics(settings(withClient)), 'calendar.call')

    expect(check.status).toBe('fail')
    expect(check.fix).toContain('התחברות ליומן')
  })

  it('403 סתמי: מפנה ל-Authorized JavaScript origins', async () => {
    __setToken('test-token')
    googleMode = 'origin'
    const check = find(await runDiagnostics(settings(withClient)), 'calendar.call')

    expect(check.status).toBe('fail')
    expect(check.fix).toContain('origins')
  })
})

describe('הודעות התיקון עצמן', () => {
  it('אותה שגיאת 401 מקבלת תיקון שונה לפי המסלול', () => {
    const error = new Error('401 invalid x-api-key')
    expect(explainClaudeFailure(error, 'direct').fix).toContain('sk-ant-')
    expect(explainClaudeFailure(error, 'server').fix).toContain('ANTHROPIC_API_KEY')
  })

  it('חריגת מכסה לא נשלחת את המשתמש לבדוק מפתח', () => {
    const check = explainClaudeFailure(new Error('429 rate_limit_error'), 'direct')
    expect(check.fix).toContain('דקה')
  })

  it('שגיאה לא מוכרת נשמרת כלשונה במקום להיעלם', () => {
    const check = explainClaudeFailure(new Error('משהו מוזר לגמרי'), 'direct')
    expect(check.detail).toContain('משהו מוזר לגמרי')
    expect(check.fix).toBeTruthy()
  })

  it('כל כישלון מחזיר גם מה לעשות', () => {
    const failures = [
      explainClaudeFailure(new Error('403 permission denied'), 'direct'),
      explainClaudeFailure(new Error('400 invalid_request'), 'server'),
      explainCalendarFailure(new Error('Invalid Credentials 401')),
      explainCalendarFailure(new Error('משהו אחר')),
    ]
    for (const check of failures) {
      expect(check.status).toBe('fail')
      expect(check.fix?.length ?? 0).toBeGreaterThan(10)
    }
  })
})
