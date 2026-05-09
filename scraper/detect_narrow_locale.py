# -*- coding: utf-8 -*-
"""Detect Cars/Trekker/Coverage Meta cards that point at a SINGLE specific
small location (one island, one road, one parking lot) rather than a broad
country-wide rule. The plonkit example: "Santa Catalina car — This island
to the south of Los Angeles has a unique Google car." The image is just a
generic Google car shot; identifying it as USA/Catalina requires niche
prior knowledge that doesn't generalize.

These cards are valid for advanced country-streaks but useless noise for a
beginner learning broad country metas. Blacklisting them with reason
'narrow_locale' filters them out of all quiz pools.
"""
from __future__ import annotations
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
BL = REPO / 'extension' / 'data' / 'giveaway_blacklist.json'

# Coverage / car / trekker meta types — the only types we apply this filter to
CAR_TYPES = {
    'car meta', 'car', 'unique car', 'snorkel', 'snorkels', 'trekker',
    'coverage meta', 'low cam', 'low car', 'follow car', 'pickup car', 'high cam',
}

# A description is "narrow" if it points at a single small place
NARROW_RX = re.compile(
    r'(?:'
    r'\bthis\s+(?:island|town|village|car|truck|trekker|vehicle|coverage|harbour|harbor|port|street|road|stretch|highway|route|bay|valley|park|resort|distillery|volcano|glacier)\b'
    r'|\bon\s+(?:the\s+)?(?:island|main\s+island|the\s+islands?)\s+of\s+\w+'
    r'|\b(?:found\s+)?(?:to\s+the\s+)?(?:north(?:east|west)?|south(?:east|west)?|east|west|near|around|south\s+of|north\s+of|east\s+of|west\s+of|northeast\s+of|northwest\s+of|southeast\s+of|southwest\s+of)\s+(?:[A-Z][a-zA-Z]+\s+){0,3}'
    r'|\bin\s+(?:the\s+)?(?:tiny|small|specific|single)\s+'
    r'|\b(?:exclusively|only|uniquely)\s+(?:found|seen|covered|driven)\s+(?:in|on|at)\s+'
    r'|\bcovered\s+by\s+(?:a\s+)?(?:trekker|boat|horse|volcano)'
    r'|\bonly\s+island\s+with\s+'
    r'|\b(?:on|along)\s+(?:Highway|Route|Road|highway|route|road)\s+\d+'
    r'|\b(?:on\s+)?(?:Ilha|Île|Isla|Insel)\b'   # foreign-language "island"
    r')',
    re.I,
)

# Broad-coverage descriptors override the narrow signal — these talk about
# whole-country or large-region metas which ARE useful for learning.
BROAD_RX = re.compile(
    r'(?:'
    r'\b(?:throughout|across|nationwide|country-?wide|all over|in\s+all\s+coverage|all\s+coverage|everywhere)\b'
    r'|\b(?:most|much)\s+of\s+(?:the\s+country|the\s+nation|coverage)\b'
    r')',
    re.I,
)


def main():
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    bl = json.loads(BL.read_text(encoding='utf-8'))

    flagged = []
    for cc, c in tips.items():
        if cc == '_meta' or not isinstance(c, dict):
            continue
        # metas[]
        for i, m in enumerate(c.get('metas') or []):
            t = (m.get('type') or '').lower()
            if t not in CAR_TYPES:
                continue
            desc = m.get('description') or ''
            title = m.get('title') or ''
            text = f'{title} {desc}'
            if NARROW_RX.search(text) and not BROAD_RX.search(text):
                flagged.append((cc, f'country:{cc}:{i}', m.get('type'), title, desc[:120]))
        # regions[] — same check
        for region, entries in (c.get('regions') or {}).items():
            for j, e in enumerate(entries or []):
                t = (e.get('type') or '').lower()
                if t not in CAR_TYPES:
                    continue
                desc = e.get('text') or e.get('description') or ''
                title = e.get('title') or ''
                text = f'{title} {desc}'
                if NARROW_RX.search(text) and not BROAD_RX.search(text):
                    flagged.append((cc, f'country:{cc}:region:{region}:{j}', e.get('type'), title, desc[:120]))

    added = 0
    merged = 0
    for cc, k, t, title, snippet in flagged:
        new_reason = 'narrow_locale'
        if k in bl:
            old = bl[k].get('reason', '')
            if 'narrow_locale' not in old:
                bl[k]['reason'] = old + ' / ' + new_reason
                merged += 1
        else:
            bl[k] = {
                'cc': cc,
                'reason': new_reason,
                'detected_text': (snippet.strip() or title or t),
            }
            added += 1

    BL.write_text(json.dumps(bl, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'narrow-locale scan complete:')
    print(f'  {len(flagged)} cards flagged')
    print(f'  {added} added to blacklist')
    print(f'  {merged} merged with existing entries')
    print(f'  blacklist now {len(bl)} total entries')

    print('\nFlagged per country:')
    for cc, n in Counter(c[0] for c in flagged).most_common(20):
        print(f'  {cc}: {n}')


if __name__ == '__main__':
    main()
