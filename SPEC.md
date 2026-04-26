# Plonker — GeoGuessr meta learning extension

## What it is
A Chrome MV3 extension that overlays geoguessr.com to track how the user does in singleplayer + learnable-meta-map games, then teaches them the metas they keep missing.

## Locked requirements (from 40-question discovery)

### Goals
- Primary: country ID from any clue (intermediate level, 15k–22k avg)
- Cover all meta categories: bollards/poles/lines, language/scripts/signage, vehicles/plates/antenna, vegetation/soil/sky
- Match GeoGuessr's dark theme

### Tracker (v1, MVP)
- **Game modes tracked**: singleplayer + learnable-meta community maps
- **Movement modes**: separate stats per NMPZ vs Moving (key insight: different metas matter)
- **Country detection**: parse GG result page DOM (via fetch interception of `/api/v3/games/{token}` → `rounds[i].streakLocationCode` → ISO country code)
- **Image storage**: links to Google Maps coords only — no screenshots
- **Overlay obtrusiveness**: silent during round, popup only after guess
- **Post-round popup contents**:
  - Why-it-was-X meta breakdown (3–5 key metas pulled from plonkit/learnablemeta)
  - Distance-from-clue diagnostic (closest distinguishing meta vs what user guessed)
  - Structured note: meta tag (bollard / language / plate / vegetation / other) + free-text comment
  - "No spoilers" mode: hide actual country until clicked
- **Plonkit + learnablemeta links** in popup

### Storage
- Supabase project `qhudavmfhbumknqddgig` (`hard diffs`, free tier, single-user reuse)
- Tables prefixed `plonker_*` to keep isolated from other projects
- Publishable key on client, RLS policies allow anon CRUD on `plonker_*` only

### Study mode (v2)
- **Surface**: full new tab (`chrome-extension://.../study.html`)
- **Trigger**: manual button in popup (no auto-suggest, no daily reminder for v1)
- **Session**: endless until X wrong (lives configurable, default 3)
- **SRS**: Leitner box (5 boxes)
- **Question types**: country ID + which-region-within-country + meta-clue identification + compare-two-images
- **Image source**: curated screenshots scraped from plonkit + learnablemeta
- **MC options**: configurable 3–8
- **Distractors**: hard only (visually/regionally similar countries)
- **Wrong answer**: explanation + side-by-side + re-queue (all three)
- **Session focus**: random by default; filter by continent / GG sub-region (Baltics, Scandinavia, Balkans, SE Asia, LatAm) / easy-confused pairs (Belarus/Russia, Czech/Slovakia, Argentina/Uruguay)

### Dashboard (v2)
- World heatmap (red weak, green mastered) → click country → per-country drill-down
- Per-country drill-down: heatmap of mostly-missed meta concepts within that country (not just country acc)
- Ranked list (worst-first table)
- Per-meta-concept mastery integrated into per-country view (not separate tab)
- Stats only — no gamification, no badges, no XP

### Branding
- Name: **Plonker** (GG-community lingo)

### Reference data
- Bundled at build time, refreshed monthly via scraper
- Sources: plonkit.net (per-country guides) + learnablemeta.com (per-map meta lists)

## Architecture
```
extension/
  manifest.json         # MV3
  src/
    background.ts       # service worker, Supabase client, message router
    content.ts          # isolated-world, message bridge
    inject.ts           # MAIN-world, fetch override (the real magic)
    popup/              # toolbar popup: settings + "Open study mode" button (v2)
    overlay/            # post-round modal injected on geoguessr.com
    study/              # full-page study mode (v2)
    dashboard/          # full-page dashboard (v2)
    lib/
      gg-api.ts         # types + helpers for parsed GG state
      supabase.ts       # thin Supabase wrapper
      country-codes.ts  # ISO-2 → ISO-3 + disputed-territory normalization (CC_DICT from miraclewhips)
  data/
    plonkit/            # scraped per-country JSON
    learnablemeta/      # scraped per-map JSON
    distractors.json    # hard-distractor neighbor map
  assets/               # icons, fonts, images
scraper/
  scrape_plonkit.py
  scrape_learnablemeta.py
  build_bundle.py
docs/
  SUPABASE_SCHEMA.sql
README.md
SPEC.md (this file)
```

## Supabase schema (single-user, RLS permissive on plonker_* prefix)

```sql
create table plonker_round (
  id uuid primary key default gen_random_uuid(),
  game_id text not null,
  game_token text,
  round_index int not null,
  game_type text,          -- "standard", "challenge", "infinity"
  game_mode text,          -- "standard"
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

create table plonker_note (
  id uuid primary key default gen_random_uuid(),
  round_id uuid references plonker_round(id) on delete cascade,
  meta_tag text,           -- 'bollard' | 'language' | 'plate' | 'vegetation' | 'other'
  comment text,
  created_at timestamptz default now()
);

create table plonker_settings (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz default now()
);

create index plonker_round_country_idx on plonker_round(actual_country_iso2);
create index plonker_round_played_at_idx on plonker_round(played_at desc);
create index plonker_note_round_idx on plonker_note(round_id);

alter table plonker_round enable row level security;
alter table plonker_note enable row level security;
alter table plonker_settings enable row level security;

create policy "anon_all_round"    on plonker_round    for all to anon using (true) with check (true);
create policy "anon_all_note"     on plonker_note     for all to anon using (true) with check (true);
create policy "anon_all_settings" on plonker_settings for all to anon using (true) with check (true);
```
