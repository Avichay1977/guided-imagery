import { DeviceConsole } from "@/components/DeviceConsole";
import { mixNotesDevice } from "@/lib/devices/mix-notes";

export default function Home() {
  return (
    <main className="flex-1">
      <div className="rail border-b border-[var(--line)]">
        <div className="mx-auto flex w-full max-w-[1400px] items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <span className="text-sm tracking-[0.2em] text-[var(--muted)]">
            האולפן
          </span>
          <span className="text-[11px] text-[var(--muted)]">
            מכשיר אחד פעיל · MIX NOTES
          </span>
        </div>
      </div>

      <DeviceConsole baseDevice={mixNotesDevice} />
    </main>
  );
}
