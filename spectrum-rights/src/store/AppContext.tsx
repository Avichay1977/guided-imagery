import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import type { ActionStatus, Profile, StoredDoc } from '../types'
import { loadActions, loadProfile, saveActions, saveProfile, clearProfile } from './storage'
import { deleteDoc, listDocs, saveDoc } from './docsDb'

interface AppContextValue {
  profile: Profile | null
  setProfile: (p: Profile) => void
  resetProfile: () => void
  actions: Record<string, ActionStatus>
  setActionStatus: (rightId: string, status: ActionStatus) => void
  docs: StoredDoc[]
  addDoc: (doc: StoredDoc) => Promise<void>
  removeDoc: (id: string) => Promise<void>
  ownedDocTypes: string[]
}

const AppContext = createContext<AppContextValue | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [profile, setProfileState] = useState<Profile | null>(() => loadProfile())
  const [actions, setActions] = useState<Record<string, ActionStatus>>(() => loadActions())
  const [docs, setDocs] = useState<StoredDoc[]>([])

  useEffect(() => {
    listDocs()
      .then(setDocs)
      .catch(() => setDocs([]))
  }, [])

  const setProfile = useCallback((p: Profile) => {
    saveProfile(p)
    setProfileState(p)
  }, [])

  const resetProfile = useCallback(() => {
    clearProfile()
    setProfileState(null)
    setActions({})
  }, [])

  const setActionStatus = useCallback((rightId: string, status: ActionStatus) => {
    setActions((prev) => {
      const next = { ...prev, [rightId]: status }
      saveActions(next)
      return next
    })
  }, [])

  const addDoc = useCallback(async (doc: StoredDoc) => {
    await saveDoc(doc)
    setDocs(await listDocs())
  }, [])

  const removeDoc = useCallback(async (id: string) => {
    await deleteDoc(id)
    setDocs(await listDocs())
  }, [])

  const ownedDocTypes = useMemo(() => {
    const fromProfile = profile?.documentsAvailable ?? []
    const fromVault = docs.map((d) => d.docType)
    return Array.from(new Set([...fromProfile, ...fromVault]))
  }, [profile, docs])

  const value = useMemo(
    () => ({
      profile,
      setProfile,
      resetProfile,
      actions,
      setActionStatus,
      docs,
      addDoc,
      removeDoc,
      ownedDocTypes,
    }),
    [profile, setProfile, resetProfile, actions, setActionStatus, docs, addDoc, removeDoc, ownedDocTypes],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
