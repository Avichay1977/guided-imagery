/**
 * טיפוסי הליבה של האולפן.
 *
 * "מכשיר" (Device) הוא יחידת העבודה הבסיסית: ממשק חזותי (נובים, סליידרים,
 * מתגים), חוקים ברורים, ורמת אוטונומיה. ה־AI הוא מודול בתוך המכשיר — לא
 * ההפך. המכשיר קובע מה נכנס, מה יוצא, ומה אסור.
 */

export type ControlKind = "knob" | "fader" | "toggle" | "selector";

export interface BaseControl {
  id: string;
  label: string;
  /** הסבר קצר שמופיע במצב עריכה */
  hint?: string;
  /** כיצד הפקד מתורגם להוראה ל־AI. `{value}` מוחלף בערך המוצג. */
  promptTemplate: string;
}

export interface RangeControl extends BaseControl {
  kind: "knob" | "fader";
  min: number;
  max: number;
  step: number;
  defaultValue: number;
  /** יחידה להצגה בלבד, למשל "%" */
  unit?: string;
  /** תוויות איכותיות לפי אחוז מהטווח, למשל ["עדין", "מאוזן", "אגרסיבי"] */
  zones?: string[];
}

export interface ToggleControl extends BaseControl {
  kind: "toggle";
  defaultValue: boolean;
  /** ההוראה נשלחת רק כשהמתג דלוק */
  offPromptTemplate?: string;
}

export interface SelectorControl extends BaseControl {
  kind: "selector";
  options: { value: string; label: string }[];
  defaultValue: string;
}

export type Control = RangeControl | ToggleControl | SelectorControl;

export type ControlValue = number | boolean | string;
export type ControlValues = Record<string, ControlValue>;

/** רמת אוטונומיה — כמה המכשיר רשאי לעשות בעצמו */
export type AutonomyLevel = 1 | 2 | 3;

export const AUTONOMY_LABELS: Record<AutonomyLevel, string> = {
  1: "הצעה בלבד",
  2: "טיוטה לאישור",
  3: "ביצוע אחרי אישור",
};

export const AUTONOMY_RULES: Record<AutonomyLevel, string> = {
  1: "אתה מציע בלבד. אל תנסח פעולות כאילו בוצעו. אל תמציא נתונים חסרים.",
  2: "אתה מכין טיוטה מוכנה לאישור אנושי. סמן כל פריט שדורש החלטה של האדם.",
  3: "אתה מכין תוכנית ביצוע מסודרת. שום פעולה לא מתבצעת ללא אישור מפורש של המשתמש.",
};

/** שדה קלט שהמשתמש ממלא לפני הרצה */
export interface InputField {
  id: string;
  label: string;
  placeholder?: string;
  multiline?: boolean;
  required?: boolean;
}

/** שלב בשרשרת העיבוד — משמש גם לתצוגת החיבורים */
export interface PipelineStage {
  id: string;
  label: string;
  detail: string;
  /** האם השלב דורש אישור אנושי */
  gate?: boolean;
}

export interface Device {
  id: string;
  name: string;
  subtitle: string;
  /** תיאור התפקיד — נכנס לפרומפט המערכת */
  role: string;
  accent: string;
  inputs: InputField[];
  controls: Control[];
  rules: string[];
  autonomy: AutonomyLevel;
  pipeline: PipelineStage[];
  /** סכימת הפלט (JSON Schema) שהמנוע חייב לעמוד בה */
  outputSchema: Record<string, unknown>;
  /** תיאור הפלט במילים, לצורך הפרומפט */
  outputBrief: string;
}

export interface Preset {
  id: string;
  deviceId: string;
  name: string;
  values: ControlValues;
  autonomy: AutonomyLevel;
  createdAt: string;
}

/** פריט תיקון בודד שמוחזר מהמכשיר */
export interface FixItem {
  area: string;
  target: string;
  action: string;
  priority: "גבוהה" | "בינונית" | "נמוכה";
  confidence: number;
  quote: string;
  needsDecision: boolean;
}

export interface RunResult {
  summary: string;
  items: FixItem[];
  missing: string[];
  meta?: {
    model: string;
    inputTokens: number;
    outputTokens: number;
    ms: number;
  };
}

export interface RunLogEntry {
  id: string;
  deviceId: string;
  at: string;
  values: ControlValues;
  inputs: Record<string, string>;
  result: RunResult;
}

export function defaultValues(device: Device): ControlValues {
  const values: ControlValues = {};
  for (const control of device.controls) {
    values[control.id] = control.defaultValue;
  }
  return values;
}

/** תווית איכותית לפי מיקום הערך בטווח */
export function zoneLabel(control: RangeControl, value: number): string | null {
  if (!control.zones?.length) return null;
  const ratio = (value - control.min) / (control.max - control.min);
  const index = Math.min(
    control.zones.length - 1,
    Math.floor(ratio * control.zones.length),
  );
  return control.zones[index];
}
