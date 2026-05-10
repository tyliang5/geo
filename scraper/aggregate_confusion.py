# -*- coding: utf-8 -*-
"""Aggregate confusion_NNN.json into one confusion_drills.json.

Output schema:
  {
    "drills": [
      { "id": "<slug>", "label": "Red-and-white striped concrete bollards",
        "category": "bollard",
        "cards": ["country:CR:5", "country:ID:2", ...] }
    ]
  }

Each drill becomes a topic at runtime: pick a random card from the cluster
and ask "which country?" — the lookalikes from other countries are the
multiple-choice distractors.
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'extension' / 'data' / 'confusion_drills.json'
SRC = Path.home() / 'AppData/Local/Temp/plonkit_confusion_audit'


def slug(s: str) -> str:
    s = re.sub(r'[^a-z0-9]+', '_', s.lower()).strip('_')
    return s[:48] or 'drill'


def main():
    drills = []
    seen_slugs = set()
    for f in sorted(SRC.glob('confusion_*.json')):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'SKIP {f.name}: {e}')
            continue
        category = data.get('category') or ''
        for cluster in data.get('clusters') or []:
            label = (cluster.get('label') or '').strip()
            cards = cluster.get('cards') or []
            if not label or len(cards) < 2:
                continue
            # Confusion only matters if the cluster spans >=2 countries
            ccs = set()
            for k in cards:
                m = re.match(r'country:([A-Z]+)', k)
                if m:
                    ccs.add(m.group(1))
            if len(ccs) < 2:
                continue
            sid = f'{slug(category)}__{slug(label)}'
            if sid in seen_slugs:
                sid = f'{sid}_{len(seen_slugs)}'
            seen_slugs.add(sid)
            drills.append({
                'id': sid,
                'label': label,
                'category': category,
                'cards': cards,
            })

    drills.sort(key=lambda d: -len(d['cards']))
    OUT.write_text(json.dumps({'drills': drills}, indent=2, ensure_ascii=False),
                   encoding='utf-8')
    print(f'wrote {len(drills)} confusion drills to {OUT}')
    print('top 10:')
    for d in drills[:10]:
        print(f'  {len(d["cards"]):3d}  [{d["category"]}]  {d["label"]}')


if __name__ == '__main__':
    main()
