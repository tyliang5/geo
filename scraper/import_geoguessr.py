"""Backfill historical GeoGuessr round data into Supabase.

Why this exists: the Plonker extension only captures rounds played AFTER it's
installed. To see weak countries from your full history (Solo, Streak, Duels),
this script hits the GeoGuessr internal API directly using your session
cookie and inserts each round into Supabase via the same schema the extension
uses.

How to use:

    1. Open https://www.geoguessr.com in Chrome and sign in.
    2. Open DevTools → Application → Cookies → www.geoguessr.com.
    3. Copy the value of the `_ncfa` cookie. (It's the only one that matters.)
    4. Set the GG_NCFA env var, then run:

           export GG_NCFA="paste-the-cookie-value-here"
           python scraper/import_geoguessr.py --limit 500

       On Windows PowerShell:
           $env:GG_NCFA = "paste-the-cookie-value-here"
           python scraper/import_geoguessr.py --limit 500

The script:
  - Pages through /api/v4/feed/private to enumerate finished games.
  - For each Standard / Streak / Duels game, fetches /api/v3/games/<token> or
    the duels endpoint and pulls per-round actual_lat/lng + guess_lat/lng.
  - Reverse-geocodes guess coords via Nominatim (1 req/sec) to fill
    guess_country_iso2 — same approach as background.js.
  - Upserts into plonker_round with onConflict (game_id, round_index) so
    re-running is safe.

Caveats:
  - GeoGuessr's internal API is unofficial. Endpoints can change without
    notice. If something breaks, inspect the network tab while playing a
    round to find the new shape.
  - Duels have a different per-round structure than Standard games. We
    flatten both into the same schema.
  - Rate-limit yourself: ~10 req/sec for GG, 1 req/sec for Nominatim.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Iterable
import requests

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scraper'))

SUPABASE_URL = 'https://qhudavmfhbumknqddgig.supabase.co'
SUPABASE_KEY = 'sb_publishable_aGh_bbXqckmx-0DgaEySWg_9yyc_994'
SUPA_HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}

GG_BASE = 'https://www.geoguessr.com'
GG_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'Mozilla/5.0 (plonker-importer/1.0)',
    'Referer': 'https://www.geoguessr.com/',
}


def gg_get(path: str, ncfa: str) -> dict | list | None:
    url = f'{GG_BASE}{path}'
    headers = {**GG_HEADERS, 'Cookie': f'_ncfa={ncfa}'}
    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Feed iteration. The /api/v4/feed/private endpoint returns activity items
# including finished games. Each item has a payload with a token we can
# resolve via /api/v3/games/<token>.
# ---------------------------------------------------------------------------
def iter_feed(ncfa: str, limit: int) -> Iterable[dict]:
    pagination_token: str | None = None
    fetched = 0
    while fetched < limit:
        path = '/api/v4/feed/private'
        if pagination_token:
            path += f'?paginationToken={pagination_token}'
        body = gg_get(path, ncfa)
        if not body or not body.get('entries'):
            return
        for entry in body['entries']:
            yield entry
            fetched += 1
            if fetched >= limit:
                return
        pagination_token = body.get('paginationToken')
        if not pagination_token:
            return
        time.sleep(0.2)  # be polite


def extract_game_tokens(entry: dict) -> list[tuple[str, str]]:
    """Return a list of (kind, token) for game references in one feed entry.

    'kind' is 'standard' for classic Solo/Streak (resolvable via
    /api/v3/games/<token>) or 'duels' for Duels matches.
    """
    out: list[tuple[str, str]] = []
    payload = entry.get('payload')
    if isinstance(payload, str):
        try: payload = json.loads(payload)
        except Exception: payload = {}
    payload = payload or {}

    # Different feed types nest differently. Walk recursively for any
    # gameToken / gameId / matchId keys.
    def walk(obj, path=''):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ('gameToken', 'gameId') and isinstance(v, str):
                    out.append(('standard', v))
                elif k in ('matchId', 'duelToken') and isinstance(v, str):
                    out.append(('duels', v))
                else:
                    walk(v, f'{path}.{k}')
        elif isinstance(obj, list):
            for x in obj:
                walk(x, path)
    walk(payload)
    walk(entry.get('user') or {})
    return list(dict.fromkeys(out))  # dedup, preserve order


# ---------------------------------------------------------------------------
# Round extraction — Standard and Duels share fields but live at different
# paths. Map both into a flat list of round-records the persist step writes.
# ---------------------------------------------------------------------------
def fetch_standard_rounds(token: str, ncfa: str) -> list[dict]:
    data = gg_get(f'/api/v3/games/{token}', ncfa)
    if not data:
        return []
    rounds_meta = data.get('rounds') or []
    guesses = (data.get('player') or {}).get('guesses') or []
    out = []
    for i, r in enumerate(rounds_meta):
        g = guesses[i] if i < len(guesses) else None
        out.append({
            'game_id': data.get('token') or token,
            'round_index': i,
            'game_type': data.get('type'),
            'game_mode': data.get('mode'),
            'forbid_moving': bool(data.get('forbidMoving')),
            'forbid_panning': bool(data.get('forbidRotating')),
            'forbid_zooming': bool(data.get('forbidZooming')),
            'map_id': data.get('map'),
            'map_name': data.get('mapName'),
            'actual_lat': r.get('lat'),
            'actual_lng': r.get('lng'),
            'actual_country_iso2': (r.get('streakLocationCode') or '').upper() or None,
            'guess_lat': g.get('lat') if g else None,
            'guess_lng': g.get('lng') if g else None,
            'guess_country_iso2': (g.get('streakLocationCode') or '').upper() if g and g.get('streakLocationCode') else None,
            'round_score': (g or {}).get('roundScoreInPoints')
                          or ((g or {}).get('roundScore') or {}).get('amount'),
            'distance_m': (g or {}).get('distanceInMeters')
                          or (((g or {}).get('distance') or {}).get('meters') or {}).get('amount'),
        })
    return out


def fetch_duels_rounds(match_id: str, ncfa: str) -> list[dict]:
    # Duels live on a different host; the path that works from the same cookie:
    data = gg_get(f'/api/duels/{match_id}', ncfa)
    if not data:
        return []
    me_id = (data.get('myTeam') or {}).get('id')
    rounds = data.get('rounds') or []
    out = []
    for i, r in enumerate(rounds):
        # Find my guess in the round's guesses array
        guesses = r.get('guesses') or []
        my_guess = next((g for g in guesses if g.get('teamId') == me_id), None)
        out.append({
            'game_id': match_id,
            'round_index': i,
            'game_type': 'duels',
            'game_mode': 'duels',
            'forbid_moving': bool(data.get('options', {}).get('movementOptions', {}).get('forbidMoving')),
            'forbid_panning': bool(data.get('options', {}).get('movementOptions', {}).get('forbidPanning')),
            'forbid_zooming': bool(data.get('options', {}).get('movementOptions', {}).get('forbidZooming')),
            'map_id': data.get('options', {}).get('map'),
            'map_name': data.get('options', {}).get('mapName'),
            'actual_lat': r.get('panorama', {}).get('lat'),
            'actual_lng': r.get('panorama', {}).get('lng'),
            'actual_country_iso2': (r.get('panorama', {}).get('countryCode') or '').upper() or None,
            'guess_lat': (my_guess or {}).get('lat'),
            'guess_lng': (my_guess or {}).get('lng'),
            'guess_country_iso2': None,  # duels don't surface guess country directly
            'round_score': (my_guess or {}).get('score'),
            'distance_m': (my_guess or {}).get('distance'),
        })
    return out


# ---------------------------------------------------------------------------
# Reverse geocode (Nominatim) — fill guess_country_iso2 when GG didn't.
# Cached in-memory only; run is a one-shot.
# ---------------------------------------------------------------------------
_geo_cache: dict[tuple[float, float], str | None] = {}


def reverse_country(lat: float | None, lng: float | None) -> str | None:
    if lat is None or lng is None:
        return None
    key = (round(lat, 2), round(lng, 2))
    if key in _geo_cache:
        return _geo_cache[key]
    try:
        r = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'format': 'jsonv2', 'lat': lat, 'lon': lng, 'zoom': 5},
            headers={'User-Agent': 'plonker-importer/1.0', 'Accept-Language': 'en'},
            timeout=15,
        )
        cc = (r.json().get('address', {}).get('country_code') or '').upper() or None
    except Exception:
        cc = None
    _geo_cache[key] = cc
    time.sleep(1.1)  # Nominatim courtesy
    return cc


# ---------------------------------------------------------------------------
# Persist
# ---------------------------------------------------------------------------
def upsert_round(row: dict) -> bool:
    url = f'{SUPABASE_URL}/rest/v1/plonker_round'
    headers = {
        **SUPA_HEADERS,
        'Prefer': 'resolution=merge-duplicates,return=minimal',
    }
    r = requests.post(
        url, headers=headers,
        params={'on_conflict': 'game_id,round_index'},
        data=json.dumps(row),
        timeout=15,
    )
    if not r.ok:
        print(f'   supabase error {r.status_code}: {r.text[:120]}', file=sys.stderr)
        return False
    return True


# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=200,
                    help='Max feed entries to walk back (each may contain multiple games).')
    ap.add_argument('--no-geocode', action='store_true',
                    help='Skip Nominatim reverse-geocode for guess_country_iso2.')
    args = ap.parse_args()

    ncfa = os.environ.get('GG_NCFA')
    if not ncfa:
        print('ERROR: set the GG_NCFA env var to your _ncfa cookie value.', file=sys.stderr)
        print('See the docstring at the top of this file for steps.', file=sys.stderr)
        sys.exit(2)

    print('walking feed...')
    seen_games: set[tuple[str, str]] = set()
    rows_written = 0
    rows_skipped = 0
    n_games = 0

    for entry in iter_feed(ncfa, args.limit):
        for kind, token in extract_game_tokens(entry):
            if (kind, token) in seen_games:
                continue
            seen_games.add((kind, token))
            n_games += 1
            try:
                if kind == 'standard':
                    rounds = fetch_standard_rounds(token, ncfa)
                else:
                    rounds = fetch_duels_rounds(token, ncfa)
            except Exception as e:
                print(f'  [{kind}] {token[:8]} fetch failed: {e}')
                continue
            if not rounds:
                continue
            for row in rounds:
                if not args.no_geocode and not row.get('guess_country_iso2'):
                    row['guess_country_iso2'] = reverse_country(row.get('guess_lat'), row.get('guess_lng'))
                # Compute movement_label is generated by the DB; skip
                if upsert_round(row):
                    rows_written += 1
                else:
                    rows_skipped += 1
            time.sleep(0.2)

    print(f'\ndone: {n_games} games, {rows_written} rounds written, {rows_skipped} failed')


if __name__ == '__main__':
    main()
