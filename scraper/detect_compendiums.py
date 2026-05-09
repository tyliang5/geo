# -*- coding: utf-8 -*-
"""Detect "compendium" / "infographic" cards across all countries — single
images that show MANY different metas (e.g., a Russia bus-stops chart
with 20+ regional styles labeled) instead of one specific meta. These are
useful as study references but useless as quiz cards because the answer
is "everywhere".

We blacklist them with reason='compendium' so they're filtered from quiz
pools but still visible in fact-sheets / region-tips for studying.

Detection signals:
  1. URL keywords: busstops, infographic, chart, diagram, compendium,
     guide, comparison, montage, all_regions, overview, _all_, summary,
     listing, examples, varieties, types_of, kinds_of.
  2. Description patterns: "These are…", "Shown here…", "This map shows",
     "This is a [chart|map|diagram]", "Each […] has its own", phrasing
     that explicitly references the image as a chart/list.
  3. The image is referenced from 3+ different region keys with identical
     descriptions — a strong "this is the master chart" signal.

Adds matches to extension/data/giveaway_blacklist.json with reason
'compendium' (or merges with existing reason).
"""
from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
BL = REPO / 'extension' / 'data' / 'giveaway_blacklist.json'

URL_RX = re.compile(
    r'(?:'
    r'[Bb]us[_ ][Ss]top'
    r'|[Bb]usstop'
    r'|infographic'
    r'|compendium'
    r'|comparison'
    r'|chart\.'
    r'|diagram'
    r'|montage'
    r'|collage'
    r'|all[_ ]regions'
    r'|all[_ ]states'
    r'|overview'
    r'|_summary'
    r'|summary[_ ]graphic'
    r'|summary\.png'
    r'|listing'
    r'|varieties'
    r'|types[_ ]of'
    r'|kinds[_ ]of'
    r'|examples'
    r'|every[_ ](state|region|prefecture|province|department)'
    # Geographic distribution / coverage maps
    r'|coverage[_ ]?map'
    r'|coverage\.png'
    r'|_coverage[_./]'
    r'|distribution[_ ]?map'
    r'|distribution\.png'
    # Topographic / climate / biome reference maps
    r'|topograph(?:ic|y)?'
    r'|_topo[_./]'
    r'|relief[_ ]?map'
    r'|elevation[_ ]?map'
    r'|altitude[_ ]?map'
    r'|biome[_ ]?map'
    r'|climate[_ ]?map'
    r'|k(?:ö|o)ppen'
    r'|vegetation[_ ]?map'
    r'|soil[_ ]?map'
    r'|geology[_ ]?map'
    r'|population[_ ]?map'
    r'|density[_ ]?map'
    # Road / highway / phone reference layouts
    r'|highways?\.png'
    r'|highways?[_ ]map'
    r'|road[_ ]?map\.'
    r'|areacodes?'
    r'|area[_ ]codes'
    r'|phonecodes?'
    r'|phone[_ ]codes'
    r'|dialingcodes'
    r'|state[_ ]acronyms?'
    r'|country[_ ]acronyms?'
    r'|regional[_ ]codes'
    r'|guide\.png'
    r'|guide\.jpg'
    r'|/guide[_/.]'
    r'|cheatsheet'
    r'|reference[_ ]?map'
    r'|reference[_ ]?card'
    # Layout/grid/overview-style file names
    r'|grid\.png'
    r'|grid\.jpg'
    # Plonkit summary/intro graphics often start with 0_
    r'|/0_[A-Z]'
    r'|_0_summary'
    r')',
    re.I,
)

DESC_RX = re.compile(
    r'(?:'
    # Anchored at start of sentence/line:
    r'^\s*(?:'
        r'These are the\b'
        r'|This (?:image|chart|map|diagram|infographic|graphic) (?:shows|displays|illustrates|depicts|highlights)'
        r'|Shown (?:here|in this image|in the image|above|below) (?:is|are)\b'
        r'|Here(?:\'s| is)\s+(?:an?|the)\s+(?:overview|chart|map|diagram|infographic|summary|comparison|guide)'
        r'|Below (?:is|are)\b'
        r'|The (?:image|chart|map|diagram|infographic) (?:shows|displays|illustrates|highlights)'
        r'|Each\s+(?:[A-Z][a-z]+\s+)?(?:state|region|province|prefecture|department|oblast|krai|country)\s+has its own'
        r'|This is a (?:chart|map|diagram|infographic|comparison|guide|listing|summary|graphic|coverage)'
    r')'
    r'|'
    # Anywhere in the description:
    r'\bcoverage[_ ]?map\b'
    r'|\b(?:topographic|topography|relief|elevation|altitude|biome|climate|distribution|vegetation|soil|geological|population|density|köppen)[\s-]+map\b'
    r'|\bclick on the (?:image|chart|map|graphic) to enlarge\b'
    r'|\b(?:see|see this|see the|here\'s|here is) (?:the )?(?:[a-z]+ )?(?:map|chart|infographic|diagram|graphic|guide|distribution)\b'
    r'|\bsummary (?:of|graphic|chart)\b'
    r'|\bcheat[\s-]?sheet\b'
    r'|\boverview (?:of|map|chart)\b'
    r'|\b(?:road|highway|phone|area)\s+code(?:s)?\s+map\b'
    r')',
    re.I | re.M,
)


def main():
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    bl = json.loads(BL.read_text(encoding='utf-8'))

    # First pass: collect all (cardKey, image_url, description) tuples
    cards = []
    img_to_keys = defaultdict(list)   # (cc, url) -> [cardKey,...]
    img_to_descs = defaultdict(list)  # (cc, url) -> [description,...]
    for cc, c in tips.items():
        if cc == '_meta' or not isinstance(c, dict):
            continue
        for i, m in enumerate(c.get('metas') or []):
            url = (m.get('images') or [None])[0]
            if not url:
                continue
            k = f'country:{cc}:{i}'
            desc = m.get('description') or ''
            cards.append((cc, k, url, desc))
            img_to_keys[(cc, url)].append(k)
            img_to_descs[(cc, url)].append(desc)
        for region, entries in (c.get('regions') or {}).items():
            for j, e in enumerate(entries or []):
                url = (e.get('images') or [None])[0]
                if not url:
                    continue
                k = f'country:{cc}:region:{region}:{j}'
                desc = e.get('text') or e.get('description') or ''
                cards.append((cc, k, url, desc))
                img_to_keys[(cc, url)].append(k)
                img_to_descs[(cc, url)].append(desc)

    # Second pass: identify compendiums. A cardKey is a compendium when:
    #   (a) URL matches the keyword regex, OR
    #   (b) description matches the "this image shows…" regex.
    # We do NOT blacklist on cross-region image reuse alone — that's how
    # legitimate multi-region metas (e.g. a cactus that grows in 5 provinces)
    # appear, and the union logic in app.js already accepts any of those
    # regions as correct.
    blacklist_keys = set()
    blacklist_reasons = {}     # cardKey -> reason string
    for cc, k, url, desc in cards:
        reasons = []
        if URL_RX.search(url):
            reasons.append('compendium_url')
        if DESC_RX.search(desc.strip()):
            reasons.append('compendium_desc')
        if reasons:
            blacklist_keys.add(k)
            blacklist_reasons[k] = ' / '.join(sorted(set(reasons)))

    added = 0
    merged = 0
    for k in sorted(blacklist_keys):
        cc = k.split(':')[1]
        new_reason = 'compendium (' + blacklist_reasons[k] + ')'
        if k in bl:
            old = bl[k].get('reason', '')
            if 'compendium' not in old:
                bl[k]['reason'] = old + ' / ' + new_reason
                merged += 1
        else:
            # Find the card to capture a snippet
            snippet = ''
            for c2, k2, url2, desc2 in cards:
                if k2 == k:
                    snippet = (desc2[:120].strip() or url2[-60:])
                    break
            bl[k] = {
                'cc': cc,
                'reason': new_reason,
                'detected_text': snippet,
            }
            added += 1

    BL.write_text(json.dumps(bl, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'compendium scan complete:')
    print(f'  {len(blacklist_keys)} cards flagged')
    print(f'  {added} added to blacklist')
    print(f'  {merged} merged with existing entries')
    print(f'  blacklist now {len(bl)} total entries')

    # Top countries
    from collections import Counter
    by_cc = Counter(k.split(':')[1] for k in blacklist_keys)
    print(f'\nFlagged per country:')
    for cc, n in by_cc.most_common(20):
        print(f'  {cc}: {n}')


if __name__ == '__main__':
    main()
