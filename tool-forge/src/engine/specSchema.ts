import type {
  ActionOutput,
  ControlType,
  FieldType,
  SpecAction,
  SpecCollection,
  SpecControl,
  SpecField,
  ToolSpec,
} from '../types'

/**
 * הסכימה שנשלחת ל-Claude ב-structured outputs.
 * כל השדות חובה (כך דורשת סכימה קפדנית) — ערכים "ריקים" מנוקים ב-normalizeSpec.
 * default של בקרה נשלח תמיד כמחרוזת כדי להימנע מאיחוד טיפוסים.
 */
export const TOOL_SPEC_JSON_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['name', 'tagline', 'icon', 'systemPrompt', 'fields', 'controls', 'actions', 'collections'],
  properties: {
    name: { type: 'string', description: 'שם קצר לכלי, בעברית' },
    tagline: { type: 'string', description: 'משפט אחד שמסביר מה הכלי עושה' },
    icon: { type: 'string', description: 'אמוג׳י יחיד' },
    systemPrompt: {
      type: 'string',
      description: 'הקשר קבוע ל-AI: מי המשתמש, מה התחום, איך לענות. בעברית.',
    },
    fields: {
      type: 'array',
      description: 'הקלטים שהמשתמש ממלא לפני הפעלת פעולה (1-5)',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'label', 'type', 'placeholder', 'options', 'required'],
        properties: {
          id: { type: 'string', description: 'מזהה באנגלית, snake_case' },
          label: { type: 'string' },
          type: { type: 'string', enum: ['text', 'longtext', 'select', 'date', 'number'] },
          placeholder: { type: 'string', description: 'טקסט רמז, או מחרוזת ריקה' },
          options: { type: 'array', items: { type: 'string' }, description: 'רק ל-select, אחרת []' },
          required: { type: 'boolean' },
        },
      },
    },
    controls: {
      type: 'array',
      description: 'סליידרים/מתגים/בוררים שמכוונים את אופי הפלט (1-4)',
      items: {
        type: 'object',
        additionalProperties: false,
        required: [
          'id',
          'label',
          'type',
          'hint',
          'min',
          'max',
          'step',
          'lowLabel',
          'highLabel',
          'options',
          'default',
        ],
        properties: {
          id: { type: 'string', description: 'מזהה באנגלית, snake_case' },
          label: { type: 'string' },
          type: { type: 'string', enum: ['slider', 'toggle', 'choice'] },
          hint: { type: 'string' },
          min: { type: 'number', description: 'סליידר בלבד, אחרת 0' },
          max: { type: 'number', description: 'סליידר בלבד, אחרת 0' },
          step: { type: 'number', description: 'סליידר בלבד, אחרת 0' },
          lowLabel: { type: 'string', description: 'מה המשמעות של הקצה הנמוך' },
          highLabel: { type: 'string', description: 'מה המשמעות של הקצה הגבוה' },
          options: { type: 'array', items: { type: 'string' }, description: 'רק ל-choice, אחרת []' },
          default: {
            type: 'string',
            description: 'ערך ברירת מחדל כמחרוזת: מספר לסליידר, "true"/"false" למתג, אחת האפשרויות לבורר',
          },
        },
      },
    },
    actions: {
      type: 'array',
      description: 'הכפתורים על לוח השליטה (2-5)',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'label', 'icon', 'prompt', 'output', 'target', 'primary'],
        properties: {
          id: { type: 'string', description: 'מזהה באנגלית, snake_case' },
          label: { type: 'string' },
          icon: { type: 'string', description: 'אמוג׳י יחיד' },
          prompt: {
            type: 'string',
            description:
              'ההוראה ל-AI. אפשר לשלב ערכי שדות ובקרות עם {{field_id}}. יש לפרט מה בדיוק מצופה בפלט.',
          },
          output: {
            type: 'string',
            enum: ['text', 'items', 'both'],
            description: 'text = תשובה חופשית, items = פריטים לאוסף, both = שניהם',
          },
          target: {
            type: 'string',
            description: 'מזהה האוסף שאליו נכנסים הפריטים, או מחרוזת ריקה',
          },
          primary: { type: 'boolean', description: 'כפתור ראשי אחד בלבד' },
        },
      },
    },
    collections: {
      type: 'array',
      description: 'הזיכרון של הכלי — רשימות פריטים עם סטטוסים (1-2)',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['id', 'label', 'itemLabel', 'statuses', 'hasTimecode', 'emptyText'],
        properties: {
          id: { type: 'string', description: 'מזהה באנגלית, snake_case' },
          label: { type: 'string' },
          itemLabel: { type: 'string', description: 'שם פריט יחיד, למשל "תיקון מיקס"' },
          statuses: { type: 'array', items: { type: 'string' }, description: '2-4 סטטוסים בעברית' },
          hasTimecode: { type: 'boolean', description: 'האם לפריט יש חותמת זמן/מיקום' },
          emptyText: { type: 'string' },
        },
      },
    },
  },
} as const

/** הסכימה של תוצאת הרצת פעולה. */
export const ACTION_RESULT_JSON_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['text', 'items'],
  properties: {
    text: { type: 'string', description: 'התשובה למשתמש בעברית. מחרוזת ריקה אם הפעולה מייצרת רק פריטים.' },
    items: {
      type: 'array',
      description: 'פריטים להוספה לאוסף. מערך ריק אם אין.',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['title', 'detail', 'status', 'at', 'tags'],
        properties: {
          title: { type: 'string', description: 'שורה אחת, קצרה ומעשית' },
          detail: { type: 'string', description: 'פירוט קצר, או מחרוזת ריקה' },
          status: { type: 'string', description: 'אחד הסטטוסים של האוסף' },
          at: { type: 'string', description: 'חותמת זמן/מיקום אם יש, אחרת מחרוזת ריקה' },
          tags: { type: 'array', items: { type: 'string' } },
        },
      },
    },
  },
} as const

const FIELD_TYPES: FieldType[] = ['text', 'longtext', 'select', 'date', 'number']
const CONTROL_TYPES: ControlType[] = ['slider', 'toggle', 'choice']
const OUTPUTS: ActionOutput[] = ['text', 'items', 'both']

function str(value: unknown, fallback = ''): string {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback
}

function strList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map((v) => str(v)).filter(Boolean)
}

function num(value: unknown, fallback: number): number {
  const n = typeof value === 'string' ? Number(value) : value
  return typeof n === 'number' && Number.isFinite(n) ? n : fallback
}

function slug(value: unknown, fallback: string): string {
  const raw = str(value)
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return raw || fallback
}

export function newId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 9)}${Date.now().toString(36).slice(-4)}`
}

function normalizeField(raw: unknown, index: number): SpecField {
  const r = (raw ?? {}) as Record<string, unknown>
  const type = FIELD_TYPES.includes(r.type as FieldType) ? (r.type as FieldType) : 'text'
  const options = strList(r.options)
  return {
    id: slug(r.id, `field_${index + 1}`),
    label: str(r.label, `שדה ${index + 1}`),
    type: type === 'select' && options.length === 0 ? 'text' : type,
    placeholder: str(r.placeholder) || undefined,
    options: options.length ? options : undefined,
    required: r.required === true,
  }
}

function normalizeControl(raw: unknown, index: number): SpecControl {
  const r = (raw ?? {}) as Record<string, unknown>
  const type = CONTROL_TYPES.includes(r.type as ControlType) ? (r.type as ControlType) : 'slider'
  const options = strList(r.options)
  const id = slug(r.id, `control_${index + 1}`)
  const label = str(r.label, `בקרה ${index + 1}`)
  const hint = str(r.hint) || undefined

  if (type === 'toggle') {
    return { id, label, type, hint, default: r.default === true || str(r.default) === 'true' }
  }
  if (type === 'choice') {
    const opts = options.length ? options : ['רגיל', 'מורחב']
    const fallback = opts[0]
    const chosen = str(r.default, fallback)
    return { id, label, type, hint, options: opts, default: opts.includes(chosen) ? chosen : fallback }
  }

  const min = num(r.min, 1)
  const max = num(r.max, 5) > min ? num(r.max, 5) : min + 4
  const step = num(r.step, 1) > 0 ? num(r.step, 1) : 1
  const def = Math.min(max, Math.max(min, num(r.default, Math.round((min + max) / 2))))
  return {
    id,
    label,
    type,
    hint,
    min,
    max,
    step,
    lowLabel: str(r.lowLabel) || undefined,
    highLabel: str(r.highLabel) || undefined,
    default: def,
  }
}

function normalizeCollection(raw: unknown, index: number): SpecCollection {
  const r = (raw ?? {}) as Record<string, unknown>
  const statuses = strList(r.statuses)
  return {
    id: slug(r.id, `collection_${index + 1}`),
    label: str(r.label, 'רשימה'),
    itemLabel: str(r.itemLabel, 'פריט'),
    statuses: statuses.length ? statuses : ['פתוח', 'בוצע'],
    hasTimecode: r.hasTimecode === true,
    emptyText: str(r.emptyText) || undefined,
  }
}

function normalizeAction(raw: unknown, index: number, collectionIds: string[]): SpecAction {
  const r = (raw ?? {}) as Record<string, unknown>
  const output = OUTPUTS.includes(r.output as ActionOutput) ? (r.output as ActionOutput) : 'text'
  const target = slug(r.target, '')
  return {
    id: slug(r.id, `action_${index + 1}`),
    label: str(r.label, `פעולה ${index + 1}`),
    icon: str(r.icon) || '▶',
    prompt: str(r.prompt, 'סכם את הקלט של המשתמש בצורה מעשית.'),
    output,
    target: collectionIds.includes(target) ? target : output === 'text' ? undefined : collectionIds[0],
    primary: r.primary === true,
  }
}

/**
 * מקבל אובייקט ממקור לא בטוח (Claude / קובץ מיובא / localStorage ישן)
 * ומחזיר ToolSpec תקין שאפשר להריץ.
 */
export function normalizeSpec(raw: unknown, meta: Partial<ToolSpec> = {}): ToolSpec {
  const r = (raw ?? {}) as Record<string, unknown>
  const now = new Date().toISOString()

  const collections = (Array.isArray(r.collections) ? r.collections : []).map(normalizeCollection)
  if (collections.length === 0) {
    collections.push({
      id: 'items',
      label: 'רשימה',
      itemLabel: 'פריט',
      statuses: ['פתוח', 'בוצע'],
    })
  }
  const collectionIds = collections.map((c) => c.id)

  const fields = (Array.isArray(r.fields) ? r.fields : []).map(normalizeField)
  if (fields.length === 0) {
    fields.push({
      id: 'input',
      label: 'קלט',
      type: 'longtext',
      placeholder: 'הדביקו כאן את הטקסט הגולמי',
      required: true,
    })
  }

  const controls = (Array.isArray(r.controls) ? r.controls : []).map(normalizeControl)

  const actions = (Array.isArray(r.actions) ? r.actions : []).map((a, i) =>
    normalizeAction(a, i, collectionIds),
  )
  if (actions.length === 0) {
    actions.push({
      id: 'process',
      label: 'עבד',
      icon: '⚡',
      prompt: 'קח את הקלט של המשתמש והפוך אותו לרשימת פריטים מעשית.',
      output: 'both',
      target: collectionIds[0],
      primary: true,
    })
  }
  if (!actions.some((a) => a.primary)) actions[0].primary = true

  return {
    id: meta.id ?? newId('tool'),
    name: str(r.name, 'כלי חדש'),
    tagline: str(r.tagline, 'לוח שליטה אישי'),
    icon: str(r.icon, '🎛️'),
    systemPrompt: str(
      r.systemPrompt,
      'אתה עוזר אישי שמייצר פלט מעשי, קצר ומדויק בעברית. אל תוסיף הקדמות מיותרות.',
    ),
    fields,
    controls,
    actions,
    collections,
    createdAt: meta.createdAt ?? now,
    updatedAt: now,
    sourceBrief: meta.sourceBrief ?? (str(r.sourceBrief) || undefined),
    builtBy: meta.builtBy,
  }
}
