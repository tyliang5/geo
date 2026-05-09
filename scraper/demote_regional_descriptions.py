# -*- coding: utf-8 -*-
"""Demote country-level metas whose descriptions are clearly REGIONAL (about
a specific town/area) into regions{}. The earlier rescue_stranded script
moved everything from junk-keyed regions into metas[] indiscriminately;
many of those were genuinely regional descriptions like "Ambanja can be
recognized by..." that should stay regional.

Heuristic: description matches a "<TownName> can be recognized by..." or
"<TownName> is" pattern, meaning the meta is about a specific place inside
the country, not a country-wide feature.

These regional metas often use plonkit images that include a country-outline
overlay — appearing in country-ID quiz makes them giveaways.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
BAK = REPO / 'extension' / 'data' / 'tips.json.bak4'

# Patterns that strongly suggest "this is a specific named place"
REGIONAL_PATTERNS = [
    # "Ambanja can be recognized by..." / "St Augustin is..." / "Toliara has..."
    re.compile(r'^([A-Z][a-zA-Z\.\']+(?:\s+[A-Z][a-zA-Z\.\']+){0,3})\s+(?:can be|is|has|features|contains|shows)\b'),
    # "The town of X" / "The village of X" / "The island of X"
    re.compile(r'\bthe\s+(?:town|village|city|island|atoll|park|trekker)\s+of\s+[A-Z]'),
    # "X National Park" / "X Forest" — proper noun + place type
    re.compile(r'\b[A-Z][a-zA-Z]+\s+(?:National Park|Forest|Beach|Bay|River|Mountain|Valley|Reserve|Coast|Massif)\b'),
    # "between X and Y" — often regional
    re.compile(r'\bbetween\s+[A-Z][a-zA-Z]+\s+and\s+[A-Z]'),
    # "near X" / "around X" / "in X" + Capital
    re.compile(r'\b(?:near|around|south\s+of|north\s+of|east\s+of|west\s+of)\s+[A-Z][a-zA-Z]{3,}'),
]


def looks_regional(description: str) -> bool:
    if not description:
        return False
    text = description.strip()
    return any(rx.search(text) for rx in REGIONAL_PATTERNS)


def main() -> None:
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    if not BAK.exists():
        BAK.write_text(TIPS.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'wrote backup -> {BAK.name}')

    demoted = 0
    countries_touched = 0

    for cc, c in tips.items():
        if cc == '_meta':
            continue
        metas = c.get('metas') or []
        if not metas:
            continue
        keep = []
        local_demoted = 0
        for m in metas:
            if not (m.get('images') or [None])[0]:
                keep.append(m)
                continue
            desc = m.get('description') or m.get('text') or ''
            if looks_regional(desc):
                # Move to regions{} under a generic "Local areas" key —
                # not quizzable in country-ID, available for fact-sheet study.
                regions = c.setdefault('regions', {})
                regions.setdefault('Local areas', []).append({
                    'type': m.get('type') or 'Region',
                    'title': m.get('title') or '',
                    'text': desc,
                    'description': desc,
                    'comparison': m.get('comparison') or '',
                    'images': m.get('images') or [],
                    'from_maps': m.get('from_maps') or [],
                })
                local_demoted += 1
            else:
                keep.append(m)
        if local_demoted:
            countries_touched += 1
            demoted += local_demoted
            c['metas'] = keep

    TIPS.write_text(json.dumps(tips, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'demoted {demoted} location-specific metas across {countries_touched} countries')
    print('(moved from metas[] to regions["Local areas"][] — visible in fact-sheet, hidden from country-ID quiz)')


if __name__ == '__main__':
    main()
