"use client";

import { useMemo, useState } from "react";

import { zoneLabel } from "@/lib/types";
import type {
  AutonomyLevel,
  ControlValues,
  Device,
  RangeControl,
  RunResult,
} from "@/lib/types";

/**
 * בדיקת פקד — ההרצה שמכריעה אם נוב הוא פקד או קישוט.
 *
 * מריצה את אותו קלט בדיוק בשלושה מצבים של פקד אחד, ומציגה את התוצאות זו
 * לצד זו. אם ההבדל בין העמודות לא ניכר ולא עקבי — הפקד לא באמת שולט
 * במכשיר, וכדאי להפוך אותו לבורר בדיד או לוותר עליו.
 */

type SweepRun = {
  value: number;
  result: RunResult | null;
  error: string | null;
};

/** מפתח יציב לפריט, כדי להשוות בין הרצות בלי להיתפס לניסוח */
function itemKey(area: string, target: string): string {
  return `${area.trim()}|${target.trim()}`.toLowerCase();
}

export function SweepPanel({
  device,
  values,
  autonomy,
  inputs,
}: {
  device: Device;
  values: ControlValues;
  autonomy: AutonomyLevel;
  inputs: Record<string, string>;
}) {
  const rangeControls = useMemo(
    () =>
      device.controls.filter(
        (control): control is RangeControl =>
          control.kind === "knob" || control.kind === "fader",
      ),
    [device.controls],
  );

  const [controlId, setControlId] = useState(rangeControls[0]?.id ?? "");
  const control =
    rangeControls.find((item) => item.id === controlId) ?? rangeControls[0];

  const [points, setPoints] = useState<number[]>(() =>
    control ? spread(control) : [],
  );
  const [runs, setRuns] = useState<SweepRun[]>([]);
  const [busy, setBusy] = useState(false);

  const missingInput = device.inputs.some(
    (field) => field.required && !(inputs[field.id] ?? "").trim(),
  );

  const pickControl = (id: string) => {
    setControlId(id);
    const next = rangeControls.find((item) => item.id === id);
    if (next) setPoints(spread(next));
    setRuns([]);
  };

  const runSweep = async () => {
    if (!control || missingInput) return;
    setBusy(true);
    setRuns(points.map((value) => ({ value, result: null, error: null })));

    // סדרתי בכוונה — שלוש קריאות במקביל נוטות להיתקל במגבלת קצב
    for (let index = 0; index < points.length; index += 1) {
      const value = points[index];
      let run: SweepRun = { value, result: null, error: null };

      try {
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            deviceId: device.id,
            values: { ...values, [control.id]: value },
            autonomy,
            inputs,
          }),
        });
        const payload = (await response.json()) as RunResult & {
          error?: string;
        };
        run = response.ok
          ? { value, result: payload, error: null }
          : { value, result: null, error: payload.error ?? "ההרצה נכשלה." };
      } catch {
        run = { value, result: null, error: "לא הצלחתי להגיע לשרת." };
      }

      setRuns((previous) =>
        previous.map((item, i) => (i === index ? run : item)),
      );
    }

    setBusy(false);
  };

  const comparison = useMemo(() => {
    const completed = runs.filter((run) => run.result);
    if (completed.length < 2) return null;

    const keySets = completed.map(
      (run) =>
        new Set(
          run.result!.items.map((item) => itemKey(item.area, item.target)),
        ),
    );
    const all = new Set(keySets.flatMap((set) => [...set]));

    let shared = 0;
    let unique = 0;
    for (const key of all) {
      const hits = keySets.filter((set) => set.has(key)).length;
      if (hits === keySets.length) shared += 1;
      if (hits === 1) unique += 1;
    }

    return { shared, unique, total: all.size };
  }, [runs]);

  if (!control) {
    return (
      <p className="text-sm text-[var(--muted)]">
        למכשיר הזה אין פקד רציף לבדיקה.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[12px] leading-relaxed text-[var(--muted)]">
        אותו קלט, שלושה מצבים של פקד אחד. אם העמודות יוצאות כמעט זהות — הפקד
        לא שולט במכשיר באמת, וכדאי להפוך אותו לבורר עם מצבים בדידים.
      </p>

      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="engraved">פקד לבדיקה</span>
          <select
            value={control.id}
            onChange={(event) => pickControl(event.target.value)}
            className="rounded-lg border border-[var(--line)] bg-[#0f1113] px-3 py-2 text-xs outline-none focus:border-[var(--muted)]"
          >
            {rangeControls.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        {points.map((point, index) => (
          <label key={index} className="flex flex-col gap-1.5">
            <span className="engraved">מצב {index + 1}</span>
            <input
              type="number"
              value={point}
              min={control.min}
              max={control.max}
              step={control.step}
              onChange={(event) =>
                setPoints((previous) =>
                  previous.map((item, i) =>
                    i === index ? Number(event.target.value) : item,
                  ),
                )
              }
              className="w-24 rounded-lg border border-[var(--line)] bg-[#0f1113] px-3 py-2 text-xs tabular-nums outline-none focus:border-[var(--muted)]"
            />
          </label>
        ))}

        <button
          type="button"
          onClick={runSweep}
          disabled={busy || missingInput}
          className="rounded-lg px-4 py-2 text-xs font-medium text-[#14161a] transition disabled:opacity-50"
          style={{ background: device.accent }}
        >
          {busy ? "מריץ…" : "הרץ בדיקה"}
        </button>

        {missingInput ? (
          <span className="text-xs text-[var(--muted)]">
            מלא קודם את הקלט למעלה.
          </span>
        ) : null}
      </div>

      {comparison ? (
        <div className="rounded-lg border border-[var(--line)] bg-[#0f1113] px-4 py-3 text-[12px]">
          <span className="engraved">חפיפה בין ההרצות</span>
          <p className="mt-1">
            {comparison.shared} פריטים הופיעו בכל המצבים ·{" "}
            {comparison.unique} הופיעו במצב אחד בלבד · {comparison.total} פריטים
            שונים בסך הכל.
            {comparison.unique === 0 ? (
              <strong className="text-[var(--alert)]">
                {" "}
                אין הבדל אמיתי בין המצבים — הפקד לא משפיע.
              </strong>
            ) : null}
          </p>
        </div>
      ) : null}

      {runs.length > 0 ? (
        <div className="grid gap-3 lg:grid-cols-3">
          {runs.map((run, index) => (
            <SweepColumn
              key={index}
              control={control}
              run={run}
              accent={device.accent}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SweepColumn({
  control,
  run,
  accent,
}: {
  control: RangeControl;
  run: SweepRun;
  accent: string;
}) {
  const zone = zoneLabel(control, run.value);
  const result = run.result;
  const avg = result?.items.length
    ? Math.round(
        result.items.reduce((sum, item) => sum + item.confidence, 0) /
          result.items.length,
      )
    : 0;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-[var(--line)] bg-[var(--panel-3)] p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="lcd rounded px-2 py-0.5 text-[11px] tabular-nums">
          {control.label} {run.value}
          {control.unit ?? ""}
        </span>
        {zone ? (
          <span className="text-[10px] text-[var(--muted)]">{zone}</span>
        ) : null}
      </div>

      {run.error ? (
        <p className="text-[12px] text-[var(--alert)]">{run.error}</p>
      ) : !result ? (
        <p className="text-[12px] text-[var(--muted)]">ממתין…</p>
      ) : (
        <>
          <p className="text-[11px] text-[var(--muted)]">
            {result.items.length} פריטים · ודאות ממוצעת {avg}% ·{" "}
            {result.missing.length} שאלות פתוחות
          </p>
          <ul className="flex flex-col gap-1">
            {result.items.map((item, index) => (
              <li
                key={index}
                className="rounded border border-[var(--line)] bg-[#0f1113] px-2 py-1.5 text-[11px] leading-snug"
              >
                <span style={{ color: accent }}>{item.area}</span> ·{" "}
                {item.target}
                <span className="block text-[var(--muted)]">{item.action}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

/** שלוש נקודות על הטווח: נמוך, אמצע, גבוה */
function spread(control: RangeControl): number[] {
  const mid = (control.min + control.max) / 2;
  const snap = (value: number) =>
    Number(
      (Math.round(value / control.step) * control.step).toFixed(4),
    );
  return [control.min, snap(mid), control.max];
}
