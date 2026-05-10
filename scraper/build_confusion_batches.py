# -*- coding: utf-8 -*-
"""Build batches for the confused-pair audit.

Groups every quizzable card by a normalised meta-type ("bollard",
"guardrail", "road marking", etc.) so an agent can look at all the
cards in one category at once and cluster the ones that look visually
similar across countries — those are the cards a player is most likely
to confuse for one another.

Output: $TEMP/plonkit_confusion_audit/batch_NNN.json — one batch per
category, each containing every card with that type. Agent emits a
list of clusters (each cluster = list of cardKeys that look the same
to the eye).

Categories with <8 cards or where every card is from the same country
are skipped — confusion only matters across countries.
"""
import json
import re
import hashlib
import collections
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
BL = REPO / 'extension' / 'data' / 'giveaway_blacklist.json'
CACHE = REPO / 'scraper' / '.image_cache'
OUT_DIR = Path.home() / 'AppData/Local/Temp/plonkit_confusion_audit'


def cache_path_for(url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    ext = Path(urlparse(url).path).suffix.lower() or '.bin'
    return CACHE / (h + ext)


def normalise_type(raw: str) -> str:
    """Collapse cosmetic differences so 'Bollards' and 'Bollard' merge."""
    s = (raw or '').strip().lower()
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # Strip common suffixes / prefixes that just describe the item but
    # don't change what it is.
    s = re.sub(r's\b', '', s)  # plural -> singular
    return s


def main():
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    bl = json.loads(BL.read_text(encoding='utf-8'))

    by_type = collections.defaultdict(list)
    for cc, c in tips.items():
        if cc == '_meta' or not isinstance(c, dict):
            continue
        country = c.get('name') or cc
        def add(meta, key, region=''):
            if key in bl:
                return
            url = (meta.get('images') or [None])[0]
            if not url:
                return
            lp = (REPO / 'extension' / url) if url.startswith('assets/') \
                 else cache_path_for(url)
            if not lp.exists():
                return
            t = normalise_type(meta.get('type') or '')
            if not t:
                return
            by_type[t].append({
                'key': key, 'cc': cc, 'country': country, 'region': region,
                'type': meta.get('type') or '', 'title': meta.get('title') or '',
                'desc': (meta.get('description') or meta.get('text') or '')[:140],
                'path': str(lp),
            })

        for i, m in enumerate(c.get('metas') or []):
            add(m, f'country:{cc}:{i}')
        for region, entries in (c.get('regions') or {}).items():
            for j, e in enumerate(entries or []):
                add(e, f'country:{cc}:region:{region}:{j}', region)

    # Filter: only keep categories with >=8 cards across >=3 countries.
    keep = {}
    for t, cards in by_type.items():
        if len(cards) < 8:
            continue
        ccs = {c['cc'] for c in cards}
        if len(ccs) < 3:
            continue
        # Cap each category at 200 to keep batches tractable for an agent.
        keep[t] = cards[:200]
    # Sort categories by size desc so the biggest groups (bollards,
    # guardrails) get their own batches first.
    cats = sorted(keep.items(), key=lambda kv: -len(kv[1]))

    print(f'kept {len(cats)} categories, total {sum(len(v) for _, v in cats)} cards')
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUT_DIR.glob('*.json'):
        f.unlink()
    for b, (t, cards) in enumerate(cats):
        (OUT_DIR / f'batch_{b:03d}.json').write_text(
            json.dumps({'category': t, 'cards': cards}, indent=2, ensure_ascii=False),
            encoding='utf-8')
    print(f'wrote {len(cats)} category batches to {OUT_DIR}')
    for t, cards in cats[:10]:
        ccs = sorted({c['cc'] for c in cards})
        print(f'  {len(cards):4d}  {t!r}  {len(ccs)} countries')


if __name__ == '__main__':
    main()
