/**
 * קטלוג היכולות — הרשימה הסגורה של מה שכלי יכול לעשות.
 *
 * זו הנקודה שבה ה-AI מפסיק להיות מתכנת ונעשה מרכיב: הוא לא מנסח התנהגות חופשית,
 * הוא בוחר יכולת מהקטלוג ומספק לה הוראה. יכולת שלא נמצאת כאן לא קיימת, גם אם
 * המודל ביקש אותה — normalizeSpec פשוט לא ייצור אותה.
 *
 * כל יכולת מצהירה על עצמה: מה היא מקבלת, מה היא מחזירה, האם היא משנה משהו בעולם,
 * האם היא הפיכה, ואיזו הרשאה היא דורשת. ההצהרה הזו היא מה שמייצר את מסך ההרשאות
 * של הכלי — אין מצב שהממשק מבטיח דבר אחד והמנוע עושה אחר.
 */

export type PermissionId = 'read.input' | 'write.list' | 'draft.text' | 'calendar.write'

export interface Capability {
  id: string
  label: string
  /** תיאור למודל: מתי לבחור ביכולת הזו */
  description: string
  /** מה הפעולה מחזירה */
  output: 'text' | 'items' | 'both'
  /** האם היא משנה משהו מחוץ לאפליקציה */
  mutatesWorld: boolean
  /** האם היא מחייבת אישור מפורש לפני ביצוע */
  requiresApproval: boolean
  /** האם אפשר לבטל אותה אחרי שבוצעה */
  reversible: boolean
  permissions: PermissionId[]
}

export const CAPABILITIES: Capability[] = [
  {
    id: 'extract.items',
    label: 'חילוץ פריטים',
    description: 'פירוק טקסט גולמי לפריטים נפרדים שאפשר לפעול לפיהם, ושמירתם באוסף.',
    output: 'both',
    mutatesWorld: false,
    requiresApproval: false,
    reversible: true,
    permissions: ['read.input', 'write.list'],
  },
  {
    id: 'compose.text',
    label: 'ניסוח טקסט',
    description: 'כתיבת טיוטה מוכנה למשתמש — תשובה, הודעה, פוסט. לא נשלחת לאף אחד.',
    output: 'text',
    mutatesWorld: false,
    requiresApproval: false,
    reversible: true,
    permissions: ['read.input', 'draft.text'],
  },
  {
    id: 'summarize',
    label: 'סיכום ותמונת מצב',
    description: 'סיכום של הקלט או של מה שכבר יש באוסף, כולל מספרים ומגמות.',
    output: 'text',
    mutatesWorld: false,
    requiresApproval: false,
    reversible: true,
    permissions: ['read.input'],
  },
  {
    id: 'plan',
    label: 'תכנון וסדר עדיפויות',
    description: 'הצעת סדר עבודה, שיבוץ או צעד הבא על בסיס הפריטים הקיימים.',
    output: 'text',
    mutatesWorld: false,
    requiresApproval: false,
    reversible: true,
    permissions: ['read.input'],
  },
  {
    id: 'classify',
    label: 'סיווג ותיוג',
    description: 'מיון פריטים לקטגוריות, רמות דחיפות או סטטוסים.',
    output: 'items',
    mutatesWorld: false,
    requiresApproval: false,
    reversible: true,
    permissions: ['read.input', 'write.list'],
  },
  {
    id: 'calendar.createEvent',
    label: 'יצירת אירוע ביומן',
    description:
      'הוספת אירוע ל-Google Calendar. משנה מצב מחוץ לאפליקציה ולכן עוברת תמיד דרך תור אישורים.',
    output: 'text',
    mutatesWorld: true,
    requiresApproval: true,
    reversible: true,
    permissions: ['read.input', 'calendar.write'],
  },
]

export const CAPABILITY_IDS = CAPABILITIES.map((capability) => capability.id)

export function getCapability(id: string | undefined): Capability | undefined {
  return CAPABILITIES.find((capability) => capability.id === id)
}

export const PERMISSION_LABELS: Record<PermissionId, string> = {
  'read.input': 'קריאת הטקסט שאתם מזינים',
  'write.list': 'הוספה ועדכון של פריטים ברשימות הכלי',
  'draft.text': 'ניסוח טיוטות להצגה בלבד',
  'calendar.write': 'יצירת אירועים ביומן — דורש אישור לכל אירוע',
}

/**
 * יכולות שהמנוע יודע להריץ ישירות מכפתור בלוח.
 * יכולת ששייכת לתור האישורים לא נכנסת לכאן — היא מופעלת מפריט, לא מכפתור,
 * וממילא לא תתבצע בלי אישור.
 */
export function isDirectlyRunnable(capability: Capability): boolean {
  return !capability.mutatesWorld && !capability.requiresApproval
}

/**
 * ניחוש היכולת של פעולה ישנה שנשמרה לפני שהקטלוג היה קיים.
 *
 * ההסקה נשענת קודם כול על סוג הפלט, שהוא עובדה, ורק אחר כך על רמזים בתווית.
 * רמזי תווית מופעלים רק כשהפלט הוא טקסט — שם באמת יש הבדל בין ניסוח, סיכום
 * ותכנון. פעולה שמייצרת פריטים היא תמיד חילוץ או סיווג, לא משנה איך קראו לה.
 */
export function inferCapability(action: { output?: string; id?: string; label?: string }): string {
  const hint = `${action.id ?? ''} ${action.label ?? ''}`

  if (action.output === 'items' || action.output === 'both') {
    return /classif|סווג|תיוג|קטגור/i.test(hint) ? 'classify' : 'extract.items'
  }

  if (/summar|trend|סיכום|תמונת מצב|מגמ/i.test(hint)) return 'summarize'
  if (/plan|slot|schedule|שיבוץ|תכנון|סדר עבודה|צעד הבא/i.test(hint)) return 'plan'
  return 'compose.text'
}
