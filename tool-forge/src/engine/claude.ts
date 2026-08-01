import type { CollectionItem, SpecAction, ToolSpec } from '../types'
import type { ActionResult } from './localActions'
import { newId, normalizeSpec } from './specSchema'
import { callClaude, parseJson, type Connection } from './transport'

export { describeApiError } from './transport'
export { renderPrompt } from './requests'

/** בונה ToolSpec מתיאור חופשי. */
export async function buildSpecWithClaude(brief: string, connection: Connection): Promise<ToolSpec> {
  const text = await callClaude(connection, 'buildSpec', [brief])

  return normalizeSpec(parseJson(text), {
    id: newId('tool'),
    sourceBrief: brief.trim(),
    builtBy: 'claude',
  })
}

/** מריץ פעולה אחת של הלוח ומחזיר טקסט ופריטים. */
export async function runActionWithClaude(
  spec: ToolSpec,
  action: SpecAction,
  values: Record<string, string>,
  controls: Record<string, number | boolean | string>,
  items: CollectionItem[],
  connection: Connection,
): Promise<ActionResult> {
  const text = await callClaude(connection, 'runAction', [spec, action, values, controls, items])

  const parsed = parseJson(text) as { text?: unknown; items?: unknown }
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
