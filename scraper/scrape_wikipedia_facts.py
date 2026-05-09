"""Pull definitive country fact tables from Wikipedia (driving side + highway
speed limits) so build_country_facts.py can override hand-curated guesses with
ground-truth.

Output: scraper/wikipedia_facts.json keyed by ISO2 alpha-2 code.

Run:
    python scraper/scrape_wikipedia_facts.py
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "scraper" / "wikipedia_facts.json"

UA = "Mozilla/5.0 (Plonker geo-fact scraper, +https://github.com/tyliang5/geo)"

# Country-name → ISO2. Keyed by lowercase normalised forms; values are ISO2.
# We seed from the bundled country-slugs.js so we stay in sync with the
# extension's known set.
def load_iso2_map() -> dict[str, str]:
    text = (REPO / "extension" / "src" / "data" / "country-slugs.js").read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for m in re.finditer(r"^\s+([A-Z]{2}):\s*\{\s*name:\s*'([^']+)'", text, re.MULTILINE):
        iso2, name = m.group(1), m.group(2)
        # Decode JS \uXXXX escapes.
        name = name.encode("ascii", "backslashreplace").decode("unicode_escape")
        out[normalise_name(name)] = iso2
    # Common aliases Wikipedia uses but country-slugs.js doesn't.
    aliases = {
        "uk": "GB", "england": "GB", "great britain": "GB",
        "usa": "US", "u.s.": "US", "u.s.a.": "US",
        "south korea": "KR", "north korea": "KP",
        "russia": "RU", "russian federation": "RU",
        "czech republic": "CZ", "czechia": "CZ",
        "vietnam": "VN", "viet nam": "VN",
        "ivory coast": "CI", "cote d'ivoire": "CI",
        "myanmar": "MM", "burma": "MM",
        "east timor": "TL", "timor-leste": "TL",
        "swaziland": "SZ", "eswatini": "SZ",
        "macedonia": "MK", "north macedonia": "MK",
        "burma (myanmar)": "MM",
        "iran": "IR", "uae": "AE",
        "republic of ireland": "IE",
        "republic of china": "TW", "taiwan": "TW",
        "people's republic of china": "CN", "china": "CN",
        "hong kong sar": "HK", "macau sar": "MO", "macao": "MO",
    }
    for k, v in aliases.items():
        out.setdefault(normalise_name(k), v)
    return out


def normalise_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\[[^\]]*\]", "", n)         # strip footnote brackets
    n = re.sub(r"\([^)]*\)", "", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def fetch_html(url: str) -> BeautifulSoup:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


# ---------------------------------------------------------------------------
# Driving side via Wikidata SPARQL — wd:P1622 (driving side):
#   Q13196750 = left, Q14565199 = right.
# ---------------------------------------------------------------------------
SPARQL = "https://query.wikidata.org/sparql"
SIDE_LEFT_QID = "Q11920728"
SIDE_RIGHT_QID = "Q14565199"

DRIVING_QUERY = """
SELECT ?iso2 ?side WHERE {
  ?country wdt:P297 ?iso2 .
  ?country wdt:P1622 ?side .
}
"""


def scrape_driving_side() -> dict[str, str]:
    r = requests.get(
        SPARQL,
        params={"query": DRIVING_QUERY, "format": "json"},
        headers={"User-Agent": UA, "Accept": "application/sparql-results+json"},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    out: dict[str, str] = {}
    for binding in data.get("results", {}).get("bindings", []):
        iso2 = binding["iso2"]["value"]
        side_uri = binding["side"]["value"]
        if SIDE_LEFT_QID in side_uri:
            out[iso2] = "left"
        elif SIDE_RIGHT_QID in side_uri:
            out[iso2] = "right"
    return out


# ---------------------------------------------------------------------------
# Speed limits (highway / motorway max).
# ---------------------------------------------------------------------------
SPEED_URL = "https://en.wikipedia.org/wiki/Speed_limits_by_country"


def parse_kmh(text: str) -> int | None:
    """Pull the first kmh number out of a cell. Handles 'no limit', '110 (60)',
    ranges like '100-130'. We take the MAX (most permissive) number."""
    if not text:
        return None
    t = text.lower()
    if "no limit" in t or "unlimited" in t or "no speed limit" in t:
        return 999
    # Strip footnote markers and parentheticals.
    t = re.sub(r"\[[^\]]*\]", "", t)
    nums = [int(n) for n in re.findall(r"\b(\d{2,3})\b", t)]
    nums = [n for n in nums if 30 <= n <= 200]
    return max(nums) if nums else None


def scrape_speed_limits(name_to_iso: dict[str, str]) -> dict[str, int]:
    """Return ISO2 -> max highway speed in kmh."""
    soup = fetch_html(SPEED_URL)
    tables = soup.select("table.wikitable")
    found: dict[str, int] = {}
    misses: list[str] = []
    for table in tables:
        headers = [th.get_text(" ", strip=True).lower() for th in table.select("tr th")]
        # Looking for a country column AND any column related to motorway.
        country_idx = None
        motorway_idx = None
        for i, h in enumerate(headers):
            if country_idx is None and ("country" in h or "jurisdiction" in h):
                country_idx = i
            if motorway_idx is None and ("motorway" in h or "freeway" in h or "expressway" in h or "highway" in h):
                motorway_idx = i
        if country_idx is None or motorway_idx is None:
            continue
        for tr in table.select("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) <= max(country_idx, motorway_idx):
                continue
            country_cell = cells[country_idx].get_text(" ", strip=True)
            speed_cell = cells[motorway_idx].get_text(" ", strip=True)
            kmh = parse_kmh(speed_cell)
            if kmh is None:
                continue
            iso2 = name_to_iso.get(normalise_name(country_cell))
            if iso2:
                # Keep the MAX across multiple table appearances (some
                # countries have province-level rows).
                if found.get(iso2, 0) < kmh:
                    found[iso2] = kmh
            else:
                misses.append(country_cell)
    if misses:
        print(f"[speed] {len(misses)} unmatched (sample): {misses[:8]}", file=sys.stderr)
    return found


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    name_to_iso = load_iso2_map()
    print(f"loaded {len(name_to_iso)} name aliases")
    print("scraping driving side from Wikidata...")
    driving = scrape_driving_side()
    print(f"  got {len(driving)} countries")
    print("scraping speed limits...")
    speeds = scrape_speed_limits(name_to_iso)
    print(f"  got {len(speeds)} countries")

    out = {
        "_meta": {
            "source": "Wikipedia (Left-_and_right-hand_traffic, Speed_limits_by_country)",
        },
        "driving_side": driving,
        "speed_limit_max_kmh": speeds,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
