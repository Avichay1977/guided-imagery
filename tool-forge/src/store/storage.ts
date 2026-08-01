import type { AuditEntry, PendingAction, Settings, ToolSpec, ToolState } from '../types'
import type { ToolVersion } from '../engine/versions'
import { normalizeSpec } from '../engine/specSchema'

const KEYS = {
  tools: 'toolforge.tools.v1',
  states: 'toolforge.states.v1',
  settings: 'toolforge.settings.v1',
  pending: 'toolforge.pending.v1',
  audit: 'toolforge.audit.v1',
  versions: 'toolforge.versions.v1',
} as const

export const DEFAULT_SETTINGS: Settings = {
  apiKey: '',
  engine: 'auto',
  serverUrl: '',
  serverToken: '',
  googleClientId: '',
  // ברירת מחדל בטוחה: שום דבר לא יוצא החוצה עד שמכבים את זה ביודעין
  simulate: true,
}

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
    serverUrl: typeof stored.serverUrl === 'string' ? stored.serverUrl : DEFAULT_SETTINGS.serverUrl,
    serverToken:
      typeof stored.serverToken === 'string' ? stored.serverToken : DEFAULT_SETTINGS.serverToken,
    googleClientId:
      typeof stored.googleClientId === 'string' ? stored.googleClientId : DEFAULT_SETTINGS.googleClientId,
    // רק ערך מפורש false מכבה סימולציה — כל מצב אחר נשאר בטוח
    simulate: stored.simulate === false ? false : true,
  }
}

export function saveSettings(settings: Settings): void {
  write(KEYS.settings, settings)
}

export function loadPending(): PendingAction[] {
  const raw = read<PendingAction[]>(KEYS.pending, [])
  return Array.isArray(raw) ? raw : []
}

export function savePending(pending: PendingAction[]): void {
  write(KEYS.pending, pending)
}

export function loadAudit(): AuditEntry[] {
  const raw = read<AuditEntry[]>(KEYS.audit, [])
  return Array.isArray(raw) ? raw : []
}

export function saveAudit(audit: AuditEntry[]): void {
  write(KEYS.audit, audit)
}

export function loadVersions(): ToolVersion[] {
  const raw = read<ToolVersion[]>(KEYS.versions, [])
  return Array.isArray(raw) ? raw : []
}

export function saveVersions(versions: ToolVersion[]): void {
  write(KEYS.versions, versions)
}
