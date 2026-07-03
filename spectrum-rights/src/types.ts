export type UserType = 'parent' | 'adult' | 'family'
export type AgeGroup = '0-3' | '3-7' | '7-18' | '18+'
export type DiagnosisStatus = 'none' | 'in_process' | 'private' | 'public'
export type AllowanceStatus =
  | 'none'
  | 'child_disability'
  | 'general_disability'
  | 'special_services'
  | 'unknown'
export type Hmo = 'clalit' | 'maccabi' | 'meuhedet' | 'leumit' | ''
export type EducationFramework =
  | 'none'
  | 'regular'
  | 'integration'
  | 'special'
  | 'special_autism'
  | ''
export type FunctionalLevel =
  | 'independent'
  | 'partial_help'
  | 'supervision'
  | 'high_dependency'
export type YesNoUnknown = 'yes' | 'no' | 'unknown'

export interface Profile {
  userType: UserType
  ageGroup: AgeGroup
  diagnosisStatus: DiagnosisStatus
  allowanceStatus: AllowanceStatus
  city: string
  hmo: Hmo
  educationFramework: EducationFramework
  livesAtHome: YesNoUnknown
  billsInApplicantName: YesNoUnknown
  functionalLevel: FunctionalLevel
  documentsAvailable: string[]
}

export type Eligibility = 'eligible' | 'maybe' | 'no'

export type RightCategory =
  | 'allowance'
  | 'health'
  | 'municipal'
  | 'tax'
  | 'education'
  | 'transport'

export interface RightSource {
  name: string
  url: string
  lastChecked: string
  confidence: 'high' | 'medium'
}

export interface Right {
  id: string
  title: string
  shortDescription: string
  category: RightCategory
  priority: number
  eligibility: (p: Profile) => Eligibility
  eligibilityNote?: string
  requiredDocuments: string[]
  steps: string[]
  formUrl?: string
  source: RightSource
  letterTemplateId?: string
}

export type ActionStatus =
  | 'not_started'
  | 'in_progress'
  | 'submitted'
  | 'need_docs'
  | 'approved'
  | 'rejected'

export interface DocTypeDef {
  id: string
  label: string
  hint?: string
}

export interface StoredDoc {
  id: string
  name: string
  docType: string
  mimeType: string
  blob: Blob
  addedAt: string
}

export interface LetterDetails {
  fullName: string
  idNumber: string
  childName: string
  childIdNumber: string
  address: string
  phone: string
}
