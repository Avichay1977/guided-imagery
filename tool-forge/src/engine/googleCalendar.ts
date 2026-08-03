/**
 * חיבור ל-Google Calendar — הפעולה החיצונית הראשונה של המערכת.
 *
 * שתי החלטות שמכתיבות את כל הקובץ:
 *
 * 1. אין שרת, ולכן משתמשים ב-Google Identity Services בזרימת ה-token של דפדפן.
 *    היא דורשת Client ID בלבד ולעולם לא client secret — אין סוד שאפשר לדלוף מכאן.
 * 2. אסימון הגישה נשמר **בזיכרון בלבד**, אף פעם לא ב-localStorage. הוא פג אחרי
 *    כשעה, ואחרי רענון דף צריך להתחבר מחדש. זה מכוון: אסימון יומן שיושב באחסון
 *    הדפדפן הוא בדיוק מה שלא רוצים שיישאר שם.
 *
 * הקריאות ל-API הן fetch גולמי — זה ה-REST API של Google, לא Anthropic.
 */

const GIS_SRC = 'https://accounts.google.com/gsi/client'
let CALENDAR_API = 'https://www.googleapis.com/calendar/v3'

/** לבדיקות בלבד: מפנה את הקריאות לשרת מקומי שמדמה את Google. */
export function __setCalendarApiBase(url: string): void {
  CALENDAR_API = url
}

/** לבדיקות בלבד: מזריק אסימון פעיל בלי לעבור דרך מסך ההסכמה. */
export function __setToken(value: string, ttlMs = 3600_000): void {
  token = { value, expiresAt: Date.now() + ttlMs }
}
/** רק יצירה וצפייה באירועים — לא קריאת כל היומן ולא הרשאות אחרות. */
export const CALENDAR_SCOPE = 'https://www.googleapis.com/auth/calendar.events'

interface TokenResponse {
  access_token?: string
  expires_in?: number
  error?: string
  error_description?: string
}

interface TokenClient {
  requestAccessToken: (overrides?: { prompt?: string }) => void
}

interface GoogleIdentityServices {
  accounts: {
    oauth2: {
      initTokenClient: (config: {
        client_id: string
        scope: string
        callback: (response: TokenResponse) => void
        error_callback?: (error: { type?: string; message?: string }) => void
      }) => TokenClient
      revoke: (token: string, done?: () => void) => void
    }
  }
}

declare global {
  interface Window {
    google?: GoogleIdentityServices
  }
}

let scriptPromise: Promise<void> | null = null

function loadGis(): Promise<void> {
  if (window.google?.accounts?.oauth2) return Promise.resolve()
  if (scriptPromise) return scriptPromise

  scriptPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = GIS_SRC
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => {
      scriptPromise = null
      reject(new Error('לא הצלחנו לטעון את ספריית ההתחברות של Google. בדקו חיבור לאינטרנט.'))
    }
    document.head.appendChild(script)
  })
  return scriptPromise
}

/** האסימון החי — בזיכרון בלבד. */
let token: { value: string; expiresAt: number } | null = null

export function isConnected(): boolean {
  return token !== null && token.expiresAt > Date.now() + 30_000
}

export function disconnect(): void {
  const current = token?.value
  token = null
  // typeof — הקובץ נטען גם מחוץ לדפדפן (בדיקות, רינדור בצד שרת)
  if (current && typeof window !== 'undefined' && window.google?.accounts?.oauth2) {
    window.google.accounts.oauth2.revoke(current)
  }
}

/** פותח את מסך ההסכמה של Google ומחזיר אסימון גישה לשעה הקרובה. */
export async function connect(clientId: string): Promise<void> {
  if (!clientId.trim()) {
    throw new Error('חסר Client ID של Google. הוסיפו אותו בהגדרות.')
  }
  await loadGis()

  await new Promise<void>((resolve, reject) => {
    const client = window.google!.accounts.oauth2.initTokenClient({
      client_id: clientId.trim(),
      scope: CALENDAR_SCOPE,
      callback: (response) => {
        if (response.error || !response.access_token) {
          reject(
            new Error(
              response.error_description ?? response.error ?? 'ההתחברות ל-Google לא הושלמה.',
            ),
          )
          return
        }
        token = {
          value: response.access_token,
          expiresAt: Date.now() + (response.expires_in ?? 3600) * 1000,
        }
        resolve()
      },
      error_callback: (error) => {
        reject(new Error(error.message ?? 'חלון ההתחברות של Google נסגר.'))
      },
    })
    client.requestAccessToken({ prompt: '' })
  })
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!isConnected()) {
    throw new Error('החיבור ל-Google פג. התחברו מחדש בהגדרות.')
  }
  const response = await fetch(`${CALENDAR_API}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token!.value}`,
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })

  if (response.status === 401) {
    token = null
    throw new Error('ההרשאה ליומן פגה. התחברו מחדש.')
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { message?: string }
    } | null
    throw new Error(body?.error?.message ?? `שגיאת Google Calendar (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export interface CalendarEvent {
  id: string
  summary?: string
  htmlLink?: string
  start?: { dateTime?: string; date?: string }
  end?: { dateTime?: string; date?: string }
}

/** קריאה מינימלית לקריאה בלבד — משמשת את בדיקת החיבור. */
export async function probeCalendar(): Promise<number> {
  const params = new URLSearchParams({
    timeMin: new Date().toISOString(),
    maxResults: '1',
    singleEvents: 'true',
  })
  const result = await call<{ items?: unknown[] }>(
    `/calendars/primary/events?${params.toString()}`,
  )
  return (result.items ?? []).length
}

/** לתצוגה בדוח הבדיקה בלבד. */
export function calendarBase(): string {
  return CALENDAR_API
}

export function localTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Jerusalem'
}

/**
 * מחפש אירוע קיים שחופף לטיוטה — הבסיס למניעת כפילות.
 * מחזיר אירוע רק אם הכותרת דומה **וגם** שעת ההתחלה קרובה (עד 30 דקות).
 */
export async function findDuplicate(
  summary: string,
  startIso: string,
): Promise<CalendarEvent | null> {
  const start = new Date(startIso)
  if (Number.isNaN(start.getTime())) return null

  const windowStart = new Date(start.getTime() - 12 * 3600_000).toISOString()
  const windowEnd = new Date(start.getTime() + 12 * 3600_000).toISOString()

  const params = new URLSearchParams({
    timeMin: windowStart,
    timeMax: windowEnd,
    singleEvents: 'true',
    orderBy: 'startTime',
    maxResults: '50',
  })

  const result = await call<{ items?: CalendarEvent[] }>(
    `/calendars/primary/events?${params.toString()}`,
  )

  const normalize = (text: string) => text.trim().toLowerCase().replace(/\s+/g, ' ')
  const target = normalize(summary)

  return (
    (result.items ?? []).find((event) => {
      const existing = normalize(event.summary ?? '')
      if (!existing) return false
      const titleMatches = existing === target || existing.includes(target) || target.includes(existing)
      if (!titleMatches) return false
      const existingStart = event.start?.dateTime ?? event.start?.date
      if (!existingStart) return false
      return Math.abs(new Date(existingStart).getTime() - start.getTime()) <= 30 * 60_000
    }) ?? null
  )
}

/**
 * מזהה יציב שנגזר מהפריט: אותו פריט תמיד ייתן אותו מזהה, כך שניסיון שני ליצור
 * את אותו אירוע נדחה בצד Google עם 409.
 *
 * הכללים לקוחים ממסמך ה-discovery של Google (schemas.Event.properties.id):
 * תווים מותרים הם base32hex בלבד — a–v ו-0–9 — והאורך בין 5 ל-1024.
 *
 * ⚠️ Google מציינת במפורש שהיא **לא מתחייבת** לזהות התנגשות מזהים בזמן היצירה,
 * בגלל האופי המבוזר של המערכת. לכן המזהה הוא שכבת ההגנה הראשונה ולא היחידה:
 * findDuplicate בודק חפיפה לפני שהכרטיס בכלל מגיע לאישור.
 */
export function eventIdFor(itemId: string): string {
  const encoded = Array.from(itemId)
    .map((char) => char.charCodeAt(0).toString(32))
    .join('')
    .replace(/[^a-v0-9]/g, '')
  return `toolforge${encoded}`.slice(0, 200).padEnd(5, '0')
}

export class DuplicateEventError extends Error {
  constructor(readonly eventId: string) {
    super('אירוע זהה כבר נוצר מהפריט הזה.')
    this.name = 'DuplicateEventError'
  }
}

export async function createEvent(draft: {
  summary: string
  description?: string
  start: string
  end: string
  /** מזהה יציב שנגזר מהפריט — המנגנון שמונע יצירה כפולה */
  eventId?: string
}): Promise<CalendarEvent> {
  const timeZone = localTimeZone()
  try {
    return await call<CalendarEvent>('/calendars/primary/events', {
      method: 'POST',
      body: JSON.stringify({
        id: draft.eventId,
        summary: draft.summary,
        description: draft.description,
        start: { dateTime: draft.start, timeZone },
        end: { dateTime: draft.end, timeZone },
      }),
    })
  } catch (error) {
    // Google מחזיר 409 כשהמזהה כבר קיים — זו בדיוק ההגנה מפני לחיצה כפולה
    if (draft.eventId && error instanceof Error && /409|already exists|duplicate/i.test(error.message)) {
      throw new DuplicateEventError(draft.eventId)
    }
    throw error
  }
}

/** ביטול — מוחק אירוע שאנחנו יצרנו, לפי המזהה ששמרנו. */
export async function deleteEvent(eventId: string): Promise<void> {
  await call<void>(`/calendars/primary/events/${encodeURIComponent(eventId)}`, {
    method: 'DELETE',
  })
}
