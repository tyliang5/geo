# -*- coding: utf-8 -*-
"""Aggregate mnemonics_NNN.json into one card_mnemonics.json.

Output: { cardKey: "1-line mnemonic" }
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'extension' / 'data' / 'card_mnemonics.json'
SRC = Path.home() / 'AppData/Local/Temp/plonkit_mnemonic_audit'


def main():
    merged = {}
    for f in sorted(SRC.glob('mnemonics_*.json')):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'SKIP {f.name}: {e}')
            continue
        if not isinstance(data, dict):
            print(f'SKIP {f.name}: not a dict')
            continue
        for k, v in data.items():
            s = (v or '').strip() if isinstance(v, str) else ''
            if not s:
                continue
            # If the same card appears in two batches (shouldn't happen),
            # prefer the shorter one — easier to memorise.
            if k in merged and len(merged[k]) <= len(s):
                continue
            merged[k] = s

    OUT.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {len(merged)} mnemonics to {OUT}')


if __name__ == '__main__':
    main()
