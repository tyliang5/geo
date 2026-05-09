-- Plonker cross-device progress sync.
--
-- This stores all the localStorage state the app cares about — per-card
-- accuracy, Leitner boxes, blacklist, topic / quiz totals — in a single
-- "self" row so any device with the publishable key can pull and merge.
--
-- One-time setup: paste this whole file into Supabase Dashboard →
-- SQL Editor → Run.  It's idempotent — safe to re-run.

create table if not exists public.plonker_progress (
  id text primary key,
  card_stats  jsonb not null default '{}'::jsonb,
  leitner     jsonb not null default '{}'::jsonb,
  blacklist   jsonb not null default '[]'::jsonb,
  topic_stats jsonb not null default '{}'::jsonb,
  quiz_stats  jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);

-- Allow anon (publishable-key) read/write. Acceptable for a personal tool;
-- swap to authenticated-only if you ever care about isolation.
alter table public.plonker_progress enable row level security;

drop policy if exists "plonker_progress_anon_all" on public.plonker_progress;
create policy "plonker_progress_anon_all"
  on public.plonker_progress
  for all
  to anon
  using (true) with check (true);

-- Seed the singleton row.
insert into public.plonker_progress (id) values ('self')
  on conflict (id) do nothing;

-- Bump updated_at on every write so the client can tell who's stale.
create or replace function public.plonker_progress_touch()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_plonker_progress_touch on public.plonker_progress;
create trigger trg_plonker_progress_touch
  before update on public.plonker_progress
  for each row execute function public.plonker_progress_touch();
