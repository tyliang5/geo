# -*- coding: utf-8 -*-
"""Catch the remaining "wrong type" reference-map cards: meta cards typed
as Landscape / Architecture / Vegetation / Infrastructure / etc. whose
IMAGE is actually a coverage / elevation / topographic / distribution /
biome / climate / road / highway / area-code / phone-code MAP.

These slip past the compendium / OCR detectors because:
  - The description doesn't lead with "These are…" or "Shown here is…" —
    it talks about the underlying topic (e.g. "Most of Botswana is as flat
    as a pancake") and only mentions the map as supporting evidence.
  - The OCR doesn't always pick up the map's text labels reliably.
  - The image filename is the only strong signal (e.g. *_topo.png,
    *_coverage.png, *_relief_location_map.svg.png).

Detection: any card whose image URL matches the URL_RX pattern below is
flagged with reason 'map_typed_meta'. We do NOT require a description
match — the URL alone is enough since these filenames are unambiguous.
"""
from __future__ import annotations
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
BL = REPO / 'extension' / 'data' / 'giveaway_blacklist.json'

URL_RX = re.compile(
    r'(?:'
    r'coverage[_ ]?map'
    r'|coverage\.(?:png|jpg|jpeg|webp)'
    r'|_coverage[_./]'
    r'|distribution[_ ]?map'
    r'|distribution\.(?:png|jpg|jpeg|webp)'
    r'|topograph(?:ic|y)?'
    r'|_topo[_./]'
    r'|relief[_ ]?(?:map|location)'
    r'|elevation[_ ]?(?:map|location)?'
    r'|altitude[_ ]?map'
    r'|biome[_ ]?map'
    r'|climate[_ ]?map'
    r'|k(?:ö|o)ppen'
    r'|vegetation[_ ]?map'
    r'|soil[_ ]?map'
    r'|geology[_ ]?map'
    r'|population[_ ]?map'
    r'|density[_ ]?map'
    r'|highways?\.(?:png|jpg|jpeg|webp)'
    r'|highways?[_ ]map'
    r'|road[_ ]?map\.'
    r'|areacodes?'
    r'|area[_ ]codes'
    r'|phonecodes?'
    r'|phone[_ ]codes'
    r'|dialingcodes'
    r'|state[_ ]acronyms?'
    r'|country[_ ]acronyms?'
    r'|guide\.(?:png|jpg|jpeg|webp)'
    r'|/guide\.'
    r'|cheatsheet'
    r'|reference[_ ]?(?:map|card)'
    r'|0_[A-Z][a-zA-Z_]*Summary'
    r'|0_[A-Z][a-zA-Z_]*Graphic'
    r'|untitled[_ ]?design'
    r'|infographic'
    r'|[Bb]us[_ ]?[Ss]top'
    r'|[Bb]usstops?'
    r'|comparison\.(?:png|jpg|jpeg|webp)'
    r'|comparison[_ ]chart'
    r'|chart\.(?:png|jpg|jpeg|webp)'
    r'|diagram\.(?:png|jpg|jpeg|webp)'
    r'|pavement[_ ]map'
    r'|paved[_ ]?roads?\.png'
    r'|unpaved'
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
        for i, m in enumerate(c.get('metas') or []):
            url = (m.get('images') or [None])[0] or ''
            if URL_RX.search(url):
                flagged.append((cc, f'country:{cc}:{i}', m.get('type') or '',
                                m.get('title') or '',
                                (m.get('description') or '')[:100], url))
        for region, entries in (c.get('regions') or {}).items():
            for j, e in enumerate(entries or []):
                url = (e.get('images') or [None])[0] or ''
                if URL_RX.search(url):
                    flagged.append((cc, f'country:{cc}:region:{region}:{j}',
                                    e.get('type') or '',
                                    e.get('title') or '',
                                    (e.get('text') or e.get('description') or '')[:100],
                                    url))

    added = 0
    merged = 0
    for cc, k, mtype, title, snippet, url in flagged:
        new_reason = 'map_typed_meta'
        if k in bl:
            old = bl[k].get('reason', '')
            if 'map_typed' not in old and 'compendium' not in old and 'reference_map' not in old:
                bl[k]['reason'] = old + ' / ' + new_reason
                merged += 1
        else:
            bl[k] = {
                'cc': cc,
                'reason': new_reason,
                'detected_text': (snippet.strip() or title or url[-60:]),
            }
            added += 1

    BL.write_text(json.dumps(bl, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'map-typed-meta scan complete:')
    print(f'  {len(flagged)} cards flagged')
    print(f'  {added} added to blacklist')
    print(f'  {merged} merged with existing entries')
    print(f'  blacklist now {len(bl)} total entries')

    print('\nFlagged per country:')
    for cc, n in Counter(c[0] for c in flagged).most_common(25):
        print(f'  {cc}: {n}')


if __name__ == '__main__':
    main()
