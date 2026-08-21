-- סכימת Supabase לאולפן.
-- להריץ ב־SQL Editor של הפרויקט. כל משתמש רואה רק את המידע שלו.

create table if not exists public.presets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  device_id text not null,
  name text not null,
  values jsonb not null default '{}'::jsonb,
  autonomy smallint not null default 2,
  created_at timestamptz not null default now()
);

create index if not exists presets_user_device_idx
  on public.presets (user_id, device_id, created_at desc);

create table if not exists public.runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  device_id text not null,
  values jsonb not null default '{}'::jsonb,
  inputs jsonb not null default '{}'::jsonb,
  result jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists runs_user_device_idx
  on public.runs (user_id, device_id, created_at desc);

-- הרשאות ברמת השורה: אין גישה למידע של אחרים.
alter table public.presets enable row level security;
alter table public.runs enable row level security;

create policy "presets are private" on public.presets
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "runs are private" on public.runs
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
