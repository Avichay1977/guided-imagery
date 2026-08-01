/** סכימת טיוטת אירוע היומן. מופרדת כדי ששרת הפרוקסי יוכל לייבא אותה בלי גרירת קוד דפדפן. */
export const EVENT_DRAFT_JSON_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['summary', 'description', 'start', 'end', 'confidence', 'missing', 'source'],
  properties: {
    summary: { type: 'string', description: 'כותרת האירוע ביומן, קצרה וברורה' },
    description: { type: 'string', description: 'פירוט קצר, או מחרוזת ריקה' },
    start: {
      type: 'string',
      description: 'זמן התחלה מקומי בפורמט YYYY-MM-DDTHH:MM:SS, בלי אזור זמן',
    },
    end: { type: 'string', description: 'זמן סיום באותו פורמט' },
    confidence: {
      type: 'number',
      description: 'מידת הוודאות במועד שנקבע, בין 0 ל-1. אל תנפח — 0.4 ומטה כשמנחשים',
    },
    missing: {
      type: 'string',
      description: 'מה לא היה אפשר לקבוע מהטקסט (למשל "שעה"), או מחרוזת ריקה',
    },
    source: { type: 'string', description: 'הקטע מהטקסט שממנו נגזר המועד' },
  },
} as const
