"use client";

import { useEffect, useMemo, useState } from "react";

import { ControlSlot } from "@/components/Controls";
import { Meter } from "@/components/Meter";
import { SignalFlow } from "@/components/SignalFlow";
import { buildSystemPrompt, buildUserPrompt } from "@/lib/engine";
import { isCloudEnabled } from "@/lib/supabase";
import {
  applyOverrides,
  clearOverrides,
  deletePreset,
  loadOverrides,
  loadPresets,
  loadRuns,
  newId,
  savePreset,
  saveOverrides,
  saveRun,
  type DeviceOverrides,
} from "@/lib/storage";
import {
  AUTONOMY_LABELS,
  defaultValues,
  type AutonomyLevel,
  type ControlValue,
  type ControlValues,
  type Device,
  type Preset,
  type RunLogEntry,
  type RunResult,
} from "@/lib/types";

type Tab = "flow" | "prompt" | "history";

export function DeviceConsole({ baseDevice }: { baseDevice: Device }) {
  const [overrides, setOverrides] = useState<DeviceOverrides>({});
  const [values, setValues] = useState<ControlValues>(() =>
    defaultValues(baseDevice),
  );
  const [autonomy, setAutonomy] = useState<AutonomyLevel>(baseDevice.autonomy);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState<Tab>("flow");

  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);

  const [presets, setPresets] = useState<Preset[]>([]);
  const [presetName, setPresetName] = useState("");
  const [runs, setRuns] = useState<RunLogEntry[]>([]);

  const device = useMemo(
    () => applyOverrides(baseDevice, overrides),
    [baseDevice, overrides],
  );

  // טעינה ראשונית: שינויי משתמש, פריסטים והיסטוריה
  useEffect(() => {
    loadOverrides(baseDevice.id)
      .then((stored) => {
        setOverrides(stored);
        if (stored.autonomy) setAutonomy(stored.autonomy as AutonomyLevel);
      })
      .catch(() => setOverrides({}));

    loadPresets(baseDevice.id).then(setPresets).catch(() => setPresets([]));
    loadRuns(baseDevice.id).then(setRuns).catch(() => setRuns([]));
  }, [baseDevice.id]);

  const patchOverrides = (patch: DeviceOverrides) => {
    setOverrides((previous) => {
      const next = { ...previous, ...patch };
      saveOverrides(baseDevice.id, next);
      return next;
    });
  };

  const setControl = (id: string, value: ControlValue) => {
    setValues((previous) => ({ ...previous, [id]: value }));
  };

  const systemPrompt = useMemo(
    () => buildSystemPrompt(device, values, autonomy),
    [device, values, autonomy],
  );

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      const response = await fetch("/api/run", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          deviceId: device.id,
          values,
          autonomy,
          inputs,
        }),
      });

      const payload = (await response.json()) as RunResult & { error?: string };

      if (!response.ok) {
        setError(payload.error ?? "ההרצה נכשלה.");
        setResult(null);
        return;
      }

      setResult(payload);

      const entry: RunLogEntry = {
        id: newId(),
        deviceId: device.id,
        at: new Date().toISOString(),
        values,
        inputs,
        result: payload,
      };
      await saveRun(entry).catch(() => undefined);
      setRuns((previous) => [entry, ...previous].slice(0, 20));
    } catch {
      setError("לא הצלחתי להגיע לשרת.");
      setResult(null);
    } finally {
      setRunning(false);
    }
  };

  const storePreset = async () => {
    const name = presetName.trim();
    if (!name) return;
    const preset: Preset = {
      id: newId(),
      deviceId: device.id,
      name,
      values,
      autonomy,
      createdAt: new Date().toISOString(),
    };
    await savePreset(preset);
    setPresets((previous) => [preset, ...previous]);
    setPresetName("");
  };

  const knobs = device.controls.filter((control) => control.kind === "knob");
  const rest = device.controls.filter((control) => control.kind !== "knob");

  const avgConfidence = result?.items.length
    ? result.items.reduce((sum, item) => sum + item.confidence, 0) /
      result.items.length
    : 0;
  const decisions = result?.items.filter((item) => item.needsDecision).length ?? 0;

  const flowState: "idle" | "running" | "done" = running
    ? "running"
    : result
      ? "done"
      : "idle";

  return (
    <div className="mx-auto flex w-full max-w-[1400px] flex-col gap-4 p-4 sm:p-6">
      <ConsoleHeader
        device={device}
        editing={editing}
        onToggleEditing={() => setEditing((value) => !value)}
      />

      <div className="grid gap-4 lg:grid-cols-12">
        {/* ── פאנל הפקדים ── */}
        <section className="panel relative flex flex-col gap-5 p-5 lg:col-span-4">
          <PanelScrews />

          <div className="flex flex-wrap justify-around gap-4">
            {knobs.map((control) => (
              <ControlSlot
                key={control.id}
                control={control}
                value={values[control.id]}
                onChange={(value) => setControl(control.id, value)}
                accent={device.accent}
                disabled={running}
              />
            ))}
          </div>

          <div className="h-px bg-[var(--line)]" />

          <div className="flex flex-col gap-4">
            {rest.map((control) => (
              <ControlSlot
                key={control.id}
                control={control}
                value={values[control.id]}
                onChange={(value) => setControl(control.id, value)}
                accent={device.accent}
                disabled={running}
              />
            ))}
          </div>

          <div className="h-px bg-[var(--line)]" />

          <div className="flex flex-col gap-2">
            <span className="engraved">רמת אוטונומיה</span>
            <div className="flex gap-1 rounded-lg border border-[var(--line)] bg-[#0f1113] p-1">
              {([1, 2, 3] as AutonomyLevel[]).map((level) => {
                const active = level === autonomy;
                return (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setAutonomy(level)}
                    aria-pressed={active}
                    className="flex-1 rounded-md px-2 py-1.5 text-[11px] transition"
                    style={
                      active
                        ? {
                            background: device.accent,
                            color: "#14161a",
                            fontWeight: 500,
                          }
                        : { color: "var(--muted)" }
                    }
                  >
                    {AUTONOMY_LABELS[level]}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="h-px bg-[var(--line)]" />

          <PresetBar
            presets={presets}
            name={presetName}
            onNameChange={setPresetName}
            onSave={storePreset}
            onRecall={(preset) => {
              setValues(preset.values);
              setAutonomy(preset.autonomy);
            }}
            onDelete={async (id) => {
              await deletePreset(id);
              setPresets((previous) => previous.filter((p) => p.id !== id));
            }}
            onReset={() => {
              setValues(defaultValues(baseDevice));
              setAutonomy(baseDevice.autonomy);
            }}
          />
        </section>

        {/* ── קלט ופלט ── */}
        <section className="flex flex-col gap-4 lg:col-span-8">
          <div className="panel flex flex-col gap-4 p-5">
            <div className="flex items-center justify-between">
              <span className="engraved">קלט</span>
              <span className="text-[10px] text-[var(--muted)]">
                {isCloudEnabled() ? "מחובר לענן" : "עבודה מקומית"}
              </span>
            </div>

            {device.inputs.map((field) => (
              <label key={field.id} className="flex flex-col gap-1.5">
                <span className="text-[12px] text-[var(--muted)]">
                  {field.label}
                  {field.required ? " *" : ""}
                </span>
                {field.multiline ? (
                  <textarea
                    rows={field.id === "notes" ? 6 : 3}
                    value={inputs[field.id] ?? ""}
                    placeholder={field.placeholder}
                    onChange={(event) =>
                      setInputs((previous) => ({
                        ...previous,
                        [field.id]: event.target.value,
                      }))
                    }
                    className="w-full resize-y rounded-lg border border-[var(--line)] bg-[#0f1113] p-3 text-sm leading-relaxed outline-none placeholder:text-[#5c6068] focus:border-[var(--muted)]"
                  />
                ) : (
                  <input
                    value={inputs[field.id] ?? ""}
                    placeholder={field.placeholder}
                    onChange={(event) =>
                      setInputs((previous) => ({
                        ...previous,
                        [field.id]: event.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-[var(--line)] bg-[#0f1113] p-3 text-sm outline-none placeholder:text-[#5c6068] focus:border-[var(--muted)]"
                  />
                )}
              </label>
            ))}

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={run}
                disabled={running}
                className="rounded-lg px-5 py-2.5 text-sm font-medium text-[#14161a] transition disabled:opacity-60"
                style={{ background: device.accent }}
              >
                {running ? "מעבד…" : "הרץ מכשיר"}
              </button>
              {error ? (
                <span className="text-sm text-[var(--alert)]">{error}</span>
              ) : null}
            </div>
          </div>

          {result ? (
            <div className="panel flex flex-col gap-4 p-5">
              <div className="grid gap-4 sm:grid-cols-3">
                <Meter
                  label="ודאות ממוצעת"
                  value={avgConfidence}
                  unit="%"
                  accent={device.accent}
                />
                <Meter label="פריטים" value={result.items.length} max={20} />
                <Meter
                  label="דורש הכרעה"
                  value={decisions}
                  max={Math.max(1, result.items.length)}
                  warnAbove={Math.max(1, result.items.length) / 2}
                />
              </div>

              <div className="rounded-lg border border-[var(--line)] bg-[#0f1113] p-4">
                <span className="engraved">תקציר</span>
                <p className="mt-2 text-sm leading-relaxed">{result.summary}</p>
              </div>

              <ol className="flex flex-col gap-2">
                {result.items.map((item, index) => (
                  <li
                    key={`${item.target}-${index}`}
                    className="rounded-lg border border-[var(--line)] bg-[var(--panel-3)] p-3"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className="rounded px-2 py-0.5 text-[11px]"
                        style={{
                          background: `${device.accent}22`,
                          color: device.accent,
                        }}
                      >
                        {item.area}
                      </span>
                      <span className="text-[13px] font-medium">
                        {item.target}
                      </span>
                      <span className="text-[11px] text-[var(--muted)]">
                        דחיפות {item.priority} · ודאות {item.confidence}%
                      </span>
                      {item.needsDecision ? (
                        <span className="rounded border border-[var(--alert)] px-1.5 py-0.5 text-[10px] text-[var(--alert)]">
                          דורש הכרעה
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-2 text-sm leading-relaxed">{item.action}</p>
                    {item.quote ? (
                      <p className="mt-2 border-r-2 border-[var(--line)] pr-2 text-[12px] text-[var(--muted)]">
                        ״{item.quote}״
                      </p>
                    ) : null}
                  </li>
                ))}
              </ol>

              {result.missing.length > 0 ? (
                <div className="rounded-lg border border-[var(--line)] bg-[#0f1113] p-4">
                  <span className="engraved">מידע חסר — לשאול את הלקוח</span>
                  <ul className="mt-2 flex list-disc flex-col gap-1 pr-5 text-sm">
                    {result.missing.map((question, index) => (
                      <li key={index}>{question}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {result.meta ? (
                <p className="text-[11px] text-[var(--muted)]">
                  {result.meta.model} · {result.meta.inputTokens} טוקני קלט ·{" "}
                  {result.meta.outputTokens} טוקני פלט ·{" "}
                  {(result.meta.ms / 1000).toFixed(1)} שניות
                </p>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>

      {/* ── תצוגות משנה ── */}
      <section className="panel flex flex-col gap-4 p-5">
        <div className="flex flex-wrap gap-1 rounded-lg border border-[var(--line)] bg-[#0f1113] p-1 sm:w-fit">
          {(
            [
              ["flow", "שרשרת אותות"],
              ["prompt", "ההוראה שנשלחת"],
              ["history", `היסטוריה (${runs.length})`],
            ] as [Tab, string][]
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              aria-pressed={tab === id}
              className="rounded-md px-3 py-1.5 text-xs transition"
              style={
                tab === id
                  ? { background: device.accent, color: "#14161a" }
                  : { color: "var(--muted)" }
              }
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "flow" ? (
          <SignalFlow device={device} state={flowState} />
        ) : null}

        {tab === "prompt" ? (
          <div className="flex flex-col gap-3">
            <p className="text-[12px] text-[var(--muted)]">
              זו ההוראה המדויקת שנשלחת למנוע. היא נגזרת ממצב הפקדים, מהחוקים
              ומרמת האוטונומיה — אין שכבה נסתרת.
            </p>
            <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded-lg border border-[var(--line)] bg-[#0f1113] p-4 text-[12px] leading-relaxed">
              {systemPrompt}
              {"\n\n— — —\n\n"}
              {buildUserPrompt(device, inputs)}
            </pre>
          </div>
        ) : null}

        {tab === "history" ? (
          <div className="flex flex-col gap-2">
            {runs.length === 0 ? (
              <p className="text-sm text-[var(--muted)]">אין עדיין הרצות.</p>
            ) : (
              runs.map((entry) => (
                <button
                  key={entry.id}
                  type="button"
                  onClick={() => {
                    setResult(entry.result);
                    setValues(entry.values);
                    setInputs(entry.inputs);
                  }}
                  className="rounded-lg border border-[var(--line)] bg-[var(--panel-3)] p-3 text-right transition hover:border-[var(--muted)]"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[13px]">
                      {entry.result.items.length} פריטים ·{" "}
                      {entry.result.missing.length} שאלות פתוחות
                    </span>
                    <span className="text-[11px] text-[var(--muted)]">
                      {new Date(entry.at).toLocaleString("he-IL")}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-[12px] text-[var(--muted)]">
                    {entry.result.summary}
                  </p>
                </button>
              ))
            )}
          </div>
        ) : null}
      </section>

      {editing ? (
        <EditPanel
          device={device}
          baseDevice={baseDevice}
          autonomy={autonomy}
          onAutonomy={(level) => {
            setAutonomy(level);
            patchOverrides({ autonomy: level });
          }}
          onRules={(rules) => patchOverrides({ rules })}
          onControlLabel={(id, label) =>
            patchOverrides({
              controlLabels: { ...(overrides.controlLabels ?? {}), [id]: label },
            })
          }
          onControlPrompt={(id, prompt) =>
            patchOverrides({
              controlPrompts: {
                ...(overrides.controlPrompts ?? {}),
                [id]: prompt,
              },
            })
          }
          onReset={() => {
            clearOverrides(baseDevice.id);
            setOverrides({});
            setAutonomy(baseDevice.autonomy);
          }}
        />
      ) : null}
    </div>
  );
}

function ConsoleHeader({
  device,
  editing,
  onToggleEditing,
}: {
  device: Device;
  editing: boolean;
  onToggleEditing: () => void;
}) {
  return (
    <header className="panel flex flex-wrap items-center justify-between gap-4 px-5 py-4">
      <div className="flex items-center gap-4">
        <span
          className="h-9 w-1.5 rounded-full"
          style={{ background: device.accent }}
        />
        <div>
          <h1 className="text-lg font-medium tracking-wide">{device.name}</h1>
          <p className="text-[12px] text-[var(--muted)]">{device.subtitle}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={onToggleEditing}
        className="rounded-lg border border-[var(--line)] px-4 py-2 text-xs transition hover:border-[var(--muted)]"
        style={editing ? { borderColor: device.accent, color: device.accent } : undefined}
      >
        {editing ? "סגור מצב עריכה" : "מצב עריכה"}
      </button>
    </header>
  );
}

function PanelScrews() {
  return (
    <>
      <span className="screw absolute right-2.5 top-2.5" />
      <span className="screw absolute left-2.5 top-2.5" />
      <span className="screw absolute bottom-2.5 right-2.5" />
      <span className="screw absolute bottom-2.5 left-2.5" />
    </>
  );
}

function PresetBar({
  presets,
  name,
  onNameChange,
  onSave,
  onRecall,
  onDelete,
  onReset,
}: {
  presets: Preset[];
  name: string;
  onNameChange: (value: string) => void;
  onSave: () => void;
  onRecall: (preset: Preset) => void;
  onDelete: (id: string) => void;
  onReset: () => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="engraved">Presets</span>
        <button
          type="button"
          onClick={onReset}
          className="text-[11px] text-[var(--muted)] underline-offset-2 hover:underline"
        >
          איפוס לברירת מחדל
        </button>
      </div>

      <div className="flex gap-2">
        <input
          value={name}
          onChange={(event) => onNameChange(event.target.value)}
          placeholder="שם ל־preset"
          className="min-w-0 flex-1 rounded-lg border border-[var(--line)] bg-[#0f1113] px-3 py-2 text-xs outline-none placeholder:text-[#5c6068] focus:border-[var(--muted)]"
        />
        <button
          type="button"
          onClick={onSave}
          className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs transition hover:border-[var(--muted)]"
        >
          שמור
        </button>
      </div>

      {presets.length > 0 ? (
        <ul className="flex flex-col gap-1">
          {presets.map((preset) => (
            <li
              key={preset.id}
              className="flex items-center gap-2 rounded-lg border border-[var(--line)] bg-[var(--panel-3)] px-3 py-1.5"
            >
              <button
                type="button"
                onClick={() => onRecall(preset)}
                className="min-w-0 flex-1 truncate text-right text-xs"
              >
                {preset.name}
              </button>
              <button
                type="button"
                onClick={() => onDelete(preset.id)}
                aria-label={`מחיקת ${preset.name}`}
                className="text-[11px] text-[var(--muted)] hover:text-[var(--alert)]"
              >
                מחק
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function EditPanel({
  device,
  baseDevice,
  autonomy,
  onAutonomy,
  onRules,
  onControlLabel,
  onControlPrompt,
  onReset,
}: {
  device: Device;
  baseDevice: Device;
  autonomy: AutonomyLevel;
  onAutonomy: (level: AutonomyLevel) => void;
  onRules: (rules: string[]) => void;
  onControlLabel: (id: string, label: string) => void;
  onControlPrompt: (id: string, prompt: string) => void;
  onReset: () => void;
}) {
  return (
    <section className="panel flex flex-col gap-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium">מצב עריכה</h2>
          <p className="text-[12px] text-[var(--muted)]">
            כאן משנים מה המכשיר עושה: תוויות הפקדים, ההוראה שכל פקד שולח,
            החוקים ורמת האוטונומיה. השינויים נשמרים מיד.
          </p>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="rounded-lg border border-[var(--line)] px-3 py-2 text-xs transition hover:border-[var(--alert)] hover:text-[var(--alert)]"
        >
          החזר את המכשיר למקור
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <span className="engraved">חוקים</span>
          {device.rules.map((rule, index) => (
            <div key={index} className="flex gap-2">
              <textarea
                rows={2}
                value={rule}
                onChange={(event) => {
                  const next = [...device.rules];
                  next[index] = event.target.value;
                  onRules(next);
                }}
                className="min-w-0 flex-1 resize-y rounded-lg border border-[var(--line)] bg-[#0f1113] p-2 text-[12px] outline-none focus:border-[var(--muted)]"
              />
              <button
                type="button"
                onClick={() => onRules(device.rules.filter((_, i) => i !== index))}
                aria-label="מחיקת חוק"
                className="self-start rounded-lg border border-[var(--line)] px-2 py-1 text-[11px] text-[var(--muted)] hover:text-[var(--alert)]"
              >
                מחק
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={() => onRules([...device.rules, "חוק חדש"])}
            className="w-fit rounded-lg border border-[var(--line)] px-3 py-2 text-xs transition hover:border-[var(--muted)]"
          >
            הוסף חוק
          </button>

          <div className="mt-2 flex flex-col gap-2">
            <span className="engraved">רמת אוטונומיה (ברירת מחדל למכשיר)</span>
            <div className="flex gap-1 rounded-lg border border-[var(--line)] bg-[#0f1113] p-1">
              {([1, 2, 3] as AutonomyLevel[]).map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => onAutonomy(level)}
                  aria-pressed={autonomy === level}
                  className="flex-1 rounded-md px-2 py-1.5 text-[11px] transition"
                  style={
                    autonomy === level
                      ? { background: device.accent, color: "#14161a" }
                      : { color: "var(--muted)" }
                  }
                >
                  {AUTONOMY_LABELS[level]}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <span className="engraved">פקדים</span>
          {device.controls.map((control) => {
            const original = baseDevice.controls.find(
              (item) => item.id === control.id,
            );
            return (
              <div
                key={control.id}
                className="flex flex-col gap-2 rounded-lg border border-[var(--line)] bg-[#0f1113] p-3"
              >
                <input
                  value={control.label}
                  onChange={(event) =>
                    onControlLabel(control.id, event.target.value)
                  }
                  className="rounded border border-[var(--line)] bg-[var(--panel-3)] px-2 py-1 text-[12px] outline-none focus:border-[var(--muted)]"
                />
                <textarea
                  rows={3}
                  value={control.promptTemplate}
                  onChange={(event) =>
                    onControlPrompt(control.id, event.target.value)
                  }
                  className="resize-y rounded border border-[var(--line)] bg-[var(--panel-3)] px-2 py-1 text-[12px] leading-relaxed outline-none focus:border-[var(--muted)]"
                />
                {original && original.promptTemplate !== control.promptTemplate ? (
                  <span className="text-[10px] text-[var(--amber)]">שונה מהמקור</span>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
