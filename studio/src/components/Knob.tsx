"use client";

import { useCallback, useRef } from "react";

import { zoneLabel, type RangeControl } from "@/lib/types";

/**
 * נוב סיבובי. גרירה אנכית משנה את הערך, גלגלת מכווננת, וחיצי המקלדת
 * עובדים גם הם — פקד חומרה שנשאר נגיש.
 */
export function Knob({
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
  const dragState = useRef<{ y: number; start: number } | null>(null);

  const clamp = useCallback(
    (next: number) => {
      const stepped = Math.round(next / control.step) * control.step;
      const bounded = Math.min(control.max, Math.max(control.min, stepped));
      // מונע 0.30000000000000004 בערכים עשרוניים
      return Number(bounded.toFixed(4));
    },
    [control.max, control.min, control.step],
  );

  const ratio = (value - control.min) / (control.max - control.min);
  // הנוב מסתובב 270 מעלות, מ־135- ועד 135+
  const angle = -135 + ratio * 270;
  const zone = zoneLabel(control, value);

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (disabled) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragState.current = { y: event.clientY, start: value };
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const state = dragState.current;
    if (!state) return;
    const delta = state.y - event.clientY;
    const span = control.max - control.min;
    // 180 פיקסלים של גרירה עוברים את כל הטווח
    onChange(clamp(state.start + (delta / 180) * span));
  };

  const endDrag = () => {
    dragState.current = null;
  };

  const nudge = (direction: number) => {
    onChange(clamp(value + direction * control.step));
  };

  return (
    <div className="flex flex-col items-center gap-2">
      <div
        role="slider"
        tabIndex={disabled ? -1 : 0}
        aria-label={control.label}
        aria-valuemin={control.min}
        aria-valuemax={control.max}
        aria-valuenow={value}
        aria-valuetext={zone ? `${value} — ${zone}` : String(value)}
        aria-disabled={disabled}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onKeyDown={(event) => {
          if (disabled) return;
          if (event.key === "ArrowUp" || event.key === "ArrowRight") {
            event.preventDefault();
            nudge(1);
          } else if (event.key === "ArrowDown" || event.key === "ArrowLeft") {
            event.preventDefault();
            nudge(-1);
          } else if (event.key === "Home") {
            event.preventDefault();
            onChange(control.min);
          } else if (event.key === "End") {
            event.preventDefault();
            onChange(control.max);
          }
        }}
        className={`relative h-16 w-16 touch-none select-none rounded-full outline-none ring-offset-2 ring-offset-[var(--panel)] focus-visible:ring-2 ${
          disabled ? "opacity-50" : "cursor-ns-resize"
        }`}
        style={{ ["--tw-ring-color" as string]: accent }}
      >
        <svg viewBox="0 0 64 64" className="absolute inset-0 h-full w-full">
          {/* מסלול הסקאלה */}
          <path
            d="M 13.5 50.5 A 26 26 0 1 1 50.5 50.5"
            fill="none"
            stroke="#0c0d0f"
            strokeWidth="4"
            strokeLinecap="round"
          />
          <path
            d="M 13.5 50.5 A 26 26 0 1 1 50.5 50.5"
            fill="none"
            stroke={accent}
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={`${ratio * 122} 999`}
            opacity={0.9}
          />
        </svg>
        <div className="knob-cap absolute inset-[9px] rounded-full">
          <div
            className="absolute inset-0 transition-transform duration-75"
            style={{ transform: `rotate(${angle}deg)` }}
          >
            <span
              className="absolute left-1/2 top-[6px] h-[10px] w-[2px] -translate-x-1/2 rounded-full"
              style={{ background: accent }}
            />
          </div>
        </div>
      </div>

      <div className="text-center leading-tight">
        <div className="engraved">{control.label}</div>
        <div className="lcd mt-1 rounded px-2 py-0.5 text-[11px] tabular-nums">
          {value}
          {control.unit ?? ""}
        </div>
        {zone ? (
          <div className="mt-1 text-[10px] text-[var(--muted)]">{zone}</div>
        ) : null}
      </div>
    </div>
  );
}
