# -*- coding: utf-8 -*-
"""Audit every sub-region meta across every country to find:

  (1) FALSE POSITIVES — comparison/contrast mentions of other regions
      that the runtime would incorrectly add as a "correct" answer.
  (2) MISSED LEGIT MULTI-REGION metas — descriptions that clearly say
      a feature is "in X and Y" but only one is captured.
  (3) Edge cases the comparison-phrase regex doesn't catch.

Output: scraper/_subregion_audit.json + a printed summary.
Run: python scraper/audit_subregion_mentions.py
"""
from __future__ import annotations
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
SUBS = REPO / 'extension' / 'data' / 'subregion_polygons.json'
OUT = REPO / 'scraper' / '_subregion_audit.json'

# Same regex shipped in app.js — keep them lockstep.
COMPARISON_BEFORE_RX = re.compile(
    r'(?:'
    r'\b(?:reminiscent of|similar(?:ly)? to|unlike|compared (?:to|with)|than|instead of|vs\.?|versus|akin to|resembles?|resembling|reminds (?:you )?of|but not|except|whereas|rather than|missing from|absent from|not (?:found |seen |present )?in)\s+(?:the\s+)?(?:that of\s+)?'
    r'|'
    r'\b(?:looks?|looking|seems?|seemed|feels?|felt|appears?|appeared|kinda|sorta)\s+like\s+(?:the\s+)?'
    r'|'
    r'(?:^|[.!?]\s+)Like\s+(?:the\s+)?'
    r')$',
    re.I,
)
# Strong location signals — if any of these phrases precedes the region name,
# very likely a real location reference, not a comparison.
LOCATION_BEFORE_RX = re.compile(
    r'\b(found in|seen in|located in|present in|common in|specific to|exclusive to|only in|throughout|across|in (?:northern|southern|eastern|western|central|the (?:north|south|east|west|north-?west|north-?east|south-?west|south-?east) of)?|and(?: in)?|as well as|both)\s+(?:the\s+)?$',
    re.I,
)


def classify_mention(before: str) -> str:
    """Classify a region-name mention based on its preceding text."""
    if COMPARISON_BEFORE_RX.search(before):
        return 'comparison'
    if LOCATION_BEFORE_RX.search(before):
        return 'location_strong'
    return 'location_default'


def main() -> None:
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    subs = json.loads(SUBS.read_text(encoding='utf-8'))

    audit = []
    summary = Counter()

    for cc, region_map in subs.items():
        if cc.startswith('_'):
            continue
        c = tips.get(cc) or {}
        regions = c.get('regions') or {}
        if not regions:
            continue
        all_names = sorted(region_map.keys(), key=len, reverse=True)
        for source_region, poly_ids in region_map.items():
            entries = regions.get(source_region) or []
            for idx, e in enumerate(entries):
                if not (e.get('images') or [None])[0]:
                    continue
                text = f"{e.get('title') or ''} {e.get('text') or e.get('description') or ''}"
                mentions = []
                for other in all_names:
                    if other == source_region:
                        continue
                    rx = re.compile(r'\b' + re.escape(other) + r'\b', re.I)
                    m = rx.search(text)
                    if not m:
                        continue
                    before = text[max(0, m.start() - 40):m.start()]
                    classification = classify_mention(before)
                    mentions.append({
                        'other_region': other,
                        'classification': classification,
                        'preceding_text': before.strip()[-30:],
                        'matched_at': text[max(0, m.start() - 5):min(len(text), m.end() + 25)],
                    })
                    summary[classification] += 1
                if mentions:
                    audit.append({
                        'cc': cc,
                        'source_region': source_region,
                        'meta_idx': idx,
                        'meta_type': e.get('type') or '',
                        'snippet': text.strip()[:300],
                        'other_regions_mentioned': mentions,
                    })

    OUT.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {OUT.relative_to(REPO)}')
    print(f'\n=== Summary ({sum(summary.values())} total mentions across {len(audit)} metas) ===')
    for k, v in summary.most_common():
        print(f'  {v:4d}  {k}')

    # Spotlight ambiguous cases (default-location with no strong signal — these
    # are most likely to be classification errors).
    ambiguous = [a for a in audit if any(m['classification'] == 'location_default' for m in a['other_regions_mentioned'])]
    print(f'\n=== Default-location (no strong "found in" signal): {len(ambiguous)} metas ===')
    print('Sampling 20 — review these first:')
    for a in ambiguous[:20]:
        for m in a['other_regions_mentioned']:
            if m['classification'] != 'location_default':
                continue
            print(f'  {a["cc"]}/{a["source_region"][:18]:<18} -> {m["other_region"][:18]:<18}'
                  f' | "{m["preceding_text"]}|{m["matched_at"]}"')

    # Spotlight comparisons (these we filter out — review to ensure we're not
    # over-filtering valid locations).
    comp = [a for a in audit if any(m['classification'] == 'comparison' for m in a['other_regions_mentioned'])]
    print(f'\n=== Comparison-skipped: {len(comp)} metas ===')
    print('Sampling 20 — review these to confirm we should skip them:')
    for a in comp[:20]:
        for m in a['other_regions_mentioned']:
            if m['classification'] != 'comparison':
                continue
            print(f'  {a["cc"]}/{a["source_region"][:18]:<18} -> {m["other_region"][:18]:<18}'
                  f' | "{m["preceding_text"]}|{m["matched_at"]}"')


if __name__ == '__main__':
    main()
