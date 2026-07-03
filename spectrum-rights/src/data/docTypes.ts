import type { DocTypeDef } from '../types'

export const DOC_TYPES: DocTypeDef[] = [
  { id: 'medical_diagnosis', label: 'אבחון רפואי (פסיכיאטר ילדים / נוירולוג / רופא התפתחותי)' },
  { id: 'psych_diagnosis', label: 'אבחון פסיכולוגי' },
  { id: 'diagnostic_tool_report', label: 'דו״ח כלי אבחון (ADOS / CARS / GARS / ADI)' },
  { id: 'school_confirmation', label: 'אישור לימודים / אישור מסגרת' },
  { id: 'ni_decision', label: 'החלטת ביטוח לאומי' },
  { id: 'committee_protocol', label: 'פרוטוקול ועדה' },
  { id: 'arnona_bill', label: 'חשבון ארנונה אחרון' },
  { id: 'water_bill', label: 'חשבון מים אחרון' },
  { id: 'electricity_bill', label: 'חשבון חשמל אחרון' },
  { id: 'disability_card', label: 'תעודת נכה' },
  { id: 'id_appendix', label: 'תעודת זהות + ספח' },
  { id: 'form_101', label: 'טופס 101 / תלוש שכר' },
  { id: 'hmo_docs', label: 'סיכומים רפואיים מקופת החולים' },
  { id: 'bank_confirmation', label: 'אישור ניהול חשבון בנק' },
]

export function docLabel(id: string): string {
  return DOC_TYPES.find((d) => d.id === id)?.label ?? id
}
