# -*- coding: utf-8 -*-
"""Expand subregion_polygons.json so that EVERY admin-1 region of every
covered country appears in the map, not just the ones that happen to have
their own meta cards.

Why: the sub-region quiz's union logic scans a card's description text for
region names and adds matching polygons to the correct-answer set. But the
text often mentions regions that don't have their own card (e.g., the Russia
"sandy roadsides" card mentions Khanty-Mansi, Yamalo-Nenets, Sakha — none of
which had cards, so none were in the polygon map, so the union skipped them
and the quiz only accepted Karelia/Murmansk/Novgorod).

Fix: for any country that already has *some* sub-region polygons, also
include every other admin-1 region of that country, indexed by every
plausible spelling we can extract from the admin-1 properties.
"""
import json
import re
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ADMIN1 = REPO / 'extension' / 'data' / 'admin1.geojson'
MAP_PATH = REPO / 'extension' / 'data' / 'subregion_polygons.json'
BAK = REPO / 'extension' / 'data' / 'subregion_polygons.json.bak.exhaustive'

if not BAK.exists():
    BAK.write_text(MAP_PATH.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'wrote backup -> {BAK.name}')

cur = json.loads(MAP_PATH.read_text(encoding='utf-8'))
admin1 = json.loads(ADMIN1.read_text(encoding='utf-8'))


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def name_variants(p):
    """Yield candidate spellings for an admin-1 region from its NE properties."""
    out = set()
    for k in ('name', 'name_alt', 'name_en', 'gn_name', 'gns_name', 'woe_name'):
        v = p.get(k)
        if not v or not isinstance(v, str):
            continue
        for piece in re.split(r'\s*\|\s*', v):
            piece = piece.strip()
            if not piece:
                continue
            out.add(piece)
            no_paren = re.sub(r'\s*\([^)]*\)\s*$', '', piece).strip()
            if no_paren and no_paren != piece:
                out.add(no_paren)
                m = re.search(r'\(([^)]+)\)', piece)
                if m:
                    out.add(m.group(1).strip())
            no_apo = piece.replace("'", '')
            if no_apo and no_apo != piece:
                out.add(no_apo)
            trimmed = re.sub(
                r'\s+(Krai|Oblast|Republic|Federal Subject|Autonomous (?:Okrug|Oblast)|Okrug)$',
                '', piece, flags=re.I).strip()
            if trimmed and trimmed != piece:
                out.add(trimmed)
            acc = strip_accents(piece)
            if acc and acc != piece:
                out.add(acc)
    return {n for n in out if n and len(n) >= 3}


# Country-specific manual aliases for region names that commonly appear in
# meta descriptions but don't show up in any of NE's admin-1 fields.
EXTRA_ALIASES = {
    ('RU', 'Khanty-Mansiy'):     ['Khanty-Mansi', 'Khanty Mansi', 'Khanty-Mansiysk'],
    ('RU', 'Yamal-Nenets'):      ['Yamalo-Nenets', 'Yamalo Nenets', 'Yamal Nenets'],
    ('RU', 'Sakha (Yakutia)'):   ['Sakha', 'Yakutia', 'Yakut'],
    ('RU', 'Nizhegorod'):        ['Nizhny Novgorod', 'Nizhniy Novgorod'],
    ('RU', 'Tyva'):              ['Tuva'],
    ('RU', 'Maga Buryatdan'):    ['Buryatia', 'Buryat'],
    ('RU', 'Yevrey'):            ['Jewish Autonomous', 'Jewish'],
    ('RU', 'Mariy-El'):          ['Mari El', 'Mariy El'],
    ('RU', "Arkhangel'sk"):      ['Arkhangelsk'],
    ('RU', "Astrakhan'"):        ['Astrakhan'],
    ('RU', "Perm'"):             ['Perm'],
    ('RU', "Primor'ye"):         ['Primorsky', 'Primorye'],
    ('RU', "Ryazan'"):           ['Ryazan'],
    ('RU', "Stavropol'"):        ['Stavropol'],
    ('RU', "Tver'"):             ['Tver'],
    ('RU', "Tyumen'"):           ['Tyumen'],
    ('RU', "Ul'yanovsk"):        ['Ulyanovsk'],
    ('RU', "Yaroslavl'"):        ['Yaroslavl'],
    ('RU', 'Moskva'):            ['Moscow City'],
    ('RU', 'Moskovskaya'):       ['Moscow Oblast', 'Moscow Region'],
    ('RU', 'Khakass'):           ['Khakassia'],
    ('RU', 'Komi'):              ['Komi Republic'],
    ('RU', 'Kabardin-Balkar'):   ['Kabardino-Balkaria', 'Kabardino Balkaria'],
    ('RU', 'Karachay-Cherkess'): ['Karachay-Cherkessia', 'Karachay Cherkess'],
    ('RU', 'Adygey'):            ['Adygea'],
    ('RU', 'Ingush'):             ['Ingushetia'],
    ('RU', 'Chukchi Autonomous Okrug'): ['Chukotka'],
    ('RU', 'Gorno-Altay'):       ['Altai Republic'],
    ('RU', 'Altay'):             ['Altai Krai'],
    ('GB', 'Greater London'):    ['London'],
    ('GB', 'Northern Ireland'):  ['NI'],
}

by_cc = {}
for f in admin1['features']:
    cc = f['properties'].get('iso_a2')
    if not cc:
        continue
    by_cc.setdefault(cc, []).append(f)


def fid_of(p):
    return p.get('iso_3166_2') or p.get('code_local') or f"{p.get('iso_a2')}-{(p.get('name') or 'X')[:8]}"


added_by_cc = {}
total_added = 0
for cc, regions_map in cur.items():
    feats = by_cc.get(cc, [])
    existing_ids = set()
    for v in regions_map.values():
        if isinstance(v, list):
            existing_ids.update(v)
        else:
            existing_ids.add(v)
    added = 0
    for f in feats:
        p = f['properties']
        fid = fid_of(p)
        if fid in existing_ids:
            continue
        primary = p.get('name')
        if not primary:
            continue
        names = name_variants(p)
        for alias in EXTRA_ALIASES.get((cc, primary), []):
            names.add(alias)
        for n in names:
            if n in regions_map:
                continue
            regions_map[n] = fid
            added += 1
    if added:
        added_by_cc[cc] = added
        total_added += added

MAP_PATH.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'\nadded {total_added} region-alias entries across {len(added_by_cc)} countries')
for cc, n in sorted(added_by_cc.items(), key=lambda x: -x[1])[:15]:
    print(f'  {cc}: +{n} aliases')
print(f'\nfinal RU keys: {len(cur["RU"])}  (was 36)')
