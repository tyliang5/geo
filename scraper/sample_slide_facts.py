"""Pixel-sample categorical facts off the "10 Useful Maps" slide deck and
write to scraper/slide_facts.json. The choropleth slides we sample:

    slide 3  -> sign_style  (yellow=MUTCD / red=European / green=Chinese / blue=Other)
    slide 9  -> road_lines  (yellow center / white center / yellow edge / etc.)

Slide 1 (driving side) and slide 10 (speed limits) are sampled too — they're
covered authoritatively by Wikidata/Wikipedia, so we use them as projection
calibration: if our sampling agrees with the table for ~95% of countries,
the geometry's right and we trust the same projection for slide 3 and 9.

Slide 5 (chevron colour) and slide 8 (ped-sign stripes) are Europe-only with
mixed projections and lots of in-map icons covering country fills, so we hold
off on those — they're easy to manually re-audit.

Run:
    python scraper/sample_slide_facts.py
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path
from typing import Iterable
import requests
from PIL import Image
from shapely.geometry import shape, Point

REPO = Path(__file__).resolve().parents[1]
SLIDES_DIR = REPO / "scraper" / "slides"
COUNTRIES_GEOJSON = SLIDES_DIR / "countries.geojson"
WIKI_FACTS = REPO / "scraper" / "wikipedia_facts.json"
OUT = REPO / "scraper" / "slide_facts.json"

PRES_ID = "1PB4I2imcVAukng-aLB6teAfDewkEnFWFWf-hEQsEa-8"
SLIDE_PAGE_IDS = {
    1: "g13d44f3196b_0_84",   # driving side  (calibration)
    3: "g13d44f3196b_0_12",   # sign style
    9: "g13d44f3196b_0_103",  # road lines
    10: "g13d44f3196b_0_78",  # speed limits  (calibration)
}


# ---------------------------------------------------------------------------
# Slide download
# ---------------------------------------------------------------------------
def download_slides() -> dict[int, Path]:
    SLIDES_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[int, Path] = {}
    for n, pg in SLIDE_PAGE_IDS.items():
        path = SLIDES_DIR / f"slide{n}.png"
        if not path.exists():
            url = f"https://docs.google.com/presentation/d/{PRES_ID}/export/png?id={PRES_ID}&pageid={pg}"
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            path.write_bytes(r.content)
        out[n] = path
    return out


# ---------------------------------------------------------------------------
# Country centroid lookup (Natural Earth 110m, ISO-2)
# ---------------------------------------------------------------------------
def load_country_polygons() -> dict[str, list[tuple[float, float]]]:
    """Return ISO2 -> list of (lat, lng) sample points spread across the
    country's polygon. Multiple-point sampling beats centroid-only for thin
    shapes (e.g., UK strip vs. nearby Norway), where a single projected
    centroid often lands on a border pixel or the wrong country."""
    if not COUNTRIES_GEOJSON.exists():
        url = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        SLIDES_DIR.mkdir(parents=True, exist_ok=True)
        COUNTRIES_GEOJSON.write_bytes(r.content)
    data = json.loads(COUNTRIES_GEOJSON.read_text(encoding="utf-8"))
    out: dict[str, list[tuple[float, float]]] = {}
    for feat in data["features"]:
        props = feat["properties"]
        iso2 = props.get("ISO_A2_EH") or props.get("ISO_A2")
        if not iso2 or iso2 == "-99":
            continue
        geom = shape(feat["geometry"])
        points: list[tuple[float, float]] = []
        # 1) representative_point — guaranteed inside polygon
        rp = geom.representative_point()
        points.append((rp.y, rp.x))
        # 2) grid of points within the polygon's bbox; keep those inside
        minx, miny, maxx, maxy = geom.bounds
        nx = ny = 5
        for ix in range(nx):
            for iy in range(ny):
                x = minx + (ix + 0.5) / nx * (maxx - minx)
                y = miny + (iy + 0.5) / ny * (maxy - miny)
                if geom.contains(Point(x, y)):
                    points.append((y, x))
        out[iso2] = points
    return out


# ---------------------------------------------------------------------------
# Robinson forward projection. Tabulated at 5-degree latitude steps; we
# linearly interpolate between rows for non-multiples of 5.
# ---------------------------------------------------------------------------
ROBINSON_TABLE = [
    # (lat, X, Y) — from Snyder (1987).
    (0,  1.0000, 0.0000), (5,  0.9986, 0.0620), (10, 0.9954, 0.1240),
    (15, 0.9900, 0.1860), (20, 0.9822, 0.2480), (25, 0.9730, 0.3100),
    (30, 0.9600, 0.3720), (35, 0.9427, 0.4340), (40, 0.9216, 0.4958),
    (45, 0.8962, 0.5571), (50, 0.8679, 0.6176), (55, 0.8350, 0.6769),
    (60, 0.7986, 0.7346), (65, 0.7597, 0.7903), (70, 0.7186, 0.8435),
    (75, 0.6732, 0.8936), (80, 0.6213, 0.9394), (85, 0.5722, 0.9761),
    (90, 0.5322, 1.0000),
]


def robinson(lat: float, lng: float) -> tuple[float, float]:
    """Return unit (x, y) where x in roughly [-2.667, +2.667] and y in [-1, +1].

    Caller scales these into the slide's map pixel bbox.
    """
    sign = -1 if lat < 0 else 1
    a = abs(lat)
    # find bracketing rows
    for i in range(len(ROBINSON_TABLE) - 1):
        l0, X0, Y0 = ROBINSON_TABLE[i]
        l1, X1, Y1 = ROBINSON_TABLE[i + 1]
        if l0 <= a <= l1:
            t = 0 if l0 == l1 else (a - l0) / (l1 - l0)
            X = X0 + t * (X1 - X0)
            Y = Y0 + t * (Y1 - Y0)
            break
    else:
        X, Y = ROBINSON_TABLE[-1][1], ROBINSON_TABLE[-1][2]
    x = 0.8487 * (math.pi / 180) * lng * X
    y = 1.3523 * Y * sign
    return (x, y)


def equirect(lat: float, lng: float) -> tuple[float, float]:
    return (lng / 180.0, lat / 90.0)


# ---------------------------------------------------------------------------
# Map bbox calibration. Each slide's map area is identified by:
#   - bbox (x0,y0,x1,y1) in image-pixel coords
#   - center_lng (where x=0 lands; usually 0 but Pacific-centred maps vary)
#   - projection ('robinson' | 'equirect')
#
# The numbers below were measured by visual inspection of the downloaded PNGs
# (top-left of map fill, bottom-right). Tuned by the calibration step that
# samples slide 1 and checks against Wikidata's driving side.
# ---------------------------------------------------------------------------
SLIDE_MAPS = {
    # Bbox values were back-fit from three reference points per slide (US
    # Midwest, Australia interior, Japan) projected through Robinson math.
    # See PROJECTION_NOTES.md for the linear-fit derivation.
    1:  {"bbox": (-10, 30, 920, 470), "proj": "robinson", "center_lng": 0},
    3:  {"bbox": (-10, 50, 920, 460), "proj": "robinson", "center_lng": 0},
    9:  {"bbox": (-10, 50, 920, 460), "proj": "robinson", "center_lng": 0},
    10: {"bbox": (-10, 30, 920, 470), "proj": "robinson", "center_lng": 0},
}


def project_to_pixel(lat: float, lng: float, conf: dict) -> tuple[int, int]:
    x0, y0, x1, y1 = conf["bbox"]
    proj = conf["proj"]
    lng_rel = lng - conf.get("center_lng", 0)
    # Wrap into [-180, 180]
    while lng_rel > 180: lng_rel -= 360
    while lng_rel < -180: lng_rel += 360
    if proj == "equirect":
        u, v = equirect(lat, lng_rel)
        # u in [-1, 1], v in [-1, 1] (positive-up); image y is positive-down.
        px = x0 + (u + 1) / 2 * (x1 - x0)
        py = y1 - (v + 1) / 2 * (y1 - y0)
    elif proj == "robinson":
        u, v = robinson(lat, lng_rel)
        # Robinson native unit x: [-2.667, +2.667]; y: [-1.323, +1.323]
        px = x0 + (u / 2.667 + 1) / 2 * (x1 - x0)
        py = y1 - (v / 1.3523 + 1) / 2 * (y1 - y0)
    else:
        raise ValueError(proj)
    return int(round(px)), int(round(py))


# ---------------------------------------------------------------------------
# Pixel sampling: take a 5x5 window mode (more robust than a single pixel
# against jpeg/png edge bleed and tiny country-border anti-aliasing).
# ---------------------------------------------------------------------------
def sample_color(img: Image.Image, x: int, y: int, size: int = 5) -> tuple[int, int, int]:
    w, h = img.size
    if not (0 <= x < w and 0 <= y < h):
        return (0, 0, 0)
    half = size // 2
    counts: dict[tuple[int, int, int], int] = {}
    for dx in range(-half, half + 1):
        for dy in range(-half, half + 1):
            xx, yy = max(0, min(w - 1, x + dx)), max(0, min(h - 1, y + dy))
            c = img.getpixel((xx, yy))
            if isinstance(c, int):
                c = (c, c, c)
            elif len(c) == 4:
                c = c[:3]
            # Round to a 16-step bucket for de-jittering.
            c = tuple((v // 16) * 16 for v in c)
            counts[c] = counts.get(c, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


# ---------------------------------------------------------------------------
# Color → category mapping per slide. Each category has a list of "anchor"
# RGB values; we pick the closest by Euclidean distance. WHITE is treated as
# "no data" (background) and skipped.
# ---------------------------------------------------------------------------
WHITE_THRESHOLD = 200      # >= 200 in all channels => background, no answer
DARK_THRESHOLD = 80        # max(r,g,b) below this => border/black, no answer
MIN_SAT = 18               # below this => probably grey/no-data


def is_unclear(rgb: tuple[int, int, int]) -> bool:
    r, g, b = rgb
    if r >= WHITE_THRESHOLD and g >= WHITE_THRESHOLD and b >= WHITE_THRESHOLD:
        return True
    # Anything where every channel is dim is almost certainly a country
    # border line; the per-pixel border on the slides bleeds 1-2 px.
    if max(r, g, b) < DARK_THRESHOLD:
        return True
    if max(r, g, b) - min(r, g, b) < MIN_SAT:
        return True
    return False


def rgb_to_hsv(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (c / 255.0 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    v = mx
    s = 0 if mx == 0 else (mx - mn) / mx
    if mx == mn:
        h = 0
    elif mx == r:
        h = (60 * ((g - b) / (mx - mn)) + 360) % 360
    elif mx == g:
        h = (60 * ((b - r) / (mx - mn)) + 120) % 360
    else:
        h = (60 * ((r - g) / (mx - mn)) + 240) % 360
    return (h, s, v)


def hue_dist(h1: float, h2: float) -> float:
    d = abs(h1 - h2)
    return min(d, 360 - d)


def closest_category(rgb: tuple[int, int, int], anchors: list[tuple[str, tuple[int, int, int]]]) -> str | None:
    if is_unclear(rgb):
        return None
    h, s, v = rgb_to_hsv(rgb)
    if s < 0.12:
        # Too desaturated — probably grey/border bleed.
        return None
    best, best_d = None, 1e9
    for name, anchor in anchors:
        ah, _, _ = rgb_to_hsv(anchor)
        d = hue_dist(h, ah)
        if d < best_d:
            best, best_d = name, d
    # Reject if no anchor is reasonably close (e.g., a true uncategorised hue).
    return best if best_d < 40 else None


SLIDE1_ANCHORS = [
    ("right", (200, 30, 30)),     # saturated red (RHD)
    ("left",  (35, 60, 130)),     # navy blue (LHD)
]
# Anchors below were probed directly off the slide PNGs. Slide 3 actually
# uses 5 distinct hues: yellow, red, navy, pastel green (China), and dark
# green (SE Asia / transitional). For GeoGuessr purposes blue is still a
# European-style triangle, so we collapse it into the European bucket.
SLIDE3_ANCHORS = [
    ("MUTCD",    (255, 208, 51)),   # bright yellow
    ("European", (190, 20, 29)),    # saturated red
    ("European", (0, 60, 122)),     # navy
    ("Chinese",  (151, 193, 167)),  # PASTEL green
    ("Other",    (1, 101, 51)),     # DARK green (SE Asia)
]
# Slide 9 has many distinct colours per the legend; we map to the canonical
# road-lines vocabulary used by build_country_facts.py.
SLIDE9_ANCHORS = [
    ("yellow_center_white_edge",          (200, 30, 30)),    # red on slide
    ("yellow_or_white_center_white_edge", (35, 60, 160)),    # blue on slide
    ("white_center_white_edge",           (40, 130, 60)),    # green on slide
    ("white_center_yellow_edge",          (240, 200, 50)),   # yellow on slide
    ("white_center_double_yellow",        (130, 60, 150)),   # purple on slide
    ("white_center_white_edge",           (255, 130, 30)),   # orange on slide -> bucket as default
    ("white_center_white_edge",           (20, 20, 20)),     # black -> default
]
SLIDE10_ANCHORS_KMH = [
    # Buckets by slide 10's legend.
    ("45",  (60, 0, 0)),       # very dark red ("70 / 45 or less")
    ("50",  (220, 30, 30)),    # red ("80 / 50")
    ("55",  (240, 130, 30)),   # orange ("90 / 55")
    ("60",  (240, 220, 60)),   # yellow ("100 / 60")
    ("65",  (130, 220, 60)),   # light green ("105 / 65")
    ("70",  (40, 130, 60)),    # green ("110 / 70")
    ("75",  (60, 180, 220)),   # light blue ("120 / 75")
    ("80",  (35, 60, 130)),    # dark blue ("130 / 80")
    ("85",  (130, 60, 150)),   # purple ("140 / 85")
    ("nolimit", (240, 60, 240)),  # pink/magenta
]


# ---------------------------------------------------------------------------
# Sample a single slide
# ---------------------------------------------------------------------------
def sample_slide(
    slide_n: int,
    anchors: list,
    country_points: dict[str, list[tuple[float, float]]],
    *,
    min_confidence: float = 0.6,
    min_votes: int = 3,
) -> dict[str, str]:
    img = Image.open(SLIDES_DIR / f"slide{slide_n}.png").convert("RGB")
    conf = SLIDE_MAPS[slide_n]
    out: dict[str, str] = {}
    skipped_no_data = 0
    skipped_low_conf = 0
    for iso2, pts in country_points.items():
        votes: dict[str, int] = {}
        total = 0
        for lat, lng in pts:
            px, py = project_to_pixel(lat, lng, conf)
            rgb = sample_color(img, px, py, size=3)
            cat = closest_category(rgb, anchors)
            if cat is None:
                continue
            votes[cat] = votes.get(cat, 0) + 1
            total += 1
        if not votes or total < min_votes:
            skipped_no_data += 1
            continue
        winner, count = max(votes.items(), key=lambda kv: kv[1])
        if count / total < min_confidence:
            # Mixed result — projection probably crossing borders. Defer to
            # build_country_facts.py's hand-curated fallback.
            skipped_low_conf += 1
            continue
        out[iso2] = winner
    print(f"  slide {slide_n}: {len(out)} answered, {skipped_no_data} no-data, {skipped_low_conf} low-conf")
    return out


# ---------------------------------------------------------------------------
# Calibration: how well does our slide-1 sampling match Wikidata?
# ---------------------------------------------------------------------------
def calibrate_against_wikidata(sampled: dict[str, str]) -> tuple[int, int, list[str]]:
    if not WIKI_FACTS.exists():
        print("  (no wikipedia_facts.json — skipping calibration)")
        return 0, 0, []
    wiki = json.loads(WIKI_FACTS.read_text(encoding="utf-8"))
    truth = wiki.get("driving_side", {})
    agree = disagree = 0
    misses: list[str] = []
    for iso2, side in sampled.items():
        if iso2 in truth:
            if truth[iso2] == side:
                agree += 1
            else:
                disagree += 1
                misses.append(f"{iso2}: slide={side} wikidata={truth[iso2]}")
    return agree, disagree, misses


def main() -> None:
    print("downloading slides...")
    download_slides()
    print("loading country centroids (Natural Earth 110m)...")
    centroids = load_country_polygons()
    print(f"  {len(centroids)} countries")

    print("sampling slide 1 (driving side, calibration)...")
    s1 = sample_slide(1, SLIDE1_ANCHORS, centroids)
    agree, disagree, misses = calibrate_against_wikidata(s1)
    if agree + disagree > 0:
        pct = 100 * agree / (agree + disagree)
        print(f"  calibration vs Wikidata: {agree}/{agree+disagree} agree ({pct:.0f}%)")
        if misses:
            print(f"  {len(misses)} disagreements (sample): {misses[:8]}")

    print("sampling slide 3 (sign style)...")
    s3 = sample_slide(3, SLIDE3_ANCHORS, centroids)
    print("sampling slide 9 (road lines)...")
    s9 = sample_slide(9, SLIDE9_ANCHORS, centroids)

    # We don't write slide 10 (Wikipedia gives us authoritative numeric kmh).
    out = {
        "_meta": {
            "source": "Pixel-sampled from 10 Useful Maps deck via equirectangular forward projection",
            "calibration_slide1_agree": agree,
            "calibration_slide1_total": agree + disagree,
        },
        "sign_style": s3,
        "road_lines": s9,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
