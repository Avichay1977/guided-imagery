/**
 * מאגר הבדיקות — ההודעות שהמערכת צריכה להתמודד איתן.
 *
 * המסמכים דורשים מאגר שמכסה לא רק את המקרה הנקי אלא גם את הבלגן: תאריך יחסי,
 * שעה חסרה, כמה מועדים, עברית ואנגלית מעורבות, ניסוח מבולבל, והודעה שאין בה
 * שום פעולה. הבדיקות לא בודקות ניסוח מדויק של פלט — הן בודקות **תכונות**:
 * שהמערכת לא מנחשת כשחסר מידע, שהיא מסמנת מה חסר, ושהיא לא ממציאה פעולות.
 */

export interface DateCase {
  /** מה נכתב */
  text: string
  /** האם אמור להיקבע תאריך בוודאות סבירה */
  hasDate: boolean
  /** האם אמורה להיקבע שעה */
  hasTime: boolean
  note: string
}

export const DATE_CASES: DateCase[] = [
  { text: 'פגישה ביום שלישי ב-14:00', hasDate: true, hasTime: true, note: 'יום ושעה מפורשים' },
  { text: 'נדבר מחר ב-9:30', hasDate: true, hasTime: true, note: 'תאריך יחסי' },
  { text: 'מחרתיים ב-11:00 אצל רואה החשבון', hasDate: true, hasTime: true, note: 'מחרתיים' },
  { text: 'היום ב-18:00 אימון', hasDate: true, hasTime: true, note: 'היום' },
  { text: 'ביום חמישי נסגור את זה', hasDate: true, hasTime: false, note: 'יום בלי שעה' },
  { text: 'צריך לדבר בשבוע הבא', hasDate: false, hasTime: false, note: 'מעורפל לגמרי' },
  { text: 'שיחה ב-10:00', hasDate: false, hasTime: true, note: 'שעה בלי יום' },
  { text: 'תזכיר לי להתקשר', hasDate: false, hasTime: false, note: 'בלי מועד בכלל' },
  { text: 'meeting on יום רביעי at 16:00', hasDate: true, hasTime: true, note: 'עברית ואנגלית' },
  { text: 'פגישה ב-25:99', hasDate: false, hasTime: false, note: 'שעה לא חוקית — אסור לקבל' },
  { text: 'ביום שני ב-08:15 ואז ביום שלישי ב-12:00', hasDate: true, hasTime: true, note: 'כמה מועדים — נלקח הראשון' },
  { text: 'אולי נתראה מתישהו', hasDate: false, hasTime: false, note: 'ללא התחייבות' },
]

/** הודעות גולמיות לבדיקת חילוץ פריטים במצב הדגמה. */
export const EXTRACTION_CASES: Array<{ text: string; minItems: number; note: string }> = [
  {
    text: 'בדקה 1:24 הווקאל נעלם. הבס חזק מדי.\nב-2:40 הסולו קדימה.',
    minItems: 3,
    note: 'שלוש הערות עם חותמות זמן',
  },
  { text: 'צריך לשלם 240 ש"ח על הסופר', minItems: 1, note: 'סכום כסף' },
  { text: 'משפט אחד בלבד', minItems: 1, note: 'קלט מינימלי' },
  { text: '   ', minItems: 0, note: 'קלט ריק — אסור להמציא פריטים' },
]

/** תיאורים לבדיקת בחירת התבנית במנוע המקומי. */
export const PATTERN_CASES: Array<{ brief: string; expected: string | null; note: string }> = [
  {
    brief: 'אני מוזיקאי ומקבל הערות על מיקס מלקוחות',
    expected: 'audio',
    note: 'מיקס + מוזיקאי',
  },
  { brief: 'לזהות פגישות בהודעות ולהכניס ליומן', expected: 'meetings', note: 'פגישות + יומן' },
  { brief: 'לנהל לידים והצעות מחיר ללקוחות', expected: 'clients', note: 'לקוחות + הצעת מחיר' },
  { brief: 'לפרק את כל המשימות שיש לי בראש', expected: 'tasks', note: 'משימות' },
  { brief: 'לכתוב פוסטים לרשתות', expected: 'content', note: 'פוסט + רשתות' },
  { brief: 'לתעד אימונים והרגלים', expected: 'health', note: 'אימון + הרגלים' },
  { brief: 'לסווג הוצאות ולראות תקציב', expected: 'money', note: 'הוצאות + תקציב' },
  { brief: 'לבנות כרטיסיות לימוד למבחן', expected: 'learning', note: 'לימוד + מבחן' },
  {
    brief: 'משהו לגמרי אחר שאין לו תחום מוכר במערכת',
    expected: null,
    note: 'ללא תחום — נופל לתבנית הכללית',
  },
]
