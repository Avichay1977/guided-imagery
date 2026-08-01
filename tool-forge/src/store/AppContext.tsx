import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { EMPTY_TOOL_STATE } from '../types'
import type {
  AuditEntry,
  CollectionItem,
  PendingAction,
  RunLogEntry,
  Settings,
  ToolSpec,
  ToolState,
} from '../types'
import { newId } from '../engine/specSchema'
import { connectionFrom, type Connection } from '../engine/transport'
import {
  DEFAULT_SETTINGS,
  loadAudit,
  loadPending,
  loadSettings,
  loadStates,
  loadTools,
  saveAudit,
  savePending,
  saveSettings,
  saveStates,
  saveTools,
} from './storage'

interface AppValue {
  tools: ToolSpec[]
  settings: Settings
  /** האם פעולות ירוצו מול Claude או במצב הדגמה */
  engine: 'claude' | 'demo'
  /** המסלול אל המודל: מפתח בדפדפן, שרת, או כלום */
  connection: Connection | null
  saveTool: (spec: ToolSpec) => void
  deleteTool: (toolId: string) => void
  getState: (toolId: string) => ToolState
  setFieldValue: (toolId: string, fieldId: string, value: string) => void
  setControlValue: (toolId: string, controlId: string, value: number | boolean | string) => void
  addItems: (toolId: string, items: CollectionItem[]) => void
  updateItem: (toolId: string, itemId: string, patch: Partial<CollectionItem>) => void
  deleteItem: (toolId: string, itemId: string) => void
  clearItems: (toolId: string) => void
  addLog: (toolId: string, entry: RunLogEntry) => void
  updateSettings: (patch: Partial<Settings>) => void

  /** תור הפעולות החיצוניות שממתינות להחלטה */
  pending: PendingAction[]
  queueAction: (action: PendingAction) => void
  updateAction: (actionId: string, patch: Partial<PendingAction>) => void
  removeAction: (actionId: string) => void

  /** יומן מלא של כל מה שקרה */
  audit: AuditEntry[]
  record: (entry: Omit<AuditEntry, 'id' | 'at'>) => void
  clearAudit: () => void
}

const AppContext = createContext<AppValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [tools, setTools] = useState<ToolSpec[]>(() => loadTools())
  const [states, setStates] = useState<Record<string, ToolState>>(() => loadStates())
  const [settings, setSettings] = useState<Settings>(() => loadSettings())
  const [pending, setPending] = useState<PendingAction[]>(() => loadPending())
  const [audit, setAudit] = useState<AuditEntry[]>(() => loadAudit())

  useEffect(() => saveTools(tools), [tools])
  useEffect(() => saveStates(states), [states])
  useEffect(() => saveSettings(settings), [settings])
  useEffect(() => savePending(pending), [pending])
  useEffect(() => saveAudit(audit), [audit])

  const patchState = useCallback((toolId: string, patch: (prev: ToolState) => ToolState) => {
    setStates((prev) => ({ ...prev, [toolId]: patch(prev[toolId] ?? EMPTY_TOOL_STATE) }))
  }, [])

  const value = useMemo<AppValue>(() => {
    const connection = connectionFrom(settings)
    const engine: 'claude' | 'demo' = settings.engine === 'demo' || !connection ? 'demo' : 'claude'

    return {
      tools,
      settings,
      engine,
      connection,

      saveTool: (spec) =>
        setTools((prev) => {
          const next = { ...spec, updatedAt: new Date().toISOString() }
          const index = prev.findIndex((t) => t.id === spec.id)
          if (index === -1) return [next, ...prev]
          const copy = [...prev]
          copy[index] = next
          return copy
        }),

      deleteTool: (toolId) => {
        setTools((prev) => prev.filter((t) => t.id !== toolId))
        setStates((prev) => {
          const copy = { ...prev }
          delete copy[toolId]
          return copy
        })
      },

      getState: (toolId) => states[toolId] ?? EMPTY_TOOL_STATE,

      setFieldValue: (toolId, fieldId, fieldValue) =>
        patchState(toolId, (prev) => ({
          ...prev,
          fieldValues: { ...prev.fieldValues, [fieldId]: fieldValue },
        })),

      setControlValue: (toolId, controlId, controlValue) =>
        patchState(toolId, (prev) => ({
          ...prev,
          controlValues: { ...prev.controlValues, [controlId]: controlValue },
        })),

      addItems: (toolId, items) =>
        patchState(toolId, (prev) => ({ ...prev, items: [...items, ...prev.items] })),

      updateItem: (toolId, itemId, patch) =>
        patchState(toolId, (prev) => ({
          ...prev,
          items: prev.items.map((item) => (item.id === itemId ? { ...item, ...patch } : item)),
        })),

      deleteItem: (toolId, itemId) =>
        patchState(toolId, (prev) => ({
          ...prev,
          items: prev.items.filter((item) => item.id !== itemId),
        })),

      clearItems: (toolId) => patchState(toolId, (prev) => ({ ...prev, items: [] })),

      addLog: (toolId, entry) =>
        patchState(toolId, (prev) => ({ ...prev, log: [entry, ...prev.log].slice(0, 30) })),

      updateSettings: (patch) => setSettings((prev) => ({ ...prev, ...patch })),

      pending,
      queueAction: (action) => setPending((prev) => [action, ...prev]),
      updateAction: (actionId, patch) =>
        setPending((prev) =>
          prev.map((action) => (action.id === actionId ? { ...action, ...patch } : action)),
        ),
      removeAction: (actionId) => setPending((prev) => prev.filter((a) => a.id !== actionId)),

      audit,
      record: (entry) =>
        setAudit((prev) =>
          [{ ...entry, id: newId('log'), at: new Date().toISOString() }, ...prev].slice(0, 200),
        ),
      clearAudit: () => setAudit([]),
    }
  }, [tools, states, settings, pending, audit, patchState])

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp(): AppValue {
  const context = useContext(AppContext)
  if (!context) throw new Error('useApp חייב להיות בתוך AppProvider')
  return context
}

/** ערכי ברירת מחדל של בקרות, ממוזגים עם מה שהמשתמש שינה. */
export function resolveControlValues(
  spec: ToolSpec,
  stored: Record<string, number | boolean | string>,
): Record<string, number | boolean | string> {
  const values: Record<string, number | boolean | string> = {}
  for (const control of spec.controls) {
    values[control.id] = control.id in stored ? stored[control.id] : control.default
  }
  return values
}

export function makeItem(
  collectionId: string,
  raw: { title: string; detail?: string; status?: string; at?: string; tags?: string[] },
  fallbackStatus: string,
): CollectionItem {
  return {
    id: newId('item'),
    collectionId,
    title: raw.title,
    detail: raw.detail,
    status: raw.status ?? fallbackStatus,
    at: raw.at,
    tags: raw.tags,
    createdAt: new Date().toISOString(),
  }
}

export { DEFAULT_SETTINGS }
