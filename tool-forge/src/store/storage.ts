import type { Settings, ToolSpec, ToolState } from '../types'
import { normalizeSpec } from '../engine/specSchema'

const KEYS = {
  tools: 'toolforge.tools.v1',
  states: 'toolforge.states.v1',
  settings: 'toolforge.settings.v1',
} as const

export const DEFAULT_SETTINGS: Settings = { apiKey: '', engine: 'auto' }

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // מצב פרטי / אחסון מלא — ממשיכים בזיכרון בלבד
  }
}

export function loadTools(): ToolSpec[] {
  const raw = read<unknown[]>(KEYS.tools, [])
  if (!Array.isArray(raw)) return []
  return raw.map((item) => {
    const spec = (item ?? {}) as Partial<ToolSpec>
    return normalizeSpec(spec, {
      id: spec.id,
      createdAt: spec.createdAt,
      sourceBrief: spec.sourceBrief,
      builtBy: spec.builtBy,
    })
  })
}

export function saveTools(tools: ToolSpec[]): void {
  write(KEYS.tools, tools)
}

export function loadStates(): Record<string, ToolState> {
  return read<Record<string, ToolState>>(KEYS.states, {})
}

export function saveStates(states: Record<string, ToolState>): void {
  write(KEYS.states, states)
}

export function loadSettings(): Settings {
  const stored = read<Partial<Settings>>(KEYS.settings, {})
  return {
    apiKey: typeof stored.apiKey === 'string' ? stored.apiKey : DEFAULT_SETTINGS.apiKey,
    engine: stored.engine === 'demo' ? 'demo' : 'auto',
  }
}

export function saveSettings(settings: Settings): void {
  write(KEYS.settings, settings)
}
