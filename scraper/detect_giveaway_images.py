# -*- coding: utf-8 -*-
"""Scan every meta image referenced in tips.json for "the answer is in the
image" giveaways, using OCR. Outputs extension/data/giveaway_blacklist.json
listing the cardKeys that should be hidden by default in the country-ID quiz.

Detects:
  - Country names baked into the image as text (e.g., the "ESTONIA"
    watermark on a bollard photo).
  - Country adjective forms ("Brazilian", "Russian", "Egyptian", etc.).
  - Common region-inset map labels.

Does NOT detect (corner mask handles these):
  - Country-shape inset maps with no text.

Run:
    pip install easyocr requests pillow
    python scraper/detect_giveaway_images.py [--limit N] [--verbose]

The download cache lives in scraper/.image_cache/ so re-runs are cheap.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
# AVIF support for Pillow — most learnablemeta images are .avif.
try:
    import pillow_avif  # noqa: F401  (registers the AVIF plugin via side effect)
except ImportError:
    pass

REPO = Path(__file__).resolve().parents[1]
TIPS = REPO / 'extension' / 'data' / 'tips.json'
REF = REPO / 'extension' / 'data' / 'country_reference.json'
OUT = REPO / 'extension' / 'data' / 'giveaway_blacklist.json'
CACHE = REPO / 'scraper' / '.image_cache'

# Adjective derivations off the country name (rough — covers most cases)
ADJ_SUFFIXES = ['n', 'ian', 'ese', 'i', 'ish', 'ic', 'an']


def name_variants(name: str) -> set[str]:
    """Yield uppercase forms of the country name + plausible adjective forms."""
    out = set()
    # Always emit the un-cleaned full name uppercase too — handles cases like
    # "United States of America" where stripping "United" leaves only "States",
    # which doesn't match the literal "UNITED STATES" text often baked into
    # USA-shape reference maps.
    full = name.strip()
    if full:
        out.add(full.upper())
        # First two words for compound country names ("United States",
        # "Saudi Arabia", "South Africa", "New Zealand")
        words = full.split()
        if len(words) >= 2:
            out.add(' '.join(words[:2]).upper())
    cleaned = re.sub(r'^(the|republic of|kingdom of|democratic republic of|democratic people\'s republic of|people\'s republic of|federal republic of|united)\s+', '', name, flags=re.I)
    cleaned = re.sub(r'\s+(islands?|republic|federation|kingdom|states)$', '', cleaned, flags=re.I).strip()
    if not cleaned:
        return out
    out.add(cleaned.upper())
    out.add(cleaned.lower())
    # Take just the first word for adjective derivation (e.g. "Brazil" from "Brazil")
    head = cleaned.split()[0]
    if len(head) >= 3:
        out.add(head.upper())
        out.add(head.lower())
        for s in ADJ_SUFFIXES:
            out.add((head + s).upper())
            out.add((head + s).lower())
    return out


def cache_path_for(url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()[:16]
    ext = Path(urlparse(url).path).suffix.lower() or '.bin'
    return CACHE / (h + ext)


def fetch_image(url: str) -> Path | None:
    p = cache_path_for(url)
    if p.exists():
        return p
    try:
        r = requests.get(url, timeout=20, headers={'User-Agent': 'plonker-detect/1.0'})
        if not r.ok:
            return None
        CACHE.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
        return p
    except Exception as e:
        print(f'  fetch failed: {url}: {e}', file=sys.stderr)
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0,
                    help='Process only first N image URLs (for quick testing).')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    print('loading tips + reference...')
    tips = json.loads(TIPS.read_text(encoding='utf-8'))
    reference = json.loads(REF.read_text(encoding='utf-8'))

    # Pre-compute the variant set for each country
    country_variants: dict[str, set[str]] = {}
    for cc, c in tips.items():
        if cc == '_meta':
            continue
        name = c.get('name')
        if not name:
            continue
        variants = name_variants(name)
        # Also add ISO 3-letter (uppercase) since some images stamp e.g. "USA" on top
        iso3 = (reference.get(cc) or {}).get('iso3')
        if iso3:
            variants.add(iso3.upper())
        country_variants[cc] = variants

    # Collect every image with its (cardKey, cc, country_variants)
    work: list[tuple[str, str, str]] = []  # (cardKey, cc, image_url)
    seen_urls = set()
    for cc, c in tips.items():
        if cc == '_meta' or not c.get('metas'):
            continue
        for i, m in enumerate(c['metas']):
            url = (m.get('images') or [None])[0]
            if not url or url in seen_urls:
                continue
            cardKey = f'country:{cc}:{i}'
            work.append((cardKey, cc, url))
            seen_urls.add(url)
    print(f'  {len(work)} unique image cards to scan')
    if args.limit:
        work = work[:args.limit]
        print(f'  limited to first {args.limit}')

    print('initialising easyocr...')
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)

    blacklist: dict[str, dict] = {}
    n_ok = n_giveaway = n_failed = 0

    for idx, (cardKey, cc, url) in enumerate(work, 1):
        if idx % 25 == 0 or args.verbose:
            print(f'  [{idx}/{len(work)}] {cc}  giveaways so far: {n_giveaway}')
        img_path = fetch_image(url)
        if not img_path:
            n_failed += 1
            continue
        try:
            result = reader.readtext(str(img_path), detail=0, paragraph=False)
        except Exception as e:
            n_failed += 1
            if args.verbose:
                print(f'    OCR failed: {e}')
            continue
        if not result:
            n_ok += 1
            continue
        text_concat = ' '.join(result).upper()
        # 1) Country name appears in the image (e.g. "ESTONIA" watermark).
        wanted = country_variants.get(cc, set())
        hit_self = any(v.upper() in text_concat for v in wanted if len(v) >= 3)
        # 2) Educational comparison labels — "Northern"/"Southern" type tags
        #    typically only show up on side-by-side compare images that include
        #    a country outline as overlay.
        DIRECTIONAL = {'NORTHERN', 'SOUTHERN', 'EASTERN', 'WESTERN', 'CENTRAL', 'NORTHEAST', 'NORTHWEST', 'SOUTHEAST', 'SOUTHWEST'}
        directional_hits = [w for w in DIRECTIONAL if w in text_concat]
        # 3) Generic infographic markers: "vs", "compared to", "type 1/2", etc.
        INFOGRAPHIC_MARKERS = {' VS ', ' VS. ', 'COMPARED', 'TYPE 1', 'TYPE 2', 'TYPE A', 'TYPE B', 'STYLE 1', 'OPTION 1'}
        infographic_hits = [m for m in INFOGRAPHIC_MARKERS if m in f' {text_concat} ']
        if hit_self:
            n_giveaway += 1
            blacklist[cardKey] = {
                'cc': cc,
                'reason': 'country_name_in_image',
                'detected_text': ' / '.join(result)[:200],
            }
            if args.verbose:
                print(f'    GIVEAWAY (country-name) {cardKey}: "{text_concat[:80]}"')
        elif len(directional_hits) >= 2 or infographic_hits:
            # 2+ directional words OR an infographic marker = comparison image
            n_giveaway += 1
            reason = 'directional_labels' if len(directional_hits) >= 2 else 'infographic_markers'
            blacklist[cardKey] = {
                'cc': cc,
                'reason': reason,
                'detected_text': ' / '.join(result)[:200],
            }
            if args.verbose:
                print(f'    GIVEAWAY ({reason}) {cardKey}: "{text_concat[:80]}"')
        else:
            n_ok += 1

    OUT.write_text(json.dumps(blacklist, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'\ndone: {n_ok} clean, {n_giveaway} giveaways blacklisted, {n_failed} failed')
    print(f'wrote {OUT.relative_to(REPO)}')


if __name__ == '__main__':
    main()
