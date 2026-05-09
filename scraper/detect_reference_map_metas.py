# -*- coding: utf-8 -*-
"""Detect "reference map" / infographic metas — images that ARE the answer
(topographic relief maps of a country, infographics with country-shape
outlines, climate distribution maps, etc.). These are useful for studying
but useless as quiz cards in country-ID mode.

Adds matching cardKeys to extension/data/giveaway_blacklist.json with
reason=reference_map. Merges with existing OCR-detected entries.
"""
from __future__ import annotations
import json
import re
from urllib.parse import unquote
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
BL = REPO / 'extension' / 'data' / 'giveaway_blacklist.json'

URL_RX = re.compile(
    r'(?:terrain[_-]map|topograph(?:ic|y)|relief[_-]?map|elevation[_-]?map|[_-]map[_-]of[_-]|infographic|outline[_-]of|distribution[_-]map|sciencepics|wikimedia|wikipedia|britannica|_coverage\.png|coverage_map)',
    re.I,
)
DESC_RX = re.compile(
    r'\b(topograph(?:ic|y)|relief map|elevation map|terrain map|altitude map|infographic|biome map|climate map|outline of|distribution of|here\'?s? (?:a|the) map|see (?:this|the) (?:map|infographic|chart|diagram))\b',
    re.I,
)


def main() -> None:
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    bl = json.loads(BL.read_text(encoding='utf-8'))

    added = 0
    for cc, c in tips.items():
        if cc == '_meta':
            continue
        for i, m in enumerate(c.get('metas') or []):
            url = (m.get('images') or [None])[0] or ''
            text = f"{m.get('title') or ''} {m.get('description') or ''}"
            if URL_RX.search(unquote(url)) or DESC_RX.search(text):
                key = f'country:{cc}:{i}'
                if key not in bl or '_meta' == key.split(':')[0]:
                    bl[key] = {
                        'cc': cc,
                        'reason': 'reference_map',
                        'detected_text': (text[:120].strip() or url[-80:]),
                    }
                    added += 1
                else:
                    # Already in OCR blacklist — keep existing reason but note both
                    if 'reference_map' not in bl[key].get('reason', ''):
                        bl[key]['reason'] = bl[key].get('reason', '') + ' / reference_map'

    BL.write_text(json.dumps(bl, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'added {added} reference-map entries to blacklist (total: {len(bl)})')


if __name__ == '__main__':
    main()
