create table if not exists plonker_round (
  id uuid primary key default gen_random_uuid(),
  game_id text not null,
  game_token text,
  round_index int not null,
  game_type text,
  game_mode text,
  forbid_moving bool,
  forbid_panning bool,
  forbid_zooming bool,
  movement_label text generated always as (
    case
      when forbid_moving and forbid_panning and forbid_zooming then 'NMPZ'
      when forbid_moving then 'NM'
      else 'Moving'
    end
  ) stored,
  map_id text,
  map_name text,
  is_learnable_meta_map bool default false,
  actual_lat double precision,
  actual_lng double precision,
  actual_country_iso2 text,
  actual_country_iso3 text,
  guess_lat double precision,
  guess_lng double precision,
  guess_country_iso2 text,
  round_score int,
  distance_m double precision,
  played_at timestamptz default now(),
  unique (game_id, round_index)
);

create table if not exists plonker_note (
  id uuid primary key default gen_random_uuid(),
  round_id uuid references plonker_round(id) on delete cascade,
  meta_tag text,
  comment text,
  created_at timestamptz default now()
);

create table if not exists plonker_settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz default now()
);

create index if not exists plonker_round_country_idx on plonker_round(actual_country_iso2);
create index if not exists plonker_round_played_at_idx on plonker_round(played_at desc);
create index if not exists plonker_note_round_idx on plonker_note(round_id);

alter table plonker_round enable row level security;
alter table plonker_note enable row level security;
alter table plonker_settings enable row level security;

drop policy if exists "anon_all_round"    on plonker_round;
drop policy if exists "anon_all_note"     on plonker_note;
drop policy if exists "anon_all_settings" on plonker_settings;

create policy "anon_all_round"    on plonker_round    for all to anon using (true) with check (true);
create policy "anon_all_note"     on plonker_note     for all to anon using (true) with check (true);
create policy "anon_all_settings" on plonker_settings for all to anon using (true) with check (true);
