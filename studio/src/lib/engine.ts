import {
  AUTONOMY_RULES,
  AUTONOMY_LABELS,
  zoneLabel,
  type AutonomyLevel,
  type Control,
  type ControlValues,
  type Device,
} from "@/lib/types";

/**
 * בניית ההוראה למנוע ה־AI מתוך הגדרת המכשיר ומצב הפקדים.
 *
 * הפונקציה משותפת לשרת ולממשק: המשתמש רואה בדיוק את ההוראה שנשלחת,
 * כדי שהמכשיר יישאר קופסה שקופה ולא קסם.
 */

function renderControl(control: Control, raw: unknown): string | null {
  switch (control.kind) {
    case "knob":
    case "fader": {
      const value = typeof raw === "number" ? raw : control.defaultValue;
      const zone = zoneLabel(control, value);
      const shown = zone ? `${value}${control.unit ?? ""} (${zone})` : `${value}${control.unit ?? ""}`;
      return control.promptTemplate.replaceAll("{value}", String(value)) + ` [מצב הפקד: ${shown}]`;
    }
    case "toggle": {
      const on = typeof raw === "boolean" ? raw : control.defaultValue;
      if (on) return control.promptTemplate;
      return control.offPromptTemplate ?? null;
    }
    case "selector": {
      const value = typeof raw === "string" ? raw : control.defaultValue;
      const option = control.options.find((item) => item.value === value);
      return control.promptTemplate
        .replaceAll("{value}", value)
        .concat(option ? ` [מצב הפקד: ${option.label}]` : "");
    }
  }
}

export function buildSystemPrompt(
  device: Device,
  values: ControlValues,
  autonomy: AutonomyLevel,
): string {
  const controlLines = device.controls
    .map((control) => {
      const line = renderControl(control, values[control.id]);
      return line ? `- ${control.label}: ${line}` : null;
    })
    .filter((line): line is string => line !== null);

  return [
    device.role,
    "",
    "## מצב הפקדים",
    "הפקדים נקבעו על ידי המשתמש. הם מחייבים אותך.",
    ...controlLines,
    "",
    "## חוקים",
    ...device.rules.map((rule) => `- ${rule}`),
    `- רמת אוטונומיה: ${AUTONOMY_LABELS[autonomy]}. ${AUTONOMY_RULES[autonomy]}`,
    "- אם משהו חסר או לא ברור — אל תשלים אותו מהדמיון. רשום אותו כמידע חסר.",
    "",
    "## פלט",
    device.outputBrief,
    "החזר JSON בלבד, בהתאם לסכימה. כל הטקסט בעברית.",
  ].join("\n");
}

export function buildUserPrompt(
  device: Device,
  inputs: Record<string, string>,
): string {
  return device.inputs
    .map((field) => {
      const value = (inputs[field.id] ?? "").trim();
      return `### ${field.label}\n${value || "(לא סופק)"}`;
    })
    .join("\n\n");
}
