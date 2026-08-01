import Anthropic from '@anthropic-ai/sdk'
import type { Settings } from '../types'
import {
  buildActionRequest,
  buildEventRequest,
  buildSpecRequest,
  type ClaudeRequest,
  type RequestKind,
} from './requests'

/**
 * שני מסלולים אל המודל, ובחירה ביניהם במקום אחד.
 *
 * direct — המפתח יושב בדפדפן ונשלח ישירות ל-Anthropic. מתאים לשימוש אישי
 *          במחשב שלכם, וזה מה שהיה כאן עד עכשיו.
 * server — הדפדפן לא מחזיק מפתח בכלל. הוא שולח kind + קלט לפונקציה שלכם
 *          (api/claude.ts), והיא מחזיקה את המפתח בצד השרת. זה המסלול שצריך
 *          ברגע שיש משתמש שני.
 *
 * הלקוח אף פעם לא שולח פרומפט חופשי לשרת — הוא שולח סוג בקשה וקלט, והשרת
 * בונה את הפרומפט מאותו קוד (engine/requests.ts). ככה אי אפשר להשתמש בשרת
 * שלכם כצינור פתוח למודל.
 */

export type Connection =
  | { mode: 'direct'; apiKey: string; baseUrl?: string }
  | { mode: 'server'; url: string; token: string }

export function connectionFrom(settings: Settings): Connection | null {
  if (settings.serverUrl.trim()) {
    return { mode: 'server', url: settings.serverUrl.trim(), token: settings.serverToken.trim() }
  }
  if (settings.apiKey.trim()) return { mode: 'direct', apiKey: settings.apiKey.trim() }
  return null
}

export interface RequestInput {
  buildSpec: Parameters<typeof buildSpecRequest>
  runAction: Parameters<typeof buildActionRequest>
  draftEvent: Parameters<typeof buildEventRequest>
}

function buildRequest<K extends RequestKind>(kind: K, args: RequestInput[K]): ClaudeRequest {
  switch (kind) {
    case 'buildSpec':
      return buildSpecRequest(...(args as RequestInput['buildSpec']))
    case 'runAction':
      return buildActionRequest(...(args as RequestInput['runAction']))
    default:
      return buildEventRequest(...(args as RequestInput['draftEvent']))
  }
}

function textOf(message: Anthropic.Message): string {
  return message.content
    .filter((block): block is Anthropic.TextBlock => block.type === 'text')
    .map((block) => block.text)
    .join('\n')
    .trim()
}

/** ניתוח JSON עם רשת ביטחון אם המודל עטף אותו בטקסט. */
export function parseJson(raw: string): unknown {
  try {
    return JSON.parse(raw)
  } catch {
    const start = raw.indexOf('{')
    const end = raw.lastIndexOf('}')
    if (start >= 0 && end > start) return JSON.parse(raw.slice(start, end + 1))
    throw new Error('התשובה מהמודל לא הייתה JSON תקין')
  }
}

/**
 * שולח בקשה במסלול המתאים ומחזיר את הטקסט הגולמי של התשובה.
 * הבנייה עצמה זהה בשני המסלולים; ההבדל הוא רק מי מחזיק את המפתח.
 */
export async function callClaude<K extends RequestKind>(
  connection: Connection,
  kind: K,
  args: RequestInput[K],
): Promise<string> {
  if (connection.mode === 'direct') {
    const client = new Anthropic({
      apiKey: connection.apiKey,
      dangerouslyAllowBrowser: true,
      ...(connection.baseUrl ? { baseURL: connection.baseUrl } : {}),
    })
    const request = buildRequest(kind, args)
    const message = await client.messages.create(request as Anthropic.MessageCreateParamsNonStreaming)
    if (message.stop_reason === 'refusal') throw new Error('המודל סירב לענות על הבקשה הזו.')
    return textOf(message)
  }

  const response = await fetch(connection.url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(connection.token ? { 'x-toolforge-token': connection.token } : {}),
    },
    body: JSON.stringify({ kind, args }),
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { error?: string } | null
    throw new Error(body?.error ?? `השרת החזיר שגיאה (${response.status})`)
  }

  const body = (await response.json()) as { text?: string; error?: string }
  if (body.error) throw new Error(body.error)
  return body.text ?? ''
}

export function describeApiError(error: unknown): string {
  if (error instanceof Anthropic.AuthenticationError) return 'המפתח לא תקין. בדקו אותו בהגדרות.'
  if (error instanceof Anthropic.PermissionDeniedError) return 'למפתח אין הרשאה למודל המבוקש.'
  if (error instanceof Anthropic.RateLimitError) return 'חריגה ממכסת הבקשות. נסו שוב בעוד רגע.'
  if (error instanceof Anthropic.APIConnectionError)
    return 'לא הצלחנו להגיע ל-Anthropic. בדקו חיבור לאינטרנט או חסימת CORS בדפדפן.'
  if (error instanceof Anthropic.APIError) return `שגיאת API (${error.status}): ${error.message}`
  if (error instanceof Error) return error.message
  return 'שגיאה לא ידועה'
}
