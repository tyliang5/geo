# -*- coding: utf-8 -*-
"""Move stranded sub-region metas back to country-level metas[].

A meta is "stranded" if it lives under a regions{X} key that doesn't map to
an admin-1 polygon (and isn't in our hand-curated polygon-set fallbacks).
The original reorganize_metas.py was too eager — many genuine country-level
metas got pulled into regions{"General Region"} based on a partial regex
match. They became unquizzable: not in country-ID pool, not in sub-region
pool either.

Decision: pull all metas under non-mappable region keys back into metas[].
For specific keys we KNOW are real but just need polygon aliases (e.g.
"NSW" → "New South Wales"), the polygon-builder script handles those — we
just leave them under regions{} and they'll be picked up after the next
build_subregion_polygons.py run with the new aliases.

This script is idempotent — it reads tips.json, makes the move, writes back.
A backup tips.json.bak2 is kept (original tips.json.bak from the first
reorganize remains untouched).
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
SUBS = REPO / 'extension' / 'data' / 'subregion_polygons.json'
BAK = REPO / 'extension' / 'data' / 'tips.json.bak2'

# Region keys we KEEP under regions{} even if not currently mapped — they
# are real region/state names that just need polygon aliases added to
# build_subregion_polygons.py. Listed here so a future polygon-builder run
# picks them up; this script preserves them.
PROBABLY_REAL_REGIONS = {
    'AU': ['NSW', 'Qld', 'Vic', 'Tas', 'WA', 'SA', 'NT', 'ACT'],
    'BR': ['Sao Paulo', 'Sao Paulo State', 'Rio de Janeiro State', 'Northeast Brazil',
           'Southern Brazil', 'Southeast Brazil', 'North Brazil'],
    'FR': ['Brittany', 'Normandy', 'Provence', 'Alsace', 'Burgundy', 'Corsica'],
    'ID': ['Sumatra', 'Sulawesi', 'Kalimantan', 'Java', 'Bali', 'Papua'],
    'PH': ['Mindanao', 'Luzon', 'Visayas'],
    'MX': ['San Luis Potosi', 'Baja California', 'Yucatan', 'Chiapas'],
    'GB': ['Scotland', 'Wales', 'England', 'Northern Ireland', 'Cornwall'],
    'IT': ['Sicily', 'Sardinia', 'Tuscany', 'Lombardy', 'Veneto'],
    'ES': ['Catalonia', 'Andalusia', 'Galicia', 'Basque Country', 'Canary Islands'],
    'JP': ['Hokkaido', 'Honshu', 'Kyushu', 'Shikoku', 'Okinawa'],
    'CA': ['Quebec', 'Ontario', 'Alberta', 'British Columbia', 'Prairies', 'Maritimes', 'Atlantic Canada'],
    'CN': ['Tibet', 'Xinjiang', 'Inner Mongolia', 'Yunnan', 'Sichuan', 'Hainan'],
    'IN': ['Kashmir', 'Northeast India', 'South India', 'Goa'],
    'RU': ['Siberia', 'Far East', 'Caucasus'],
    'TH': ['Northern Thailand', 'Southern Thailand', 'Isaan'],
    'NO': ['Northern Norway', 'Western Norway', 'Eastern Norway'],
    'DE': ['Bavaria', 'Saxony', 'Hesse', 'North Rhine-Westphalia'],
    'TR': ['Anatolia', 'Eastern Anatolia', 'Aegean'],
    'NZ': ['North Island', 'South Island'],
    'CL': ['Patagonia', 'Atacama'],
    'AR': ['Patagonia', 'Pampas'],
    'PE': ['Andes'],
    'KE': ['Coast', 'Highlands'],
    'TZ': ['Zanzibar'],
}

# Junk region keys we KNOW were extraction artefacts. Always rescue these.
JUNK_KEYS = {
    'General Region', 'North', 'South', 'East', 'West',
    'Northern', 'Southern', 'Eastern', 'Western', 'Central',
    'North Of', 'South Of', 'East Of', 'West Of',
    'North Coast', 'South Coast', 'East Coast', 'West Coast',
    'North Half', 'South Half', 'East Half', 'West Half',
    'North And', 'South And', 'East And', 'West And',
    'East Parts', 'West Parts', 'North Parts', 'South Parts',
    'Coverage', 'Landscape', 'Mountains', 'General', 'Other', 'Misc',
    'Main', 'Around', 'Near', 'In', 'Of', 'The',
    # Pluralised junk
    'Easts', 'Wests', 'Norths', 'Souths',
    # Multi-word junk
    'South Us', 'North Us', 'East Us', 'West Us',
    'Southern Pines The', 'Eastern House Houses', 'East Coast This',
    'Eastern Part', 'Western South Coast',
    'Central California One', 'Northern California One',
}


def main() -> None:
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    subs = json.loads(SUBS.read_text(encoding='utf-8'))

    if not BAK.exists():
        BAK.write_text(TIPS.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'wrote backup -> {BAK.name}')

    rescued = 0
    countries_touched = 0
    kept_for_alias = 0

    for cc, c in tips.items():
        if cc == '_meta':
            continue
        regions = c.get('regions') or {}
        if not regions:
            continue
        mapped_keys = set(subs.get(cc, {}).keys())
        probably_real = set(PROBABLY_REAL_REGIONS.get(cc, []))
        new_regions = {}
        local_rescued = 0
        for region_name, entries in regions.items():
            if region_name in mapped_keys:
                # Already quizzable — keep
                new_regions[region_name] = entries
                continue
            if region_name in JUNK_KEYS:
                # Move all entries back to metas[]
                metas_target = c.setdefault('metas', [])
                for e in entries:
                    if not (e.get('images') or [None])[0]:
                        continue
                    metas_target.append({
                        'type': e.get('type') or 'Region',
                        'title': e.get('title') or '',
                        'description': e.get('text') or e.get('description') or '',
                        'comparison': e.get('comparison') or '',
                        'images': e.get('images') or [],
                        'from_maps': e.get('from_maps') or [],
                    })
                    local_rescued += 1
                continue
            if region_name in probably_real:
                # Keep — polygon-builder may map it on next run
                new_regions[region_name] = entries
                kept_for_alias += len(entries)
                continue
            # Unknown / probably junk — rescue back to metas[]
            metas_target = c.setdefault('metas', [])
            for e in entries:
                if not (e.get('images') or [None])[0]:
                    continue
                metas_target.append({
                    'type': e.get('type') or 'Region',
                    'title': e.get('title') or '',
                    'description': e.get('text') or e.get('description') or '',
                    'comparison': e.get('comparison') or '',
                    'images': e.get('images') or [],
                    'from_maps': e.get('from_maps') or [],
                })
                local_rescued += 1
        if local_rescued:
            countries_touched += 1
            rescued += local_rescued
        c['regions'] = new_regions

    TIPS.write_text(json.dumps(tips, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'rescued {rescued} stranded metas back to country-level metas[] across {countries_touched} countries')
    print(f'preserved {kept_for_alias} metas under "probably real" region keys (waiting for polygon alias)')


if __name__ == '__main__':
    main()
