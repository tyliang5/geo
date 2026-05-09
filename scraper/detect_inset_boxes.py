# -*- coding: utf-8 -*-
"""For every meta image that has a learnablemeta-style country-shape inset,
detect the inset's bounding box and store it per-card so the quiz overlay
can place the "inset hidden" mask exactly over it.

The inset has these reliable signatures:
  1. Solid light-gray / white background — pixels with a high R,G,B value
     and very low color variance.
  2. Tucked in a corner (so the bbox of bright pixels is offset from one
     corner, not centered).
  3. Occupies somewhere between 4% and 40% of the image area.

The output `mask_boxes.json` is keyed by cardKey (`country:CC:i` or
`country:CC:region:Name:i` for sub-region cards) and stores `{x, y, w, h}` as
fractions of the rendered image, ready for the overlay layer.

Run:
    pip install pillow pillow-avif-plugin numpy
    python scraper/detect_inset_boxes.py [--limit N]
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from PIL import Image
try:
    import pillow_avif  # noqa: F401  (registers AVIF plugin)
except ImportError:
    pass

import scipy.ndimage as ndi

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
OUT = REPO / 'extension' / 'data' / 'mask_boxes.json'
CACHE = REPO / 'scraper' / '.image_cache'

# Detection: we look for "map-ish" pixels — low saturation (gray-ish, since
# learnablemeta insets render countries as gray fills on white backgrounds)
# and medium-high brightness (the inset background isn't a dark photo).
# Then we find the largest contiguous region of map-ish pixels and use its
# bounding box as the mask area.
SAT_MAX = 20            # low saturation = grayscale graphic (insets use cream/gray bg)
BRIGHT_MIN = 200        # mean of (R,G,B) ≥ this
MIN_FRAC_AREA = 0.04    # smallest plausible inset = 4% of image
MAX_FRAC_AREA = 0.95    # tolerate fully-map images (sandyroads.png etc.)


def cache_path_for(url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    ext = Path(urlparse(url).path).suffix.lower() or '.bin'
    return CACHE / (h + ext)


def detect_inset(img_path: Path) -> dict | None:
    """Return {x,y,w,h} (0..1 fractions) for the inset, or None if no inset.

    Approach: build a "map-ish pixel" mask (low-sat AND bright), find every
    contiguous connected component, then pick the largest component whose
    bbox is in size range and is reasonably solid (most of its bbox is map-
    ish, not just a sparse halo).
    """
    try:
        im = Image.open(img_path).convert('RGB')
    except Exception:
        return None
    W, H = im.size
    if W < 100 or H < 100:
        return None
    # Downsample for speed
    target_w = 320
    if W > target_w:
        scale = target_w / W
        im = im.resize((target_w, int(H * scale)))
    arr = np.asarray(im).astype(np.int16)
    h, w, _ = arr.shape
    sat = arr.max(axis=2) - arr.min(axis=2)
    bright = arr.mean(axis=2)
    mapish = (sat <= SAT_MAX) & (bright >= BRIGHT_MIN)
    n_pixels = h * w
    if mapish.sum() < n_pixels * MIN_FRAC_AREA:
        return None
    # Closing fills in the country-fill gaps inside the inset, so the inset
    # becomes a single solid blob rather than a halo with holes.
    structure = np.ones((5, 5), dtype=bool)
    closed = ndi.binary_closing(mapish, structure=structure, iterations=2)
    # Connected components
    labels, n = ndi.label(closed)
    if n == 0:
        return None
    # For sharp-edge discrimination: compute per-pixel gradient magnitude
    # using sobel on the brightness channel. Insets have a hard rectangular
    # boundary against the photo underneath, photos have soft gradients.
    bright_f = bright.astype(np.float32)
    gx = ndi.sobel(bright_f, axis=1)
    gy = ndi.sobel(bright_f, axis=0)
    grad_mag = np.hypot(gx, gy)
    candidates = []
    for label_id in range(1, n + 1):
        ys, xs = np.where(labels == label_id)
        if len(ys) < n_pixels * MIN_FRAC_AREA:
            continue
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        bw, bh = (x1 - x0 + 1), (y1 - y0 + 1)
        area_frac = (bw * bh) / n_pixels
        if area_frac > MAX_FRAC_AREA:
            continue
        density = float(closed[y0:y1+1, x0:x1+1].mean())
        if density < 0.40:
            continue
        # Sharp-edge check: examine the four interior bbox edges (a thin
        # strip just inside each edge) and compute the mean gradient. A
        # graphical overlay has sharp boundaries → high gradient. A bright
        # photo region (sky, clouds) blends smoothly → low gradient.
        edge_strip = 2
        edges = []
        if y0 > 0:                   edges.append(grad_mag[max(0, y0-edge_strip):y0, x0:x1+1])
        if y1 < h - 1:               edges.append(grad_mag[y1+1:min(h, y1+1+edge_strip), x0:x1+1])
        if x0 > 0:                   edges.append(grad_mag[y0:y1+1, max(0, x0-edge_strip):x0])
        if x1 < w - 1:               edges.append(grad_mag[y0:y1+1, x1+1:min(w, x1+1+edge_strip)])
        edge_pixels = np.concatenate([e.ravel() for e in edges]) if edges else np.array([0.0])
        edge_max = float(edge_pixels.max()) if edge_pixels.size else 0
        # Rectangularity: how much of the bbox is map-ish (vs how much is the
        # photo bleeding through). Insets are highly rectangular (fill > 0.7),
        # sky blobs are organic-shaped.
        fill_ratio = len(ys) / float(bw * bh)
        candidates.append({
            'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
            'bw': bw, 'bh': bh,
            'area': area_frac, 'density': density,
            'fill': fill_ratio,
            'edge_max': edge_max,
            'pixels': len(ys),
        })
    if not candidates:
        return None
    # Sharp-edge gate: real insets have at least one borderline pixel with
    # gradient magnitude > 100 (out of ~360 max). Photos rarely cross this.
    # Also require fill_ratio > 0.55 — the inset must be roughly rectangular,
    # not a curving blob.
    candidates = [c for c in candidates if c['edge_max'] >= 80 and c['fill'] >= 0.55]
    if not candidates:
        return None
    # Pick the largest passing candidate.
    best = max(candidates, key=lambda c: c['pixels'])
    # Pick a corner anchor based on bbox position
    x0, y0, x1, y1 = best['x0'], best['y0'], best['x1'], best['y1']
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    anchor = ('t' if cy < h / 2 else 'b') + ('l' if cx < w / 2 else 'r')
    # Pad by 1.5% so the mask sits comfortably outside the inset's edge
    pad = 0.015
    fx, fy = x0 / w, y0 / h
    fw, fh = best['bw'] / w, best['bh'] / h
    x = max(0.0, fx - pad)
    y = max(0.0, fy - pad)
    fw = min(1.0 - x, fw + 2 * pad)
    fh = min(1.0 - y, fh + 2 * pad)
    return {'x': round(x, 4), 'y': round(y, 4),
            'w': round(fw, 4), 'h': round(fh, 4),
            'anchor': anchor}


def collect_cards():
    """Yield (cardKey, image_url) for every quizzable card in tips.json."""
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    for cc, c in tips.items():
        if cc == '_meta' or not isinstance(c, dict):
            continue
        # metas[]
        for i, m in enumerate(c.get('metas') or []):
            url = (m.get('images') or [None])[0]
            if url:
                yield (f'country:{cc}:{i}', url)
        # regions{}
        for region_name, entries in (c.get('regions') or {}).items():
            for j, e in enumerate(entries or []):
                url = (e.get('images') or [None])[0]
                if url:
                    yield (f'country:{cc}:region:{region_name}:{j}', url)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--no-cache-only', action='store_true',
                    help='Also process URLs whose images are not in cache (slow)')
    args = ap.parse_args()

    cards = list(collect_cards())
    print(f'collecting bbox for {len(cards)} cards...')
    if args.limit:
        cards = cards[:args.limit]
        print(f'  (limited to {len(cards)})')

    out: dict[str, dict] = {}
    n_hit = n_miss = n_skip = 0
    for idx, (key, url) in enumerate(cards, 1):
        if idx % 100 == 0:
            print(f'  [{idx}/{len(cards)}] hits={n_hit}  no-inset={n_miss}  skipped={n_skip}')
        # Local image (assets/img/...) — load directly from extension dir
        if url.startswith('assets/'):
            p = REPO / 'extension' / url
        else:
            p = cache_path_for(url)
            if not p.exists():
                n_skip += 1
                continue
        if not p.exists():
            n_skip += 1
            continue
        box = detect_inset(p)
        if box:
            out[key] = box
            n_hit += 1
        else:
            n_miss += 1

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\ndetected insets in {n_hit}/{len(cards)} cards ({n_miss} no-inset, {n_skip} skipped)')
    print(f'wrote {OUT.relative_to(REPO)}')


if __name__ == '__main__':
    main()
