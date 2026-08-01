import type { CollectionItem } from '../types'
import { localTimeZone } from './googleCalendar'
import { callClaude, type Connection } from './transport'

/**
 * הפיכת פריט ברשימה לטיוטת אירוע יומן.
 *
 * העיקרון: המערכת לא מנחשת. כשאין מספיק מידע כדי לקבוע מועד, היא מחזירה ביטחון
 * נמוך ומסמנת מה חסר — כרטיס האישור מציג את זה למשתמש לתיקון לפני שמשהו מבוצע.
 */

export interface EventDraft {
  summary: string
  description: string
  /** ISO 8601 מקומי, למשל 2026-08-04T14:00:00 */
  start: string
  end: string
  /** 0–1. מתחת ל-0.5 הכרטיס מסומן כדורש בדיקה ידנית. */
  confidence: number
  /** מה המערכת לא הצליחה לקבוע בוודאות */
  missing: string
  /** מאיזה טקסט זה נגזר — provenance */
  source: string
}

const HEBREW_DAYS: Record<string, number> = {
  ראשון: 0,
  שני: 1,
  שלישי: 2,
  רביעי: 3,
  חמישי: 4,
  שישי: 5,
  שבת: 6,
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}

function toLocalIso(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}:00`
}

function addMinutes(iso: string, minutes: number): string {
  const date = new Date(iso)
  date.setMinutes(date.getMinutes() + minutes)
  return toLocalIso(date)
}

/**
 * פענוח מקומי — עובד בלי רשת ובלי מפתח, ומכסה את הניסוחים העבריים הנפוצים:
 * "יום שלישי", "מחר", "היום", ושעה בפורמט 14:00.
 */
export function draftEventLocally(item: CollectionItem): EventDraft {
  const text = [item.at ?? '', item.title, item.detail ?? ''].join(' ')
  const now = new Date()
  const target = new Date(now)
  const missing: string[] = []
  let confidence = 0.3

  const dayMatch = text.match(/יום\s+(ראשון|שני|שלישי|רביעי|חמישי|שישי|שבת)/)
  if (/מחרתיים/.test(text)) {
    target.setDate(now.getDate() + 2)
    confidence += 0.3
  } else if (/מחר/.test(text)) {
    target.setDate(now.getDate() + 1)
    confidence += 0.3
  } else if (/היום/.test(text)) {
    confidence += 0.3
  } else if (dayMatch) {
    const wanted = HEBREW_DAYS[dayMatch[1]]
    // תמיד המופע הבא של אותו יום, כולל אם הוא היום עצמו בשבוע הבא
    const delta = (wanted - now.getDay() + 7) % 7 || 7
    target.setDate(now.getDate() + delta)
    confidence += 0.3
  } else {
    missing.push('תאריך')
    target.setDate(now.getDate() + 1)
  }

  const timeMatch = text.match(/\b(\d{1,2}):(\d{2})\b/)
  if (timeMatch) {
    const hours = Number(timeMatch[1])
    const minutes = Number(timeMatch[2])
    if (hours < 24 && minutes < 60) {
      target.setHours(hours, minutes, 0, 0)
      confidence += 0.3
    } else {
      missing.push('שעה')
      target.setHours(9, 0, 0, 0)
    }
  } else {
    missing.push('שעה')
    target.setHours(9, 0, 0, 0)
  }

  const start = toLocalIso(target)
  return {
    summary: item.title.replace(/\s+/g, ' ').slice(0, 120),
    description: item.detail ?? '',
    start,
    end: addMinutes(start, 60),
    confidence: missing.length ? Math.min(confidence, 0.45) : Math.min(confidence, 0.8),
    missing: missing.join(', '),
    source: item.at ? `${item.at} · ${item.title}` : item.title,
  }
}


/** אותה משימה, אבל עם מודל — מטפל בניסוחים שהפענוח המקומי מפספס. */
export async function draftEventWithClaude(
  item: CollectionItem,
  connection: Connection,
): Promise<EventDraft> {
  const now = new Date()
  const weekday = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'][now.getDay()]

  const text = await callClaude(connection, 'draftEvent', [
    item,
    toLocalIso(now),
    weekday,
    localTimeZone(),
  ])

  const parsed = JSON.parse(text) as Partial<EventDraft>
  const fallback = draftEventLocally(item)

  const start =
    typeof parsed.start === 'string' && !Number.isNaN(new Date(parsed.start).getTime())
      ? parsed.start
      : fallback.start
  const end =
    typeof parsed.end === 'string' && !Number.isNaN(new Date(parsed.end).getTime())
      ? parsed.end
      : addMinutes(start, 60)

  return {
    summary: parsed.summary?.trim() || fallback.summary,
    description: parsed.description?.trim() ?? '',
    start,
    end,
    confidence:
      typeof parsed.confidence === 'number'
        ? Math.max(0, Math.min(1, parsed.confidence))
        : fallback.confidence,
    missing: parsed.missing?.trim() ?? '',
    source: parsed.source?.trim() || fallback.source,
  }
}

export function formatWhen(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('he-IL', {
    weekday: 'long',
    day: 'numeric',
    month: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** ISO מקומי -> ערך ל-input[type=datetime-local] ובחזרה */
export function toInputValue(iso: string): string {
  return iso.slice(0, 16)
}

export function fromInputValue(value: string): string {
  return value.length === 16 ? `${value}:00` : value
}
