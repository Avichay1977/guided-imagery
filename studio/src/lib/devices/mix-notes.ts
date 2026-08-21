import type { Device } from "@/lib/types";

/**
 * המכשיר הראשון: הופך הערות חופשיות של לקוח לרשימת תיקוני מיקס מסודרת.
 *
 * זה מכשיר אמיתי ולא הדגמה: הקלט הוא טקסט אנושי מבולגן, הפלט הוא רשימת
 * פעולות שאפשר לעבוד לפיה, וכל פריט חייב להיות מעוגן בציטוט מהמקור.
 */
export const mixNotesDevice: Device = {
  id: "mix-notes",
  name: "MIX NOTES",
  subtitle: "מהערות לקוח לרשימת תיקונים",
  accent: "#f2a33c",
  role: "אתה מהנדס מיקס בכיר שמתרגם הערות חופשיות של לקוח לרשימת תיקונים מדויקת שאפשר לעבוד לפיה.",
  inputs: [
    {
      id: "track",
      label: "שם הטראק",
      placeholder: "לדוגמה: ״ערב אחד״ — מיקס 3",
    },
    {
      id: "notes",
      label: "הערות הלקוח",
      placeholder:
        "הדבק כאן את ההודעה כפי שהיא. אין צורך לסדר, לתקן או לתרגם.",
      multiline: true,
      required: true,
    },
    {
      id: "context",
      label: "רקע (לא חובה)",
      placeholder: "ז׳אנר, ייחוס, מגבלות טכניות, מה כבר נוסה",
      multiline: true,
    },
  ],
  controls: [
    {
      id: "granularity",
      kind: "knob",
      label: "רזולוציה",
      hint: "כמה פריטים לפרק מתוך אותה הערה",
      min: 1,
      max: 10,
      step: 1,
      defaultValue: 6,
      zones: ["מרוכז", "מאוזן", "מפורק"],
      promptTemplate:
        "רזולוציית פירוק: {value} מתוך 10. ככל שהערך גבוה יותר, פרק כל הערה ליותר פריטי פעולה נפרדים; ככל שהוא נמוך יותר, אחד פריטים קרובים לפריט אחד.",
    },
    {
      id: "threshold",
      kind: "knob",
      label: "סף רלוונטיות",
      hint: "כמה ברורה צריכה להיות ההערה כדי להיכנס לרשימה",
      min: 0,
      max: 100,
      step: 5,
      defaultValue: 35,
      unit: "%",
      zones: ["מכיל הכל", "סלקטיבי", "רק ודאי"],
      promptTemplate:
        "סף רלוונטיות: {value}%. אל תכניס לרשימה פריט שרמת הוודאות שלו נמוכה מהסף. פריטים שנפסלו — רשום אותם תחת מידע חסר.",
    },
    {
      id: "detail",
      kind: "fader",
      label: "עומק ניסוח",
      hint: "כמה טכני יהיה תיאור הפעולה",
      min: 0,
      max: 100,
      step: 5,
      defaultValue: 60,
      unit: "%",
      zones: ["קצר", "מעשי", "טכני מלא"],
      promptTemplate:
        "עומק ניסוח: {value}%. ב־0 כתוב משפט פעולה קצר; ב־100 כלול תדרים, יחסי dB, סוג מעבד ומיקום בשרשרת — אך רק כאשר יש לכך בסיס בהערה.",
    },
    {
      id: "grouping",
      kind: "selector",
      label: "סידור",
      options: [
        { value: "area", label: "לפי אזור" },
        { value: "priority", label: "לפי דחיפות" },
        { value: "order", label: "לפי סדר ההערה" },
      ],
      defaultValue: "area",
      promptTemplate:
        "סדר את הפריטים ברשימה לפי: {value}. (area = אזור בערבוב, priority = דחיפות, order = סדר ההופעה בהערות)",
    },
    {
      id: "quotes",
      kind: "toggle",
      label: "עיגון לציטוט",
      hint: "כל פריט חייב להישען על משפט מהמקור",
      defaultValue: true,
      promptTemplate:
        "כל פריט חייב לכלול ציטוט מדויק מתוך הערות הלקוח, מילה במילה, בשדה quote. אם אין ציטוט — הפריט לא נכנס לרשימה.",
      offPromptTemplate:
        "שדה quote יכול להיות תמצית של ההערה במקום ציטוט מדויק.",
    },
    {
      id: "flagUnclear",
      kind: "toggle",
      label: "סימון עמימות",
      hint: "פריט שדורש החלטה של אדם יסומן",
      defaultValue: true,
      promptTemplate:
        "סמן needsDecision=true בכל פריט שבו יש יותר מפרשנות אחת סבירה, או שהוא נוגע לבחירה אמנותית ולא טכנית.",
    },
  ],
  rules: [
    "אל תמציא הערות שהלקוח לא כתב.",
    "אל תשלח דבר לאף אחד ואל תבצע פעולה מחוץ להפקת הרשימה.",
    "מונחים לא ברורים של הלקוח (״שטוח״, ״קטן״, ״לא יושב״) מתורגמים לפעולה רק אם ההקשר מאפשר; אחרת הם עוברים למידע חסר.",
    "שמור על שפת הלקוח — אל תתקן טעמים, רק נסח פעולה.",
    "אם ההערות סותרות זו את זו, אל תכריע — סמן את הסתירה.",
  ],
  autonomy: 2,
  pipeline: [
    {
      id: "in",
      label: "הערות נכנסות",
      detail: "טקסט חופשי מהלקוח, כפי שהוא",
    },
    {
      id: "parse",
      label: "הבנת התוכן",
      detail: "זיהוי מה בכלל נאמר, והפרדה בין תלונה, בקשה ורושם כללי",
    },
    {
      id: "map",
      label: "מיפוי לאזור",
      detail: "כל הערה נקשרת לאזור בערבוב: ווקאל, לואו־אנד, דינמיקה, מרחב",
    },
    {
      id: "filter",
      label: "סינון לפי סף",
      detail: "פריטים מתחת לסף הוודאות יורדים לרשימת מידע חסר",
    },
    {
      id: "draft",
      label: "ניסוח פעולה",
      detail: "כל פריט מנוסח כפעולה שאפשר לבצע, ברמת העומק שנבחרה",
    },
    {
      id: "approve",
      label: "אישור המשתמש",
      detail: "שום דבר לא יוצא מכאן בלי שהאדם עבר על הרשימה",
      gate: true,
    },
  ],
  outputBrief:
    "רשימת תיקוני מיקס: תקציר קצר, פריטי פעולה, ורשימת מידע חסר שצריך לשאול עליו את הלקוח.",
  outputSchema: {
    type: "object",
    properties: {
      summary: {
        type: "string",
        description:
          "שתיים עד שלוש שורות: מה הלקוח בעצם מבקש, במילים של מהנדס.",
      },
      items: {
        type: "array",
        description: "פריטי הפעולה, מסודרים לפי הפקד 'סידור'.",
        items: {
          type: "object",
          properties: {
            area: {
              type: "string",
              description:
                "אזור בערבוב, בעברית. לדוגמה: ווקאל, לואו־אנד, דינמיקה, מרחב, אוטומציה.",
            },
            target: {
              type: "string",
              description: "הערוץ או האלמנט הספציפי שעליו פועלים.",
            },
            action: {
              type: "string",
              description: "הפעולה עצמה, מנוסחת כהוראה שאפשר לבצע.",
            },
            priority: {
              type: "string",
              enum: ["גבוהה", "בינונית", "נמוכה"],
            },
            confidence: {
              type: "integer",
              description: "0–100, כמה ברור שזו אכן הכוונה של הלקוח.",
            },
            quote: {
              type: "string",
              description: "המשפט מההערות שעליו הפריט נשען.",
            },
            needsDecision: {
              type: "boolean",
              description: "האם נדרשת הכרעה אנושית לפני ביצוע.",
            },
          },
          required: [
            "area",
            "target",
            "action",
            "priority",
            "confidence",
            "quote",
            "needsDecision",
          ],
          additionalProperties: false,
        },
      },
      missing: {
        type: "array",
        description:
          "מה חסר או לא ברור — שאלות מנוסחות שאפשר לשלוח ללקוח כמו שהן.",
        items: { type: "string" },
      },
    },
    required: ["summary", "items", "missing"],
    additionalProperties: false,
  },
};

export const devices: Device[] = [mixNotesDevice];

export function getDevice(id: string): Device | undefined {
  return devices.find((device) => device.id === id);
}
