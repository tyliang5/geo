# -*- coding: utf-8 -*-
"""Re-derive meta `type` from description content for metas that currently
have generic types like "Region" / blank / unset. The earlier rescue_stranded
script defaulted everything to "Region", which broke the Bollards / Architecture
/ Coverage / etc. focus topics — they couldn't filter by type anymore.

Heuristic: scan description text for category keywords, pick the strongest
match. If no match, leave as-is.

Run: python scraper/reclassify_meta_types.py
"""
from __future__ import annotations
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
BAK = REPO / 'extension' / 'data' / 'tips.json.bak3'

# Keyword → type. Order matters: the FIRST match wins. Specific patterns
# come before generic ones.
RULES = [
    # Vehicle / coverage
    (r'\bsnorkel\b', 'Snorkel'),
    (r'\b(google car|street view car|car can be (?:seen|recognized|recognised)|the car has|car meta)\b', 'Car Meta'),
    (r'\b(unique car|distinctive car|rare car)\b', 'Unique Car'),
    (r'\btrekker\b', 'Trekker'),
    (r'\b(black car|follow car|car following)\b', 'Follow Car'),
    (r'\bpickup\b', 'Pickup Car'),
    (r'\b(low.?cam|low camera)\b', 'Low Cam'),
    (r'\b(coverage meta|coverage type|generation [234]|gen ?[234]|gen-?[234])\b', 'Coverage Meta'),
    # Bollards (very common visual meta)
    (r'\bbollards?\b', 'Bollard'),
    # Plates
    (r'\b(license plate|number plate|registration plate|plate)\b', 'License Plate'),
    (r'\byellow plates?\b', 'Yellow Plates'),
    # Poles / utility
    (r'\b(holey pole|pole with hole)\b', 'Holey Pole'),
    (r'\b(ladder pole)\b', 'Ladder Poles'),
    (r'\b(pair pole|two poles)\b', 'Pair Poles'),
    (r'\b(utility pole|telephone pole|wooden pole|concrete pole|electric pole|pole top|pole marking)\b', 'Pole'),
    # Signs
    (r'\b(stop sign|alto sign|pare sign)\b', 'Stop Sign'),
    (r'\b(speed limit sign)\b', 'Speed Limit Sign'),
    (r'\b(give way|yield sign)\b', 'Give Way Sign'),
    (r'\b(town sign|city sign|village sign|town entrance)\b', 'Town Signs'),
    (r'\b(highway shield|route shield|interstate shield)\b', 'Highway Shield'),
    (r'\b(no passing zone|no overtaking)\b', 'No Passing Sign'),
    (r'\b(direction sign|distance sign|signpost)\b', 'Direction Signs'),
    (r'\b(kilometre marker|kilometer marker|km marker|highway marker|mile marker)\b', 'Kilometre Markers'),
    # Road
    (r'\b(road line|center line|edge line|yellow line|white line|double yellow)\b', 'Roadlines'),
    (r'\b(chevron)s?\b', 'Chevrons'),
    (r'\b(curb|kerb|sidewalk edge)\b', 'Curbs'),
    (r'\b(guardrail|crash barrier)\b', 'Guardrail Endings'),
    (r'\b(pedestrian crossing|crosswalk|zebra crossing)\b', 'Pedestrian Crossing'),
    # Architecture / buildings
    (r'\b(stone building|stone wall|stone hous)\b', 'Stone Buildings'),
    (r'\b(stilt house|stilt building|raised house)\b', 'Stilt Houses'),
    (r'\b(thatched roof|wooden roof|red roof|tile roof|slate roof|tin roof|metal roof|roofing)\b', 'Architecture'),
    (r'\b(house|building|architectur|villa)\b', 'Architecture'),
    # Vegetation
    (r'\b(eucalyptus|palm tree|pine tree|olive tree|baobab|cactus|bamboo)\b', 'Vegetation'),
    (r'\b(corn field|wheat field|rice paddy|vineyard|olive grove|farmland)\b', 'Agriculture'),
    (r'\b(vegetation|forest|jungle|grass|shrub|bush|biome)\b', 'Vegetation'),
    # Landscape
    (r'\b(mountain|peak|valley|plateau|plain|desert|tundra|coast|beach|fjord|river|lake|island)\b', 'Landscape'),
    (r'\b(landscape|terrain|topography|elevation)\b', 'Landscape'),
    # Language / scripts
    (r'\b(script|alphabet|language|cyrillic|arabic|hangul|devanagari|kana|hanzi)\b', 'Language'),
    (r'\b(street name|road name)\b', 'Street Name Ending'),
    # Fall-throughs
    (r'\b(infrastructure|utilit|bridge|tunnel|cable)\b', 'Infrastructure'),
]


def classify(description: str) -> str | None:
    if not description:
        return None
    text = description.lower()
    for pattern, label in RULES:
        if re.search(pattern, text):
            return label
    return None


def main() -> None:
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    if not BAK.exists():
        BAK.write_text(TIPS.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'wrote backup -> {BAK.name}')

    # Generic types we want to override if we can derive a more specific one.
    GENERIC_TYPES = {'', 'region', 'general', 'other', 'misc', 'meta'}

    changed = 0
    type_changes = Counter()
    for cc, c in tips.items():
        if cc == '_meta':
            continue
        for m in c.get('metas') or []:
            current = (m.get('type') or '').strip()
            if current.lower() not in GENERIC_TYPES:
                continue
            text = (m.get('title') or '') + ' ' + (m.get('description') or m.get('text') or '')
            new_type = classify(text)
            if new_type and new_type != current:
                type_changes[(current or 'EMPTY', new_type)] += 1
                m['type'] = new_type
                changed += 1

    TIPS.write_text(json.dumps(tips, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'reclassified {changed} metas')
    print('\nTop transitions:')
    for (old, new), n in type_changes.most_common(20):
        print(f'  {n:4d}  {old!r}  ->  {new!r}')


if __name__ == '__main__':
    main()
