# -*- coding: utf-8 -*-
"""Build batches for per-card mnemonic extraction.

For every quizzable card, an agent reads the description (and image if
present) and produces a 1-line takeaway — the single visual feature you
should burn into memory ("yellow guardrails with diagonal black stripes
= Croatia"). Shown on answer reveal so the takeaway is what sticks, not
the prose.

Output: $TEMP/plonkit_mnemonic_audit/batch_NNN.json — list of
{key, cc, region, type, title, description, path}.

Image-aware audit, so smaller batches (~200/agent).
"""
import json
import hashlib
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
CACHE = REPO / 'scraper' / '.image_cache'
OUT_DIR = Path.home() / 'AppData/Local/Temp/plonkit_mnemonic_audit'

BATCH_SIZE = 200


def cache_path_for(url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    ext = Path(urlparse(url).path).suffix.lower() or '.bin'
    return CACHE / (h + ext)


def main():
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    cards = []
    for cc, c in tips.items():
        if cc == '_meta' or not isinstance(c, dict):
            continue
        country = c.get('name') or cc
        for i, m in enumerate(c.get('metas') or []):
            desc = (m.get('description') or '').strip()
            if not desc:
                continue
            url = (m.get('images') or [None])[0]
            local = ''
            if url:
                lp = (REPO / 'extension' / url) if url.startswith('assets/') \
                     else cache_path_for(url)
                if lp.exists():
                    local = str(lp)
            cards.append({
                'key': f'country:{cc}:{i}',
                'cc': cc,
                'country': country,
                'region': '',
                'type': m.get('type') or '',
                'title': m.get('title') or '',
                'description': desc,
                'path': local,
            })
        for region, entries in (c.get('regions') or {}).items():
            for j, e in enumerate(entries or []):
                desc = (e.get('text') or e.get('description') or '').strip()
                if not desc:
                    continue
                url = (e.get('images') or [None])[0]
                local = ''
                if url:
                    lp = (REPO / 'extension' / url) if url.startswith('assets/') \
                         else cache_path_for(url)
                    if lp.exists():
                        local = str(lp)
                cards.append({
                    'key': f'country:{cc}:region:{region}:{j}',
                    'cc': cc,
                    'country': country,
                    'region': region,
                    'type': e.get('type') or '',
                    'title': e.get('title') or '',
                    'description': desc,
                    'path': local,
                })

    print(f'cards needing mnemonic: {len(cards)}')
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUT_DIR.glob('*.json'):
        f.unlink()
    n = (len(cards) + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(n):
        chunk = cards[b * BATCH_SIZE:(b + 1) * BATCH_SIZE]
        (OUT_DIR / f'batch_{b:03d}.json').write_text(
            json.dumps(chunk, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {n} batches to {OUT_DIR}')


if __name__ == '__main__':
    main()
