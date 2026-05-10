# -*- coding: utf-8 -*-
"""Aggregate redactions_NNN.json verdicts into one card_redactions.json.

Output schema:
  { cardKey: [{phrase, reason}, ...] }

Phrases are deduplicated within a card and sorted longest-first so the
runtime can do greedy non-overlapping replacement.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'extension' / 'data' / 'card_redactions.json'
SRC = Path.home() / 'AppData/Local/Temp/plonkit_redaction_audit'


def main():
    merged = {}
    for f in sorted(SRC.glob('redactions_*.json')):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'SKIP {f.name}: {e}')
            continue
        if not isinstance(data, dict):
            print(f'SKIP {f.name}: not a dict')
            continue
        for k, lst in data.items():
            if not isinstance(lst, list):
                continue
            seen = set()
            cleaned = []
            for it in lst:
                if not isinstance(it, dict):
                    continue
                p = (it.get('phrase') or '').strip()
                if not p or p.lower() in seen:
                    continue
                seen.add(p.lower())
                cleaned.append({
                    'phrase': p,
                    'reason': str(it.get('reason') or '')[:60],
                })
            if not cleaned:
                continue
            cleaned.sort(key=lambda x: -len(x['phrase']))
            merged[k] = cleaned

    OUT.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding='utf-8')
    total_phrases = sum(len(v) for v in merged.values())
    print(f'wrote {len(merged)} cards / {total_phrases} phrases to {OUT}')


if __name__ == '__main__':
    main()
