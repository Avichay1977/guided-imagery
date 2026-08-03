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
  MAX_VERSIONS_PER_TOOL,
  describeChanges,
  specsDiffer,
  type ToolVersion,
} from '../engine/versions'
import { appendUsage, type UsageEvent, type UsageKind } from '../engine/usage'
import {
  DEFAULT_SETTINGS,
  loadArchived,
  loadAudit,
  loadPending,
  loadSettings,
  loadStates,
  loadTools,
  loadUsage,
  loadVersions,
  saveArchived,
  saveAudit,
  savePending,
  saveSettings,
  saveStates,
  saveTools,
  saveUsage,
  saveVersions,
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

  /** גרסאות קודמות של כל כלי — מה השתנה ואיך חוזרים אחורה */
  versionsFor: (toolId: string) => ToolVersion[]
  restoreVersion: (versionId: string) => void

  /**
   * יומן שימוש מקומי — מה נפתח ומתי. קיים כדי שההצעות יתבססו על מה שקרה
   * ולא על ניחוש, ואינו יוצא מהמכשיר.
   */
  usage: UsageEvent[]
  recordUsage: (toolId: string, kind: UsageKind) => void
  /** כלים שהמשתמש בחר להוריד מהמדף. לא נמחקים. */
  archived: string[]
  setArchived: (toolId: string, value: boolean) => void

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
  const [versions, setVersions] = useState<ToolVersion[]>(() => loadVersions())
  const [usage, setUsage] = useState<UsageEvent[]>(() => loadUsage())
  const [archived, setArchivedList] = useState<string[]>(() => loadArchived())

  useEffect(() => saveTools(tools), [tools])
  useEffect(() => saveStates(states), [states])
  useEffect(() => saveSettings(settings), [settings])
  useEffect(() => savePending(pending), [pending])
  useEffect(() => saveAudit(audit), [audit])
  useEffect(() => saveVersions(versions), [versions])
  useEffect(() => saveUsage(usage), [usage])
  useEffect(() => saveArchived(archived), [archived])

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

          // שמירת הגרסה הקודמת לפני הדריסה — רק אם התוכן באמת השתנה
          const previous = prev[index]
          if (specsDiffer(previous, next)) {
            setVersions((history) => {
              const mine = history.filter((entry) => entry.toolId === spec.id)
              const entry: ToolVersion = {
                id: newId('ver'),
                toolId: spec.id,
                version: mine.length + 1,
                spec: previous,
                at: new Date().toISOString(),
                changes: describeChanges(previous, next),
              }
              const kept = [entry, ...mine].slice(0, MAX_VERSIONS_PER_TOOL)
              return [...history.filter((e) => e.toolId !== spec.id), ...kept]
            })
          }

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

      versionsFor: (toolId) =>
        versions
          .filter((entry) => entry.toolId === toolId)
          .sort((a, b) => b.version - a.version),

      /**
       * שחזור מחזיר את המפרט הישן דרך saveTool, ולכן הוא עצמו נשמר כגרסה חדשה.
       * אפשר תמיד לבטל גם את השחזור.
       */
      restoreVersion: (versionId) => {
        const entry = versions.find((v) => v.id === versionId)
        if (!entry) return
        setTools((prev) => {
          const index = prev.findIndex((t) => t.id === entry.toolId)
          if (index === -1) return prev
          const current = prev[index]
          const restored = { ...entry.spec, id: current.id, updatedAt: new Date().toISOString() }
          if (specsDiffer(current, restored)) {
            setVersions((history) => {
              const mine = history.filter((v) => v.toolId === entry.toolId)
              const snapshot: ToolVersion = {
                id: newId('ver'),
                toolId: entry.toolId,
                version: mine.length + 1,
                spec: current,
                at: new Date().toISOString(),
                changes: [`שוחזרה גרסה ${entry.version}`],
              }
              const kept = [snapshot, ...mine].slice(0, MAX_VERSIONS_PER_TOOL)
              return [...history.filter((v) => v.toolId !== entry.toolId), ...kept]
            })
          }
          const copy = [...prev]
          copy[index] = restored
          return copy
        })
        setAudit((prev) =>
          [
            {
              id: newId('log'),
              at: new Date().toISOString(),
              kind: 'action' as const,
              message: `שוחזרה גרסה ${entry.version} של "${entry.spec.name}"`,
            },
            ...prev,
          ].slice(0, 200),
        )
      },

      usage,
      recordUsage: (toolId, kind) =>
        setUsage((prev) => appendUsage(prev, { at: new Date().toISOString(), toolId, kind })),
      archived,
      setArchived: (toolId, value) =>
        setArchivedList((prev) =>
          value ? (prev.includes(toolId) ? prev : [...prev, toolId]) : prev.filter((id) => id !== toolId),
        ),

      audit,
      record: (entry) =>
        setAudit((prev) =>
          [{ ...entry, id: newId('log'), at: new Date().toISOString() }, ...prev].slice(0, 200),
        ),
      clearAudit: () => setAudit([]),
    }
  }, [tools, states, settings, pending, audit, versions, usage, archived, patchState])

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
