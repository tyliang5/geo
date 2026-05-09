"""Restore at least one country-level meta for any country that the regional
reorganize emptied. Keeps the regional version in regions{} too — we just
ensure every previously-quizzable country stays quizzable.
"""
import json
from pathlib import Path

TIPS = Path(r'C:/Users/tylia/Github/geo/extension/data/tips.json')
BAK = Path(r'C:/Users/tylia/Github/geo/extension/data/tips.json.bak')

tips = json.loads(TIPS.read_text(encoding='utf-8'))
bak = json.loads(BAK.read_text(encoding='utf-8'))

restored = 0
for cc, c in tips.items():
    if cc == '_meta':
        continue
    if (c.get('metas') or []):
        continue  # still has country-level cards
    bak_metas = (bak.get(cc) or {}).get('metas') or []
    # Pick the first meta with an image — any country-level identifier is
    # better than nothing.
    for m in bak_metas:
        if (m.get('images') or [None])[0]:
            c['metas'] = [m]
            restored += 1
            break

TIPS.write_text(json.dumps(tips, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'restored at least one country-level meta for {restored} countries')
