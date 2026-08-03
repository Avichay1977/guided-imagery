/**
 * תמונות — הקלט השני של המערכת, אחרי טקסט.
 *
 * תמונה נשמרת כ-data URL ולא כקובץ, כי היא צריכה לשרוד רענון דף ולהיכנס
 * ל-localStorage יחד עם שאר מצב הכלי. זה מגביל את הגודל, ולכן כל תמונה
 * מוקטנת לפני שמירה — גם כדי שהאחסון לא יתפוצץ וגם כדי שלא נשלח למודל
 * מגה־פיקסלים שהוא לא צריך.
 *
 * המגבלות למטה הן של Anthropic Messages API: התמונה נשלחת כבלוק
 * `image` עם source מסוג base64, והפורמטים המותרים הם ארבעה בלבד.
 */

export const SUPPORTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'] as const

/** הצלע הארוכה שאליה מוקטנת תמונה לפני שמירה */
export const MAX_EDGE = 1568

/** גג לכל תמונה אחרי הקטנה — מעבר לזה נדחית, כדי לא לפוצץ את האחסון */
export const MAX_BYTES = 3_000_000

export interface ImagePayload {
  mediaType: string
  /** base64 בלי הקידומת data: */
  data: string
}

/** מפרק data URL לחלקים שה-API מצפה להם. מחזיר null אם זה לא data URL של תמונה. */
export function parseDataUrl(value: string): ImagePayload | null {
  const match = /^data:(image\/[a-zA-Z+]+);base64,(.+)$/.exec(value.trim())
  if (!match) return null
  const mediaType = match[1] === 'image/jpg' ? 'image/jpeg' : match[1]
  if (!SUPPORTED_IMAGE_TYPES.includes(mediaType as (typeof SUPPORTED_IMAGE_TYPES)[number])) {
    return null
  }
  return { mediaType, data: match[2] }
}

export function isImageValue(value: string): boolean {
  return parseDataUrl(value) !== null
}

/** אורך משוער בבתים של מחרוזת base64 */
export function approximateBytes(base64: string): number {
  return Math.floor((base64.length * 3) / 4)
}

/**
 * קורא קובץ, מקטין אותו, ומחזיר data URL.
 * מקטין רק כשצריך; שומר יחס גובה-רוחב; ממיר כל פורמט לא נתמך ל-PNG.
 */
export async function fileToDataUrl(file: File): Promise<string> {
  if (!file.type.startsWith('image/')) {
    throw new Error('אפשר להעלות תמונות בלבד.')
  }

  const bitmap = await createImageBitmap(file)
  const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height))
  const width = Math.round(bitmap.width * scale)
  const height = Math.round(bitmap.height * scale)

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('הדפדפן לא אפשר עיבוד תמונה.')
  context.drawImage(bitmap, 0, 0, width, height)
  bitmap.close?.()

  // JPEG לצילומים, PNG לכל השאר — שקיפות לא שורדת JPEG
  const keepsAlpha = file.type === 'image/png' || file.type === 'image/webp'
  const url = canvas.toDataURL(keepsAlpha ? 'image/png' : 'image/jpeg', 0.85)

  const parsed = parseDataUrl(url)
  if (!parsed) throw new Error('לא הצלחנו לקרוא את התמונה.')
  if (approximateBytes(parsed.data) > MAX_BYTES) {
    throw new Error('התמונה גדולה מדי גם אחרי הקטנה. נסו תמונה קטנה יותר.')
  }
  return url
}
