"use client";

import { getSupabase } from "@/lib/supabase";
import type { Device, Preset, RunLogEntry } from "@/lib/types";

/**
 * שכבת שמירה אחת לשני עולמות.
 *
 * ללא Supabase — localStorage. עם Supabase — טבלאות presets ו־runs,
 * כשהרשאות ברמת השורה מגבילות כל משתמש למידע שלו. הממשק זהה בשני המקרים,
 * כדי שמעבר לענן לא ידרוש שכתוב של המסכים.
 */

const PRESETS_KEY = "studio.presets.v1";
const RUNS_KEY = "studio.runs.v1";

function readLocal<T>(key: string): T[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T[]) : [];
  } catch {
    return [];
  }
}

function writeLocal<T>(key: string, rows: T[]): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(rows));
}

export async function loadPresets(deviceId: string): Promise<Preset[]> {
  const supabase = getSupabase();
  if (supabase) {
    const { data, error } = await supabase
      .from("presets")
      .select("id, device_id, name, values, autonomy, created_at")
      .eq("device_id", deviceId)
      .order("created_at", { ascending: false });

    if (error) throw new Error(error.message);

    return (data ?? []).map((row) => ({
      id: row.id as string,
      deviceId: row.device_id as string,
      name: row.name as string,
      values: row.values as Preset["values"],
      autonomy: row.autonomy as Preset["autonomy"],
      createdAt: row.created_at as string,
    }));
  }

  return readLocal<Preset>(PRESETS_KEY)
    .filter((preset) => preset.deviceId === deviceId)
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

export async function savePreset(preset: Preset): Promise<void> {
  const supabase = getSupabase();
  if (supabase) {
    const { error } = await supabase.from("presets").insert({
      id: preset.id,
      device_id: preset.deviceId,
      name: preset.name,
      values: preset.values,
      autonomy: preset.autonomy,
    });
    if (error) throw new Error(error.message);
    return;
  }

  const rows = readLocal<Preset>(PRESETS_KEY);
  writeLocal(PRESETS_KEY, [preset, ...rows]);
}

export async function deletePreset(id: string): Promise<void> {
  const supabase = getSupabase();
  if (supabase) {
    const { error } = await supabase.from("presets").delete().eq("id", id);
    if (error) throw new Error(error.message);
    return;
  }

  writeLocal(
    PRESETS_KEY,
    readLocal<Preset>(PRESETS_KEY).filter((preset) => preset.id !== id),
  );
}

export async function loadRuns(deviceId: string, limit = 20): Promise<RunLogEntry[]> {
  const supabase = getSupabase();
  if (supabase) {
    const { data, error } = await supabase
      .from("runs")
      .select("id, device_id, created_at, values, inputs, result")
      .eq("device_id", deviceId)
      .order("created_at", { ascending: false })
      .limit(limit);

    if (error) throw new Error(error.message);

    return (data ?? []).map((row) => ({
      id: row.id as string,
      deviceId: row.device_id as string,
      at: row.created_at as string,
      values: row.values as RunLogEntry["values"],
      inputs: row.inputs as RunLogEntry["inputs"],
      result: row.result as RunLogEntry["result"],
    }));
  }

  return readLocal<RunLogEntry>(RUNS_KEY)
    .filter((run) => run.deviceId === deviceId)
    .slice(0, limit);
}

export async function saveRun(entry: RunLogEntry): Promise<void> {
  const supabase = getSupabase();
  if (supabase) {
    const { error } = await supabase.from("runs").insert({
      id: entry.id,
      device_id: entry.deviceId,
      values: entry.values,
      inputs: entry.inputs,
      result: entry.result,
    });
    if (error) throw new Error(error.message);
    return;
  }

  const rows = readLocal<RunLogEntry>(RUNS_KEY);
  writeLocal(RUNS_KEY, [entry, ...rows].slice(0, 50));
}

/**
 * שינויים שהמשתמש עשה למכשיר במצב עריכה.
 * נשמרים מקומית בשלב זה — כשיהיו משתמשים בענן, אותו אובייקט עובר לטבלה.
 */
export interface DeviceOverrides {
  rules?: string[];
  autonomy?: number;
  controlLabels?: Record<string, string>;
  controlPrompts?: Record<string, string>;
}

function overridesKey(deviceId: string): string {
  return `studio.device.${deviceId}.v1`;
}

/** אסינכרוני בכוונה — הקריאה מתרחשת אחרי ההידרציה, ולא בגוף האפקט */
export async function loadOverrides(deviceId: string): Promise<DeviceOverrides> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(overridesKey(deviceId));
    return raw ? (JSON.parse(raw) as DeviceOverrides) : {};
  } catch {
    return {};
  }
}

export function saveOverrides(deviceId: string, overrides: DeviceOverrides): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(overridesKey(deviceId), JSON.stringify(overrides));
}

export function clearOverrides(deviceId: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(overridesKey(deviceId));
}

/** מחיל את שינויי המשתמש על הגדרת המכשיר המקורית */
export function applyOverrides(device: Device, overrides: DeviceOverrides): Device {
  if (!overrides || Object.keys(overrides).length === 0) return device;

  return {
    ...device,
    rules: overrides.rules ?? device.rules,
    autonomy: (overrides.autonomy as Device["autonomy"]) ?? device.autonomy,
    controls: device.controls.map((control) => ({
      ...control,
      label: overrides.controlLabels?.[control.id] ?? control.label,
      promptTemplate:
        overrides.controlPrompts?.[control.id] ?? control.promptTemplate,
    })),
  };
}

export function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}
