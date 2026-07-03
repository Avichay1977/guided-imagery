import type { ActionStatus, LetterDetails, Profile } from '../types'

const PROFILE_KEY = 'srp_profile'
const ACTIONS_KEY = 'srp_actions'
const DETAILS_KEY = 'srp_letter_details'

export function loadProfile(): Profile | null {
  try {
    const raw = localStorage.getItem(PROFILE_KEY)
    return raw ? (JSON.parse(raw) as Profile) : null
  } catch {
    return null
  }
}

export function saveProfile(p: Profile): void {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(p))
}

export function clearProfile(): void {
  localStorage.removeItem(PROFILE_KEY)
  localStorage.removeItem(ACTIONS_KEY)
}

export function loadActions(): Record<string, ActionStatus> {
  try {
    const raw = localStorage.getItem(ACTIONS_KEY)
    return raw ? (JSON.parse(raw) as Record<string, ActionStatus>) : {}
  } catch {
    return {}
  }
}

export function saveActions(a: Record<string, ActionStatus>): void {
  localStorage.setItem(ACTIONS_KEY, JSON.stringify(a))
}

export const EMPTY_DETAILS: LetterDetails = {
  fullName: '',
  idNumber: '',
  childName: '',
  childIdNumber: '',
  address: '',
  phone: '',
}

export function loadLetterDetails(): LetterDetails {
  try {
    const raw = localStorage.getItem(DETAILS_KEY)
    return raw ? { ...EMPTY_DETAILS, ...(JSON.parse(raw) as LetterDetails) } : EMPTY_DETAILS
  } catch {
    return EMPTY_DETAILS
  }
}

export function saveLetterDetails(d: LetterDetails): void {
  localStorage.setItem(DETAILS_KEY, JSON.stringify(d))
}
