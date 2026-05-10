# -*- coding: utf-8 -*-
"""Build the input batches for the per-image giveaway-mask visual audit.

Goal: for every quizzable card whose image LIKELY contains a giveaway
region (country name in image, plonkit.net watermark, country-outline
inset, region label), have an agent identify the bounding box of the
giveaway so we can mask just that area instead of hiding the whole card.

We emit one per-batch JSON file under
$TEMP/plonkit_mask_audit/batch_NNN.json. Each entry is:
  {
    'key':  cardKey (`country:CC:i` or `country:CC:region:Name:j`),
    'cc':   ISO2,
    'type': meta type,
    'title': meta title,
    'desc': first 140 chars of description,
    'path': absolute filesystem path to the image,
    'is_blacklisted': bool — already in giveaway_blacklist
  }

We INCLUDE blacklisted cards because for many of them ("country_name_in_image"
etc.) the right fix is to mask the giveaway, not hide the card.
"""
import json
import hashlib
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
BL = REPO / 'extension' / 'data' / 'giveaway_blacklist.json'
CACHE = REPO / 'scraper' / '.image_cache'
OUT_DIR = Path.home() / 'AppData/Local/Temp/plonkit_mask_audit'

BATCH_SIZE = 150


def cache_path_for(url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    ext = Path(urlparse(url).path).suffix.lower() or '.bin'
    return CACHE / (h + ext)


def main():
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    bl = json.loads(BL.read_text(encoding='utf-8'))

    cards = []
    for cc, c in tips.items():
        if cc == '_meta' or not isinstance(c, dict):
            continue
        # metas[]
        for i, m in enumerate(c.get('metas') or []):
            url = (m.get('images') or [None])[0]
            if not url:
                continue
            local = (REPO / 'extension' / url) if url.startswith('assets/') \
                    else cache_path_for(url)
            if not local.exists():
                continue
            k = f'country:{cc}:{i}'
            cards.append({
                'key': k, 'cc': cc,
                'type': m.get('type') or '',
                'title': (m.get('title') or '')[:80],
                'desc':  (m.get('description') or '')[:140],
                'path':  str(local),
                'is_blacklisted': k in bl,
                'blacklist_reason': bl.get(k, {}).get('reason', '') if k in bl else '',
            })
        # regions[]
        for region, entries in (c.get('regions') or {}).items():
            for j, e in enumerate(entries or []):
                url = (e.get('images') or [None])[0]
                if not url:
                    continue
                local = (REPO / 'extension' / url) if url.startswith('assets/') \
                        else cache_path_for(url)
                if not local.exists():
                    continue
                k = f'country:{cc}:region:{region}:{j}'
                cards.append({
                    'key': k, 'cc': cc,
                    'type': e.get('type') or '',
                    'title': (e.get('title') or '')[:80],
                    'desc':  (e.get('text') or e.get('description') or '')[:140],
                    'path':  str(local),
                    'is_blacklisted': k in bl,
                    'blacklist_reason': bl.get(k, {}).get('reason', '') if k in bl else '',
                })

    print(f'cards needing mask audit: {len(cards)}')
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUT_DIR.glob('*.json'):
        f.unlink()
    n_batches = (len(cards) + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(n_batches):
        chunk = cards[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
        (OUT_DIR / f'batch_{b:03d}.json').write_text(
            json.dumps(chunk, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {n_batches} batches to {OUT_DIR}')


if __name__ == '__main__':
    main()
