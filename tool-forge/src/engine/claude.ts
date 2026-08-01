import Anthropic from '@anthropic-ai/sdk'
import type { CollectionItem, SpecAction, ToolSpec } from '../types'
import type { ActionResult } from './localActions'
import { ACTION_RESULT_JSON_SCHEMA, TOOL_SPEC_JSON_SCHEMA, newId, normalizeSpec } from './specSchema'
import { CAPABILITIES, isDirectlyRunnable } from './capabilities'

const MODEL = 'claude-opus-5'

/**
 * המפתח נשמר בדפדפן של המשתמש ונשלח ישירות ל-Anthropic.
 * זה מתאים לשימוש אישי; באפליקציה שמשרתת משתמשים אחרים צריך שרת ביניים.
 */
function client(apiKey: string): Anthropic {
  return new Anthropic({ apiKey, dangerouslyAllowBrowser: true })
}

function textOf(message: Anthropic.Message): string {
  return message.content
    .filter((block): block is Anthropic.TextBlock => block.type === 'text')
    .map((block) => block.text)
    .join('\n')
    .trim()
}

function parseJson(raw: string): unknown {
  try {
    return JSON.parse(raw)
  } catch {
    // רשת ביטחון אם המודל עטף את ה-JSON בטקסט
    const start = raw.indexOf('{')
    const end = raw.lastIndexOf('}')
    if (start >= 0 && end > start) return JSON.parse(raw.slice(start, end + 1))
    throw new Error('התשובה מהמודל לא הייתה JSON תקין')
  }
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

const BUILDER_SYSTEM = `אתה מעצב "כלים אישיים" — לוחות שליטה קטנים מבוססי AI.

המשתמש מתאר בשפה חופשית מה הוא רוצה לנהל או לבצע, ואתה מחזיר מפרט של לוח שליטה אחד שעושה בדיוק את זה.

עקרונות:
- הלוח הוא מכשיר, לא צ׳אט. שדות קלט ספורים, בקרות שמכוונות התנהגות, וכפתורים שכל אחד מהם עושה דבר אחד ברור.
- כל prompt של פעולה חייב לעמוד בפני עצמו: להסביר מה בדיוק לייצר ובאיזה מבנה. שלב בו ערכי שדות ובקרות עם {{field_id}}.
- אוסף אחד (לרוב) שהוא הזיכרון של הכלי: מה שנכנס אליו נשאר ומצטבר.
- עברית בכל הטקסטים שמוצגים למשתמש. מזהים (id) באנגלית ב-snake_case.
- 1-3 שדות, 1-4 בקרות, 2-4 פעולות, 1-2 אוספים. אל תנפח.
- כל פעולה חייבת לבחור capability מתוך הקטלוג הסגור למטה. אין יכולות אחרות; בקשה ליכולת שלא ברשימה פשוט לא תיווצר.

הקטלוג:
${CAPABILITIES.filter(isDirectlyRunnable)
  .map((capability) => `- ${capability.id}: ${capability.description}`)
  .join('\n')}

פעולות שמשנות משהו מחוץ לאפליקציה (למשל הוספה ליומן) אינן כפתורים בלוח — הן מופעלות מפריט ועוברות תמיד דרך תור אישורים. אל תנסה ליצור כפתור כזה.`

/** בונה ToolSpec מתיאור חופשי, באמצעות Claude. */
export async function buildSpecWithClaude(brief: string, apiKey: string): Promise<ToolSpec> {
  const message = await client(apiKey).messages.create({
    model: MODEL,
    max_tokens: 16000,
    system: BUILDER_SYSTEM,
    output_config: {
      effort: 'high',
      format: { type: 'json_schema', schema: TOOL_SPEC_JSON_SCHEMA as Record<string, unknown> },
    },
    messages: [
      {
        role: 'user',
        content: `בנה לי לוח שליטה לפי התיאור הבא:\n\n"""${brief.trim()}"""`,
      },
    ],
  })

  return normalizeSpec(parseJson(textOf(message)), {
    id: newId('tool'),
    sourceBrief: brief.trim(),
    builtBy: 'claude',
  })
}

/** מחליף {{field_id}} בערכים בפועל של השדות והבקרות. */
export function renderPrompt(
  prompt: string,
  spec: ToolSpec,
  values: Record<string, string>,
  controls: Record<string, number | boolean | string>,
): string {
  return prompt.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_match, key: string) => {
    if (key in values) return values[key] || '(לא הוזן)'
    if (key in controls) {
      const control = spec.controls.find((c) => c.id === key)
      const value = controls[key]
      if (control?.type === 'toggle') return value ? 'דלוק' : 'כבוי'
      return String(value)
    }
    const control = spec.controls.find((c) => c.id === key)
    if (control) return String(control.default)
    const field = spec.fields.find((f) => f.id === key)
    if (field) return '(לא הוזן)'
    return ''
  })
}

function itemsContext(spec: ToolSpec, items: CollectionItem[]): string {
  if (items.length === 0) return 'האוספים ריקים כרגע.'
  return spec.collections
    .map((collection) => {
      const rows = items
        .filter((item) => item.collectionId === collection.id)
        .slice(-40)
        .map(
          (item) =>
            `- [${item.status}]${item.at ? ` (${item.at})` : ''} ${item.title}${
              item.detail ? ` — ${item.detail.replace(/\n+/g, ' ')}` : ''
            }`,
        )
      if (rows.length === 0) return `${collection.label}: ריק.`
      return `${collection.label} (${rows.length} ${collection.itemLabel}):\n${rows.join('\n')}`
    })
    .join('\n\n')
}

/** מריץ פעולה אחת של הלוח מול Claude ומחזיר טקסט ופריטים. */
export async function runActionWithClaude(
  spec: ToolSpec,
  action: SpecAction,
  values: Record<string, string>,
  controls: Record<string, number | boolean | string>,
  items: CollectionItem[],
  apiKey: string,
): Promise<ActionResult> {
  const collection = spec.collections.find((c) => c.id === action.target) ?? spec.collections[0]

  const system = `${spec.systemPrompt}

אתה מפעיל כלי בשם "${spec.name}" — ${spec.tagline}.
כל תשובה חוזרת כ-JSON עם שני שדות: text (טקסט למשתמש) ו-items (פריטים לאוסף).
${
  action.output === 'text'
    ? 'הפעולה הזו מייצרת טקסט בלבד — החזר items ריק.'
    : `פריטים נכנסים לאוסף "${collection?.label}" (${collection?.itemLabel}). סטטוסים אפשריים: ${collection?.statuses.join(
        ', ',
      )}. ${collection?.hasTimecode ? 'שדה at הוא חותמת זמן/מיקום.' : 'השאר at ריק.'}${
        action.output === 'items' ? ' הפעולה הזו מייצרת פריטים בלבד — החזר text ריק.' : ''
      }`
}
כתוב בעברית. בלי הקדמות, בלי סיכומים על מה שאתה עומד לעשות.`

  const userContent = [
    renderPrompt(action.prompt, spec, values, controls),
    '',
    '--- מצב הלוח כרגע ---',
    itemsContext(spec, items),
  ].join('\n')

  const message = await client(apiKey).messages.create({
    model: MODEL,
    max_tokens: 16000,
    system,
    output_config: {
      effort: 'medium',
      format: { type: 'json_schema', schema: ACTION_RESULT_JSON_SCHEMA as Record<string, unknown> },
    },
    messages: [{ role: 'user', content: userContent }],
  })

  if (message.stop_reason === 'refusal') {
    throw new Error('המודל סירב לענות על הבקשה הזו.')
  }

  const parsed = parseJson(textOf(message)) as {
    text?: unknown
    items?: unknown
  }

  const rawItems = Array.isArray(parsed.items) ? parsed.items : []
  return {
    text: typeof parsed.text === 'string' ? parsed.text.trim() : '',
    items: rawItems.map((raw) => {
      const item = (raw ?? {}) as Record<string, unknown>
      return {
        title: typeof item.title === 'string' ? item.title.trim() : 'פריט',
        detail: typeof item.detail === 'string' && item.detail.trim() ? item.detail.trim() : undefined,
        status: typeof item.status === 'string' && item.status.trim() ? item.status.trim() : undefined,
        at: typeof item.at === 'string' && item.at.trim() ? item.at.trim() : undefined,
        tags: Array.isArray(item.tags)
          ? item.tags.filter((t): t is string => typeof t === 'string' && t.trim().length > 0)
          : undefined,
      }
    }),
  }
}
