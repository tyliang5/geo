# -*- coding: utf-8 -*-
"""Aggregate per-batch mask verdicts into one extension/data/card_masks.json.

Reads $TEMP/plonkit_mask_audit/masks_NNN.json (one per batch agent),
merges every entry, and writes a flat dict { cardKey: { boxes: [...] } } that
the runtime can read.

Also un-blacklists cards whose only blacklist reason is one we can now mask
precisely (country_name_in_image / country_outline_overlay / inset_locator_map
etc.) so those metas come back into rotation with the giveaway covered.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'extension' / 'data' / 'card_masks.json'
BL_PATH = REPO / 'extension' / 'data' / 'giveaway_blacklist.json'
SRC = Path.home() / 'AppData/Local/Temp/plonkit_mask_audit'

# Reasons in the blacklist that we now consider "fixable by masking".
# If a blacklisted card has a precomputed mask AND its only reason is one of
# these, we drop it from the blacklist so it shows up again with the mask.
MASKABLE_REASONS = {
    'country_name_in_image',
    'country_outline_overlay',
    'inset_locator_map',
    'plonkit_watermark',
    'region_label_overlay',
}


def load_verdicts():
    """Return list of (cardKey, boxes) tuples from every masks_NNN.json.

    Agents wrote two shapes:
      A) list of {key, path, boxes}
      B) dict { cardKey: {boxes: [...]} }
    Normalise to a stream of (key, boxes).
    """
    out = []
    for f in sorted(SRC.glob('masks_*.json')):
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
        except Exception as e:
            print(f'SKIP {f.name}: {e}')
            continue
        if isinstance(data, dict):
            iterable = ((k, v) for k, v in data.items())
        elif isinstance(data, list):
            iterable = ((e.get('key'), e) for e in data if isinstance(e, dict))
        else:
            print(f'SKIP {f.name}: unsupported root type {type(data).__name__}')
            continue
        for k, entry in iterable:
            if not k or not isinstance(entry, dict):
                continue
            boxes = entry.get('boxes') or []
            if not boxes:
                continue
            # filter junk: each box must have x/y/w/h numeric and in [0,1]
            clean = []
            for b in boxes:
                try:
                    x = float(b['x']); y = float(b['y'])
                    w = float(b['w']); h = float(b['h'])
                except (KeyError, TypeError, ValueError):
                    continue
                if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    continue
                if x + w > 1.001 or y + h > 1.001:
                    continue
                # Pad each side by 3% (clamped to [0,1]) so under-estimated
                # boxes don't leave a sliver of the giveaway peeking out.
                pad = 0.03
                x2 = max(0.0, x - pad)
                y2 = max(0.0, y - pad)
                w2 = min(1.0 - x2, w + 2 * pad)
                h2 = min(1.0 - y2, h + 2 * pad)
                # Plonkit "country shape inset" boxes glued to the right edge
                # systematically span the full height of the image — agents
                # often clipped them to where the red highlight ends but
                # missed the country outline above it. Extend any
                # right-anchored inset to the top of the image.
                reason = str(b.get('reason') or '').lower()
                right_anchored = (x2 + w2) >= 0.95
                is_inset = ('inset' in reason or 'silhouette' in reason
                            or 'country shape' in reason or 'locator' in reason
                            or 'country-shape' in reason or 'country_shape' in reason)
                if right_anchored and is_inset and y2 > 0.05:
                    h2 = min(1.0, h2 + y2)
                    y2 = 0.0
                clean.append({
                    'x': round(x2, 4), 'y': round(y2, 4),
                    'w': round(w2, 4), 'h': round(h2, 4),
                    'reason': str(b.get('reason') or '')[:80],
                })
            if clean:
                out.append((k, clean))
    return out


def main():
    verdicts = load_verdicts()
    print(f'verdicts collected: {len(verdicts)}')
    masks = {}
    for k, boxes in verdicts:
        # If the same key was audited twice (shouldn't happen) keep the
        # version with more boxes.
        if k in masks and len(masks[k]['boxes']) >= len(boxes):
            continue
        masks[k] = {'boxes': boxes}
    OUT.write_text(json.dumps(masks, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {len(masks)} card masks to {OUT}')

    # Un-blacklist cards whose only reason is now mask-fixable AND whose mask
    # is small enough to leave the rest of the image playable. A full-image
    # mask (~ {0,0,1,1}) is the same as hiding the whole card, so don't
    # un-blacklist those.
    def is_partial_mask(boxes):
        for b in boxes:
            if b['w'] >= 0.95 and b['h'] >= 0.95:
                return False
        return True

    bl = json.loads(BL_PATH.read_text(encoding='utf-8'))
    removed = 0
    for k in list(bl.keys()):
        entry = bl[k]
        reason = (entry.get('reason') or '').strip() if isinstance(entry, dict) else ''
        if k in masks and reason in MASKABLE_REASONS and is_partial_mask(masks[k]['boxes']):
            del bl[k]
            removed += 1
    BL_PATH.write_text(json.dumps(bl, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'un-blacklisted {removed} cards (now masked instead of hidden)')


if __name__ == '__main__':
    main()
