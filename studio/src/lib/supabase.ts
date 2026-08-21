"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Supabase הוא אופציונלי בשלב הזה.
 *
 * אם המשתנים לא הוגדרו — האולפן עובד מקומית מול הדפדפן, וכל מה שנשמר
 * נשמר ב־localStorage. ברגע שמגדירים חיבור, אותו קוד עובד מול הענן.
 */

let cached: SupabaseClient | null | undefined;

export function getSupabase(): SupabaseClient | null {
  if (cached !== undefined) return cached;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  cached = url && key ? createClient(url, key) : null;
  return cached;
}

export function isCloudEnabled(): boolean {
  return getSupabase() !== null;
}
