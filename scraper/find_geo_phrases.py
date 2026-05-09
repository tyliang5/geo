# -*- coding: utf-8 -*-
"""Scan every sub-region card description across all covered countries and
extract candidate multi-region geographic phrases. Outputs a per-country
list of phrases sorted by frequency, so we can hand-curate the
geographic_aliases.json dictionary instead of guessing.

A "candidate phrase" is any noun phrase that:
  - matches a known geographic descriptor pattern (compass-prefixed,
    "the X" + capitalized noun, "between A and B"), AND
  - is NOT already a single admin-1 region name (those are handled by the
    region-name path in app.js).

Run: python scraper/find_geo_phrases.py
"""
from __future__ import annotations
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
POLY = REPO / 'extension' / 'data' / 'subregion_polygons.json'
ALIASES = REPO / 'extension' / 'data' / 'geographic_aliases.json'

tips = json.loads(TIPS.read_text(encoding='utf-8'))
polygons = json.loads(POLY.read_text(encoding='utf-8'))
aliases = json.loads(ALIASES.read_text(encoding='utf-8'))

# Pattern alternatives for multi-region geographic descriptors
PATTERNS = [
    # "east/west/north/south of the Urals/Andes/etc."
    re.compile(r'\b(east|west|north|south)(?:ern)?\s+(?:of\s+)?(?:the\s+)?([A-Z][a-zA-ZÀ-ſ\-]{3,}(?:\s+[A-Z][a-zA-ZÀ-ſ\-]+){0,2})\b'),
    # "the Caucasus / the Pampa / the Outback / the Midwest"
    re.compile(r'\bthe\s+([A-Z][a-zA-ZÀ-ſ\-]{4,}(?:\s+[A-Z][a-zA-ZÀ-ſ\-]+){0,2})\b'),
    # "Northern X / Southern X / Eastern X / Western X / Central X"
    re.compile(r'\b(Northern|Southern|Eastern|Western|Central|Coastal|Inland|Upper|Lower)\s+([A-Z][a-zA-ZÀ-ſ\-]{2,})\b'),
    # "X coast", "X region"
    re.compile(r'\b([A-Z][a-zA-ZÀ-ſ\-]{3,})\s+(coast|region|peninsula|highlands|lowlands|islands|provinces|states)\b', re.I),
    # "between A and B"
    re.compile(r'\bbetween\s+([A-Z][a-zA-ZÀ-ſ\-]+(?:\s+[A-Z][a-zA-ZÀ-ſ\-]+){0,2})\s+and\s+([A-Z][a-zA-ZÀ-ſ\-]+(?:\s+[A-Z][a-zA-ZÀ-ſ\-]+){0,2})\b'),
]

# Phrases that look geographic but are noise / not multi-region
SKIP = {
    'sea', 'ocean', 'river', 'mountain', 'mountains', 'desert', 'forest', 'forests',
    'lake', 'island', 'islands', 'park', 'national', 'parks', 'street', 'road',
    'roads', 'house', 'houses', 'border', 'capital', 'city', 'town',
    'country', 'world', 'continent', 'state', 'states', 'language',
    'languages', 'people', 'population', 'culture', 'history',
}


def normalize(s):
    return s.strip().lower()


def collect_phrases():
    out = defaultdict(Counter)   # cc -> phrase -> count
    for cc, c in tips.items():
        if cc == '_meta' or not isinstance(c, dict):
            continue
        regions = c.get('regions') or {}
        # Only emit phrases for countries that have sub-region polygons —
        # phrases for other countries can't expand anyway.
        if cc not in polygons:
            continue
        admin1_names = {n.lower() for n in polygons.get(cc, {}).keys()}
        for region_name, entries in regions.items():
            for e in entries:
                text = f"{e.get('title') or ''} {e.get('text') or e.get('description') or ''}"
                if not text.strip():
                    continue
                for rx in PATTERNS:
                    for m in rx.finditer(text):
                        if m.lastindex == 2:
                            phrase = f"{m.group(1)} {m.group(2)}"
                        else:
                            phrase = m.group(1)
                        phrase = normalize(phrase)
                        if phrase in SKIP:
                            continue
                        # Skip if phrase is itself an admin-1 name
                        if phrase in admin1_names:
                            continue
                        # Skip if phrase is already in aliases
                        cc_aliases = aliases.get(cc, {})
                        if any(phrase == k.lower() for k in cc_aliases.keys() if not k.startswith('_')):
                            continue
                        out[cc][phrase] += 1
    return out


def main():
    phrases_per_cc = collect_phrases()
    print(f'\nUnmatched geographic phrases per country (showing top 15 each, freq >= 2):\n')
    for cc in sorted(phrases_per_cc.keys()):
        common = [(p, n) for p, n in phrases_per_cc[cc].most_common() if n >= 2]
        if not common:
            continue
        print(f'\n{cc}: ({len(common)} distinct phrases used >= twice)')
        for p, n in common[:25]:
            print(f'  {n:3d}  "{p}"')


if __name__ == '__main__':
    main()
