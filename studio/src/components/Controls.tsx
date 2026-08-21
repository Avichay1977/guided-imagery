"use client";

import { Knob } from "@/components/Knob";
import {
  zoneLabel,
  type Control,
  type ControlValue,
  type RangeControl,
  type SelectorControl,
  type ToggleControl,
} from "@/lib/types";

export function Fader({
  control,
  value,
  onChange,
  accent,
  disabled,
}: {
  control: RangeControl;
  value: number;
  onChange: (value: number) => void;
  accent: string;
  disabled?: boolean;
}) {
  const zone = zoneLabel(control, value);
  return (
    <label className="flex flex-col gap-2">
      <span className="flex items-baseline justify-between gap-3">
        <span className="engraved">{control.label}</span>
        <span className="lcd rounded px-2 py-0.5 text-[11px] tabular-nums">
          {value}
          {control.unit ?? ""}
        </span>
      </span>
      <input
        className="fader w-full"
        type="range"
        min={control.min}
        max={control.max}
        step={control.step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        style={{ accentColor: accent }}
      />
      {zone ? (
        <span className="text-[10px] text-[var(--muted)]">{zone}</span>
      ) : null}
    </label>
  );
}

export function Toggle({
  control,
  value,
  onChange,
  accent,
  disabled,
}: {
  control: ToggleControl;
  value: boolean;
  onChange: (value: boolean) => void;
  accent: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      disabled={disabled}
      onClick={() => onChange(!value)}
      className="flex items-center justify-between gap-3 rounded-lg border border-[var(--line)] bg-[var(--panel-3)] px-3 py-2 text-right transition hover:border-[var(--muted)] disabled:opacity-50"
    >
      <span className="flex flex-col">
        <span className="engraved">{control.label}</span>
        {control.hint ? (
          <span className="text-[10px] text-[var(--muted)]">{control.hint}</span>
        ) : null}
      </span>
      <span
        className="relative h-6 w-11 shrink-0 rounded-full border border-[#0c0d0f] transition-colors"
        style={{ background: value ? accent : "#101215" }}
      >
        <span
          className="absolute top-[2px] h-[18px] w-[18px] rounded-full bg-[#e8e6e1] shadow transition-all"
          style={{ insetInlineStart: value ? "22px" : "2px" }}
        />
      </span>
    </button>
  );
}

export function Selector({
  control,
  value,
  onChange,
  accent,
  disabled,
}: {
  control: SelectorControl;
  value: string;
  onChange: (value: string) => void;
  accent: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="engraved">{control.label}</span>
      <div className="flex gap-1 rounded-lg border border-[var(--line)] bg-[#0f1113] p-1">
        {control.options.map((option) => {
          const active = option.value === value;
          return (
            <button
              key={option.value}
              type="button"
              disabled={disabled}
              onClick={() => onChange(option.value)}
              aria-pressed={active}
              className="flex-1 rounded-md px-2 py-1.5 text-xs transition disabled:opacity-50"
              style={
                active
                  ? { background: accent, color: "#14161a", fontWeight: 500 }
                  : { color: "var(--muted)" }
              }
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/** מרנדר את הפקד הנכון לפי סוגו */
export function ControlSlot({
  control,
  value,
  onChange,
  accent,
  disabled,
}: {
  control: Control;
  value: ControlValue;
  onChange: (value: ControlValue) => void;
  accent: string;
  disabled?: boolean;
}) {
  switch (control.kind) {
    case "knob":
      return (
        <Knob
          control={control}
          value={typeof value === "number" ? value : control.defaultValue}
          onChange={onChange}
          accent={accent}
          disabled={disabled}
        />
      );
    case "fader":
      return (
        <Fader
          control={control}
          value={typeof value === "number" ? value : control.defaultValue}
          onChange={onChange}
          accent={accent}
          disabled={disabled}
        />
      );
    case "toggle":
      return (
        <Toggle
          control={control}
          value={typeof value === "boolean" ? value : control.defaultValue}
          onChange={onChange}
          accent={accent}
          disabled={disabled}
        />
      );
    case "selector":
      return (
        <Selector
          control={control}
          value={typeof value === "string" ? value : control.defaultValue}
          onChange={onChange}
          accent={accent}
          disabled={disabled}
        />
      );
  }
}
