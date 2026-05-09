"""One-shot backfill: resolve guess_country_iso2 for historical plonker_round
rows where it's null but guess_lat/guess_lng exist. Uses Nominatim reverse
geocoding (1 req/sec).

Run:
    python scraper/backfill_guess_country.py
"""
from __future__ import annotations
import time
import sys
import requests

SUPABASE_URL = 'https://qhudavmfhbumknqddgig.supabase.co'
SUPABASE_KEY = 'sb_publishable_aGh_bbXqckmx-0DgaEySWg_9yyc_994'
HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}


def fetch_null_rows():
    url = f'{SUPABASE_URL}/rest/v1/plonker_round'
    r = requests.get(
        url,
        headers=HEADERS,
        params={
            'select': 'id,guess_lat,guess_lng',
            'guess_country_iso2': 'is.null',
            'guess_lat': 'not.is.null',
            'limit': '500',
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def reverse_geocode(lat: float, lng: float) -> str | None:
    try:
        r = requests.get(
            'https://nominatim.openstreetmap.org/reverse',
            params={'format': 'jsonv2', 'lat': lat, 'lon': lng, 'zoom': 5},
            headers={'User-Agent': 'plonker-backfill/1.0', 'Accept-Language': 'en'},
            timeout=10,
        )
        if not r.ok:
            return None
        cc = (r.json().get('address', {}).get('country_code') or '').upper()
        return cc or None
    except Exception as e:
        print(f'  geocode error: {e}', file=sys.stderr)
        return None


def patch_row(row_id: str, cc2: str) -> bool:
    url = f'{SUPABASE_URL}/rest/v1/plonker_round'
    r = requests.patch(
        url,
        headers=HEADERS,
        params={'id': f'eq.{row_id}'},
        json={'guess_country_iso2': cc2},
        timeout=15,
    )
    return r.ok


def main() -> None:
    rows = fetch_null_rows()
    print(f'fetched {len(rows)} rows with null guess_country_iso2 + non-null guess coords')
    if not rows:
        print('nothing to backfill')
        return

    fixed = skipped = failed = 0
    for i, row in enumerate(rows, 1):
        lat, lng = row['guess_lat'], row['guess_lng']
        cc = reverse_geocode(lat, lng)
        if not cc:
            print(f'[{i}/{len(rows)}] {row["id"][:8]} ({lat:.2f},{lng:.2f}) -> no cc, skipping')
            skipped += 1
            time.sleep(1.1)
            continue
        if patch_row(row['id'], cc):
            print(f'[{i}/{len(rows)}] {row["id"][:8]} ({lat:.2f},{lng:.2f}) -> {cc}')
            fixed += 1
        else:
            print(f'[{i}/{len(rows)}] {row["id"][:8]} -> patch failed')
            failed += 1
        time.sleep(1.1)  # Nominatim courtesy: 1 req/sec

    print(f'\ndone: fixed={fixed} skipped={skipped} failed={failed}')


if __name__ == '__main__':
    main()
