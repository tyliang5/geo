# -*- coding: utf-8 -*-
"""Build batches for the per-card description-leakage audit.

For every quizzable card, an agent reads the description and identifies
phrases that would tell a player the answer (country/region/town names,
language identifiers, "this is unique to X" sentences). The runtime
replaces those phrases with `___` until the user reveals the answer.

Output: $TEMP/plonkit_redaction_audit/batch_NNN.json — list of
{key, cc, title, type, description, region}.

Description-only audit (no images), so we batch big — ~400 per agent.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
OUT_DIR = Path.home() / 'AppData/Local/Temp/plonkit_redaction_audit'

BATCH_SIZE = 400


def main():
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    cards = []
    for cc, c in tips.items():
        if cc == '_meta' or not isinstance(c, dict):
            continue
        country_name = c.get('name') or cc
        for i, m in enumerate(c.get('metas') or []):
            desc = (m.get('description') or '').strip()
            if not desc:
                continue
            cards.append({
                'key': f'country:{cc}:{i}',
                'cc': cc,
                'country': country_name,
                'region': '',
                'type': m.get('type') or '',
                'title': m.get('title') or '',
                'description': desc,
            })
        for region, entries in (c.get('regions') or {}).items():
            for j, e in enumerate(entries or []):
                desc = (e.get('text') or e.get('description') or '').strip()
                if not desc:
                    continue
                cards.append({
                    'key': f'country:{cc}:region:{region}:{j}',
                    'cc': cc,
                    'country': country_name,
                    'region': region,
                    'type': e.get('type') or '',
                    'title': e.get('title') or '',
                    'description': desc,
                })

    print(f'cards needing redaction audit: {len(cards)}')
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
