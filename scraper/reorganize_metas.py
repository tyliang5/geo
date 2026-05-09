"""Reorganize tips.json: move regional metas (those describing sub-region-
specific features) from each country's metas[] into its regions{} so the
country-ID quiz pool is clean.

A meta is "regional" if its description matches REGIONAL_PATTERN — same regex
as the runtime filter in app.js (kept in lockstep).

Output: extension/data/tips.json (overwritten).
Backup: extension/data/tips.json.bak (one-time).
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
BACKUP = TIPS.with_suffix('.json.bak')

REGIONAL_PATTERN = re.compile(
    r'\b(north|south|east|west)(ern|wards?)?\b\s+(of|part|side|region|coast|portion|half)\b'
    r'|\bsee (this|the) map\b'
    r'|\bin (this|these) regions?\b'
    r'|\b(most(?:ly)?|commonly|usually|specifically|only|mainly|primarily|predominantly|chiefly|exclusively) (found|seen|located|present|observed) in\b'
    r'|\b(specific|distinct|exclusive|native|endemic|particular|unique) to\b'
    r'|\b(around|near) [A-Z][a-zA-Z]+\b'
    r'|\b(Northern|Southern|Eastern|Western) [A-Z][a-z]+\b'
    r'|\bin the (north|south|east|west)\b',
    re.IGNORECASE,
)

# Region name extraction. We try to pull a plausible region label from the
# description. If we can't, fall back to "General regional".
REGION_NAME_RX = [
    re.compile(r'\b((?:Northern|Southern|Eastern|Western|Central|North|South|East|West)\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b'),
    re.compile(r'\baround\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b'),
    re.compile(r'\bnear\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b'),
    re.compile(r'\bin\s+(?:the\s+)?(north|south|east|west)(?:ern)?(?:\s+([a-zA-Z]+))?\b', re.I),
]


def extract_region(text: str) -> str:
    for rx in REGION_NAME_RX:
        m = rx.search(text)
        if not m:
            continue
        groups = [g for g in m.groups() if g]
        return ' '.join(groups).title().strip()
    return 'General Region'


def is_regional(m: dict) -> bool:
    text = f"{m.get('title') or ''} {m.get('description') or ''} {m.get('type') or ''}"
    return bool(REGIONAL_PATTERN.search(text))


def meta_to_region_entry(m: dict) -> dict:
    """Convert metas[] format to regions{regionName}[] format."""
    return {
        'text': m.get('description') or '',
        'images': m.get('images') or [],
        'type': m.get('type') or '',
        'title': m.get('title') or '',
        'comparison': m.get('comparison') or '',
        'from_maps': m.get('from_maps') or [],
    }


def main() -> None:
    if not BACKUP.exists():
        BACKUP.write_text(TIPS.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'wrote backup -> {BACKUP.name}')

    tips = json.loads(TIPS.read_text(encoding='utf-8'))

    moved_total = 0
    region_distribution = Counter()
    countries_touched = 0

    for cc, c in tips.items():
        if cc == '_meta':
            continue
        metas = c.get('metas') or []
        if not metas:
            continue
        keep = []
        moved_for_country = 0
        for m in metas:
            if is_regional(m):
                region = extract_region(f"{m.get('title') or ''} {m.get('description') or ''}")
                c.setdefault('regions', {}).setdefault(region, []).append(meta_to_region_entry(m))
                moved_for_country += 1
                region_distribution[region] += 1
            else:
                keep.append(m)
        if moved_for_country:
            countries_touched += 1
            moved_total += moved_for_country
            c['metas'] = keep

    TIPS.write_text(
        json.dumps(tips, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    print(f'moved {moved_total} regional metas across {countries_touched} countries')
    print(f'top region labels:')
    for label, n in region_distribution.most_common(15):
        print(f'  {label!r}: {n}')


if __name__ == '__main__':
    main()
