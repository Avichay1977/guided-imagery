import Anthropic from '@anthropic-ai/sdk'
import {
  buildActionRequest,
  buildEventRequest,
  buildSpecRequest,
  type ClaudeRequest,
} from '../src/engine/requests'

/**
 * פונקציית שרת שמחזיקה את מפתח ה-API במקום הדפדפן.
 *
 * הפריסה היא של Vercel (קובץ ב-api/ נעשה endpoint אוטומטית), אבל החתימה היא
 * Web Fetch רגילה, ולכן אותו קוד רץ גם ב-Cloudflare Workers, ב-Deno Deploy
 * וכל מקום שמקבל Request ומחזיר Response.
 *
 * שתי הגנות שהופכות את זה לשרת ולא לצינור פתוח:
 *
 * 1. הלקוח לא שולח פרומפט. הוא שולח kind + args, והשרת בונה את הבקשה מאותו
 *    קוד שהלקוח היה מריץ (src/engine/requests.ts). אי אפשר לבקש דרך הכתובת
 *    הזו משהו שהאפליקציה לא מייצרת בעצמה.
 * 2. אם מוגדר TOOLFORGE_ACCESS_TOKEN, כל בקשה חייבת לשאת אותו בכותרת
 *    x-toolforge-token. בלי זה הכתובת פתוחה לכל מי שמצא אותה.
 *
 * משתני סביבה:
 *   ANTHROPIC_API_KEY        חובה
 *   TOOLFORGE_ACCESS_TOKEN   מומלץ מאוד
 *   TOOLFORGE_ALLOWED_ORIGIN ברירת מחדל '*'
 */

type Kind = 'buildSpec' | 'runAction' | 'draftEvent'

function json(body: unknown, status: number, origin: string): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': origin,
      'Access-Control-Allow-Headers': 'Content-Type, x-toolforge-token',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
    },
  })
}

function buildRequest(kind: Kind, args: unknown[]): ClaudeRequest {
  switch (kind) {
    case 'buildSpec':
      return buildSpecRequest(...(args as Parameters<typeof buildSpecRequest>))
    case 'runAction':
      return buildActionRequest(...(args as Parameters<typeof buildActionRequest>))
    case 'draftEvent':
      return buildEventRequest(...(args as Parameters<typeof buildEventRequest>))
    default:
      throw new Error(`סוג בקשה לא מוכר: ${String(kind)}`)
  }
}

export default async function handler(request: Request): Promise<Response> {
  const env = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env ?? {}
  const origin = env.TOOLFORGE_ALLOWED_ORIGIN ?? '*'

  if (request.method === 'OPTIONS') return json({}, 204, origin)
  if (request.method !== 'POST') return json({ error: 'שיטה לא נתמכת' }, 405, origin)

  const expectedToken = env.TOOLFORGE_ACCESS_TOKEN
  if (expectedToken && request.headers.get('x-toolforge-token') !== expectedToken) {
    return json({ error: 'אין הרשאה לשרת הזה' }, 401, origin)
  }

  const apiKey = env.ANTHROPIC_API_KEY
  if (!apiKey) {
    return json({ error: 'לשרת חסר ANTHROPIC_API_KEY' }, 500, origin)
  }

  let payload: { kind?: Kind; args?: unknown[] }
  try {
    payload = (await request.json()) as typeof payload
  } catch {
    return json({ error: 'גוף הבקשה אינו JSON תקין' }, 400, origin)
  }

  if (!payload.kind || !Array.isArray(payload.args)) {
    return json({ error: 'הבקשה חייבת לכלול kind ו-args' }, 400, origin)
  }

  let built: ClaudeRequest
  try {
    built = buildRequest(payload.kind, payload.args)
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : 'בקשה לא תקינה' }, 400, origin)
  }

  try {
    const client = new Anthropic({ apiKey })
    const message = await client.messages.create(
      built as Anthropic.MessageCreateParamsNonStreaming,
    )

    if (message.stop_reason === 'refusal') {
      return json({ error: 'המודל סירב לענות על הבקשה הזו.' }, 200, origin)
    }

    const text = message.content
      .filter((block): block is Anthropic.TextBlock => block.type === 'text')
      .map((block) => block.text)
      .join('\n')
      .trim()

    return json({ text }, 200, origin)
  } catch (error) {
    const status = error instanceof Anthropic.APIError ? error.status : 500
    return json(
      { error: error instanceof Error ? error.message : 'שגיאה מול Anthropic' },
      typeof status === 'number' ? status : 500,
      origin,
    )
  }
}

export const config = { runtime: 'edge' }
