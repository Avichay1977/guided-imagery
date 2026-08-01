import Anthropic from '@anthropic-ai/sdk'
import type { Settings } from '../types'
import { callClaude, connectionFrom, parseJson } from './transport'
import { CALENDAR_SCOPE, calendarBase, isConnected, probeCalendar } from './googleCalendar'

/**
 * בדיקת חיבור — ההרצה האמיתית הראשונה, בלי לגלות את הבעיה באמצע עבודה.
 *
 * כל בדיקה מחזירה לא רק "נכשל" אלא **מה לעשות**. רוב התקלות בהתחברות ל-Google
 * ול-Anthropic הן הגדרה חסרה במקום אחר (origin שלא אושר, API שלא הופעל, מפתח
 * שלא נשמר), והודעת השגיאה הגולמית כמעט אף פעם לא אומרת את זה בפירוש.
 */

export interface CheckResult {
  id: string
  label: string
  status: 'ok' | 'fail' | 'skip'
  detail: string
  /** מה לעשות כדי לתקן — מוצג רק כשיש כישלון */
  fix?: string
}

function ok(id: string, label: string, detail: string): CheckResult {
  return { id, label, status: 'ok', detail }
}

function fail(id: string, label: string, detail: string, fix: string): CheckResult {
  return { id, label, status: 'fail', detail, fix }
}

function skip(id: string, label: string, detail: string): CheckResult {
  return { id, label, status: 'skip', detail }
}

/** ממפה שגיאה מ-Anthropic לסיבה ולתיקון, לפי המסלול שדרכו היא הגיעה. */
export function explainClaudeFailure(error: unknown, mode: 'direct' | 'server'): CheckResult {
  const label = 'קריאה ל-Claude'
  const message = error instanceof Error ? error.message : String(error)

  if (error instanceof Anthropic.AuthenticationError || /401|x-api-key|authentication/i.test(message)) {
    return fail(
      'claude.call',
      label,
      'המפתח נדחה על ידי Anthropic.',
      mode === 'direct'
        ? 'בדקו שהמפתח הועתק במלואו (מתחיל ב-sk-ant-) ושנשמר בלחיצה על "שמירת מפתח".'
        : 'המפתח שיושב על השרת אינו תקף. בדקו את ANTHROPIC_API_KEY בסביבת הפריסה.',
    )
  }

  if (error instanceof Anthropic.PermissionDeniedError || /403|permission/i.test(message)) {
    return fail(
      'claude.call',
      label,
      'למפתח אין הרשאה למודל המבוקש.',
      'בדקו בקונסולת Anthropic שלחשבון יש גישה ל-claude-opus-5, או שיש בו יתרה.',
    )
  }

  if (error instanceof Anthropic.RateLimitError || /429|rate.?limit/i.test(message)) {
    return fail('claude.call', label, 'חריגה ממכסת הבקשות.', 'נסו שוב בעוד דקה.')
  }

  if (/לשרת חסר ANTHROPIC_API_KEY/.test(message)) {
    return fail(
      'claude.call',
      label,
      'השרת עונה, אבל אין לו מפתח.',
      'הגדירו ANTHROPIC_API_KEY במשתני הסביבה של הפריסה, ופרסו מחדש.',
    )
  }

  if (/אין הרשאה לשרת הזה/.test(message)) {
    return fail(
      'claude.call',
      label,
      'השרת דחה את אסימון הגישה.',
      'האסימון בהגדרות חייב להיות זהה ל-TOOLFORGE_ACCESS_TOKEN שבסביבת השרת.',
    )
  }

  if (error instanceof Anthropic.APIConnectionError || /fetch|network|CORS|Failed to fetch/i.test(message)) {
    return fail(
      'claude.call',
      label,
      'לא הצלחנו להגיע ליעד.',
      mode === 'direct'
        ? 'בדקו חיבור לאינטרנט. אם האפליקציה רצה בתוך iframe או תחת הרחבה שחוסמת בקשות, המסלול הישיר לא יעבוד — השתמשו במסלול השרת.'
        : 'בדקו שכתובת השרת נכונה ושהוא מחזיר כותרות CORS (TOOLFORGE_ALLOWED_ORIGIN).',
    )
  }

  if (/400|invalid_request/i.test(message)) {
    return fail(
      'claude.call',
      label,
      `הבקשה נדחתה: ${message}`,
      'זו תקלה בבנייה של הבקשה ולא בהגדרות שלכם. שווה לדווח עם הטקסט המלא.',
    )
  }

  return fail('claude.call', label, message, 'שגיאה לא מוכרת — שמרו את הטקסט המלא לבדיקה.')
}

/** ממפה שגיאה מ-Google Calendar לסיבה ולתיקון. */
export function explainCalendarFailure(error: unknown): CheckResult {
  const label = 'קריאה ל-Google Calendar'
  const message = error instanceof Error ? error.message : String(error)

  if (/has not been used in project|is disabled|SERVICE_DISABLED|accessNotConfigured/i.test(message)) {
    return fail(
      'calendar.call',
      label,
      'Calendar API לא מופעל בפרויקט.',
      'ב-Google Cloud Console: APIs & Services → Enable APIs → Google Calendar API → Enable. ההפעלה יכולה לקחת דקה.',
    )
  }

  if (/insufficient|ACCESS_TOKEN_SCOPE_INSUFFICIENT|scope/i.test(message)) {
    return fail(
      'calendar.call',
      label,
      'לאסימון אין את ההרשאה הנדרשת.',
      `ודאו שמסך ההסכמה כולל את ההרשאה ${CALENDAR_SCOPE}, ואז התנתקו והתחברו מחדש.`,
    )
  }

  if (/פגה|401|UNAUTHENTICATED/i.test(message)) {
    return fail(
      'calendar.call',
      label,
      'האסימון פג או נדחה.',
      'האסימון נשמר בזיכרון בלבד ופג אחרי כשעה או ברענון דף. לחצו "התחברות ליומן" שוב.',
    )
  }

  if (/403|forbidden/i.test(message)) {
    return fail(
      'calendar.call',
      label,
      'Google דחה את הבקשה.',
      'לרוב זה origin שלא אושר. הוסיפו את הכתובת שממנה האפליקציה רצה ל-Authorized JavaScript origins ב-OAuth client.',
    )
  }

  return fail('calendar.call', label, message, 'בדקו את הגדרות ה-OAuth client ב-Google Cloud.')
}

/** מריץ את כל הבדיקות ומחזיר דוח מלא. */
export async function runDiagnostics(settings: Settings): Promise<CheckResult[]> {
  const results: CheckResult[] = []
  const connection = connectionFrom(settings)

  // ── מסלול אל המודל ────────────────────────────────────────────────
  if (!connection) {
    results.push(
      skip(
        'transport',
        'מסלול אל Claude',
        'לא מוגדר מפתח ולא כתובת שרת — האפליקציה במצב הדגמה.',
      ),
    )
  } else if (connection.mode === 'server') {
    results.push(ok('transport', 'מסלול אל Claude', `דרך השרת ${connection.url}`))
  } else {
    results.push(ok('transport', 'מסלול אל Claude', 'מפתח מקומי בדפדפן'))
  }

  if (connection) {
    try {
      const text = await callClaude(connection, 'probe', [])
      const parsed = parseJson(text) as { ok?: unknown }
      results.push(
        parsed.ok === true
          ? ok('claude.call', 'קריאה ל-Claude', 'הקריאה הצליחה והתשובה חזרה במבנה שביקשנו.')
          : fail(
              'claude.call',
              'קריאה ל-Claude',
              `הקריאה עברה אבל התשובה לא במבנה הצפוי: ${text.slice(0, 120)}`,
              'ה-structured outputs לא נאכף. שווה לדווח עם הטקסט המלא.',
            ),
      )
    } catch (error) {
      results.push(explainClaudeFailure(error, connection.mode))
    }
  } else {
    results.push(skip('claude.call', 'קריאה ל-Claude', 'אין מסלול מוגדר.'))
  }

  // ── Google Calendar ───────────────────────────────────────────────
  if (!settings.googleClientId.trim()) {
    results.push(
      skip('calendar.clientId', 'Google Client ID', 'לא הוגדר — היומן לא זמין.'),
    )
    results.push(skip('calendar.call', 'קריאה ל-Google Calendar', 'אין Client ID.'))
    return results
  }

  results.push(ok('calendar.clientId', 'Google Client ID', settings.googleClientId.slice(0, 24) + '…'))

  if (!isConnected()) {
    results.push(
      skip(
        'calendar.call',
        'קריאה ל-Google Calendar',
        'אין אסימון פעיל. לחצו "התחברות ליומן" ואז הריצו שוב.',
      ),
    )
    return results
  }

  try {
    const count = await probeCalendar()
    results.push(
      ok(
        'calendar.call',
        'קריאה ל-Google Calendar',
        `החיבור עובד (נקראו ${count} אירועים קרובים). ${calendarBase()}`,
      ),
    )
  } catch (error) {
    results.push(explainCalendarFailure(error))
  }

  return results
}
