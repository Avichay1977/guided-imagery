import type { CollectionItem, SpecAction, ToolSpec } from '../types'
import { ACTION_RESULT_JSON_SCHEMA, TOOL_SPEC_JSON_SCHEMA } from './specSchema'
import { CAPABILITIES, isDirectlyRunnable } from './capabilities'
import { EVENT_DRAFT_JSON_SCHEMA } from './scheduleSchema'

/**
 * בניית הבקשות ל-Claude — במקום אחד, כדי ששני הצדדים ישתמשו באותו קוד בדיוק.
 *
 * הדפדפן קורא מכאן כשהמפתח שלו מקומי, והפונקציה בצד השרת קוראת מכאן כשהמפתח
 * יושב אצלה. אין שתי גרסאות של אותו פרומפט שנפרדות עם הזמן, ואין דרך שהלקוח
 * יבקש מהשרת משהו שלא נבנה כאן.
 */

export const MODEL = 'claude-opus-5'

/** הצורות המותרות של בקשה. הלקוח שולח kind + קלט, לא פרומפט חופשי. */
export type RequestKind = 'buildSpec' | 'runAction' | 'draftEvent' | 'probe'

export interface ClaudeRequest {
  model: string
  max_tokens: number
  system: string
  output_config: { effort: 'low' | 'medium' | 'high'; format: { type: 'json_schema'; schema: Record<string, unknown> } }
  messages: Array<{ role: 'user'; content: string }>
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

/**
 * בקשת בדיקה מינימלית. קיימת כדי שאפשר יהיה לאמת שלושה דברים בקריאה אחת:
 * שהמפתח תקף, שהמודל זמין, ושה-structured outputs שלנו מתקבל — וזה בדיוק מה
 * שאי אפשר היה לאמת בלי חשבון.
 */
export function buildProbeRequest(): ClaudeRequest {
  return {
    model: MODEL,
    max_tokens: 256,
    system: 'ענה בקצרה.',
    output_config: {
      effort: 'low',
      format: {
        type: 'json_schema',
        schema: {
          type: 'object',
          additionalProperties: false,
          required: ['ok'],
          properties: { ok: { type: 'boolean', description: 'תמיד true' } },
        },
      },
    },
    messages: [{ role: 'user', content: 'החזר {"ok": true}' }],
  }
}

export function buildSpecRequest(brief: string): ClaudeRequest {
  return {
    model: MODEL,
    max_tokens: 16000,
    system: BUILDER_SYSTEM,
    output_config: {
      effort: 'high',
      format: { type: 'json_schema', schema: TOOL_SPEC_JSON_SCHEMA as unknown as Record<string, unknown> },
    },
    messages: [{ role: 'user', content: `בנה לי לוח שליטה לפי התיאור הבא:\n\n"""${brief.trim()}"""` }],
  }
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

export function buildActionRequest(
  spec: ToolSpec,
  action: SpecAction,
  values: Record<string, string>,
  controls: Record<string, number | boolean | string>,
  items: CollectionItem[],
): ClaudeRequest {
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

  return {
    model: MODEL,
    max_tokens: 16000,
    system,
    output_config: {
      effort: 'medium',
      format: {
        type: 'json_schema',
        schema: ACTION_RESULT_JSON_SCHEMA as unknown as Record<string, unknown>,
      },
    },
    messages: [
      {
        role: 'user',
        content: [
          renderPrompt(action.prompt, spec, values, controls),
          '',
          '--- מצב הלוח כרגע ---',
          itemsContext(spec, items),
        ].join('\n'),
      },
    ],
  }
}

export function buildEventRequest(
  item: Pick<CollectionItem, 'title' | 'at' | 'detail'>,
  now: string,
  weekday: string,
  timeZone: string,
): ClaudeRequest {
  return {
    model: MODEL,
    max_tokens: 4000,
    system: `אתה ממיר פריט מרשימת מטלות לטיוטת אירוע ביומן.
עכשיו: ${now} (${weekday}), אזור זמן ${timeZone}.
כללים: אם המועד לא נקבע במפורש — אל תנחש בביטחון. החזר את ההשערה הסבירה ביותר עם confidence נמוך ופרט ב-missing מה חסר.
זמנים תמיד עתידיים ביחס לעכשיו. משך ברירת מחדל: שעה.`,
    output_config: {
      effort: 'low',
      format: {
        type: 'json_schema',
        schema: EVENT_DRAFT_JSON_SCHEMA as unknown as Record<string, unknown>,
      },
    },
    messages: [
      {
        role: 'user',
        content: `כותרת: ${item.title}\nחותמת: ${item.at ?? '(אין)'}\nפירוט: ${item.detail ?? '(אין)'}`,
      },
    ],
  }
}
