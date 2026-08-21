"use client";

/**
 * מד סגמנטים בסגנון VU. משמש להצגת ודאות ממוצעת ועומס פריטים —
 * מספר שאפשר לקרוא במבט אחד בלי לקרוא טבלה.
 */
export function Meter({
  label,
  value,
  max = 100,
  unit = "",
  accent = "var(--teal)",
  warnAbove,
}: {
  label: string;
  value: number;
  max?: number;
  unit?: string;
  accent?: string;
  /** מעל הערך הזה הסגמנטים נצבעים באדום */
  warnAbove?: number;
}) {
  const segments = 16;
  const ratio = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  const lit = Math.round(ratio * segments);

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-baseline justify-between gap-2">
        <span className="engraved">{label}</span>
        <span className="lcd rounded px-1.5 py-0.5 text-[11px] tabular-nums">
          {Math.round(value)}
          {unit}
        </span>
      </div>
      <div className="flex gap-[3px]" aria-hidden>
        {Array.from({ length: segments }, (_, index) => {
          const on = index < lit;
          const hot =
            warnAbove !== undefined && (index / segments) * max >= warnAbove;
          return (
            <span
              key={index}
              className="h-3 flex-1 rounded-[2px] transition-colors"
              style={{
                background: on ? (hot ? "var(--alert)" : accent) : "#191b1f",
                boxShadow: on ? `0 0 6px -1px ${hot ? "var(--alert)" : accent}` : "none",
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
