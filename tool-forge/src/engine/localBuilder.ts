import type { ToolSpec } from '../types'
import { DOMAIN_PATTERNS, genericPattern, type DomainPattern } from './patterns'
import { newId, normalizeSpec } from './specSchema'

export interface PatternMatch {
  pattern: DomainPattern | null
  score: number
  matched: string[]
}

/** ניקוד גס: כל מילת מפתח שמופיעה בתיאור שווה נקודה. */
export function pickPattern(brief: string): PatternMatch {
  const text = brief.toLowerCase()
  let best: PatternMatch = { pattern: null, score: 0, matched: [] }

  for (const pattern of DOMAIN_PATTERNS) {
    const matched = pattern.keywords.filter((k) => text.includes(k.toLowerCase()))
    if (matched.length > best.score) {
      best = { pattern, score: matched.length, matched }
    }
  }
  return best
}

/**
 * בונה ToolSpec מתיאור חופשי — בלי רשת, בלי מפתח API.
 * בוחר את התבנית הקרובה ביותר ומלביש עליה את ההקשר של המשתמש.
 */
export function buildSpecLocally(brief: string): { spec: ToolSpec; match: PatternMatch } {
  const match = pickPattern(brief)
  const base = match.pattern ? match.pattern.build() : genericPattern()
  const trimmed = brief.trim()

  const spec = normalizeSpec(
    {
      ...base,
      systemPrompt: trimmed
        ? `${base.systemPrompt}\n\nכך תיאר המשתמש את מה שהוא צריך, בלשונו:\n"${trimmed}"\nהתאם את הפלט להקשר הזה.`
        : base.systemPrompt,
    },
    { id: newId('tool'), sourceBrief: trimmed || undefined, builtBy: 'local' },
  )

  return { spec, match }
}

/** התבניות המוכנות שמוצגות בגלריה. */
export function starterSpecs(): ToolSpec[] {
  return DOMAIN_PATTERNS.map((pattern) =>
    normalizeSpec(pattern.build(), {
      id: newId('tool'),
      sourceBrief: pattern.sampleBrief,
      builtBy: 'local',
    }),
  )
}
