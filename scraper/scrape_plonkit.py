"""
Scrapes plonkit.net per-country guide pages and produces a JSON map keyed by country slug.

Usage:
    python scraper/scrape_plonkit.py [--out scraper/plonkit_raw.json]

Notes:
    - plonkit.net is generous with hobbyist scrapers but please don't hammer it.
    - We pause 1s between requests.
    - Output is intentionally raw (full text per section); build_bundle.py distills it.
"""
import argparse
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.plonkit.net"
SLEEP = 1.0
HEADERS = {"User-Agent": "PlonkerExtension/0.1 (personal study tool)"}


def fetch(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def country_slugs() -> list[str]:
    """Plonkit's homepage map links to every covered country page.

    The country list isn't a clean <ul> on /guide; instead each country has its
    own top-level slug (e.g. /cyprus, /vietnam). We discover them by walking the
    sitemap.
    """
    soup = fetch(f"{BASE}/sitemap.xml")
    slugs = []
    for loc in soup.find_all("loc"):
        url = loc.text.strip()
        m = re.match(rf"^{re.escape(BASE)}/([a-z0-9-]+)/?$", url)
        if not m:
            continue
        slug = m.group(1)
        if slug in {
            "guide", "beginners-guide", "maps", "leaderboard", "tools",
            "donate", "regional", "highscores", "speedruns", "top",
            "rules", "submit", "map", "feedback", "guide-editor",
            "changelog", "privacy",
        }:
            continue
        slugs.append(slug)
    return sorted(set(slugs))


def scrape_country(slug: str) -> dict | None:
    soup = fetch(f"{BASE}/{slug}")
    h1 = soup.find("h1")
    if not h1:
        return None
    name = h1.get_text(strip=True)
    sections: dict[str, list[str]] = {}
    current_key = None
    for el in soup.find_all(["h3", "h4", "p", "li"]):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if el.name in {"h3", "h4"}:
            current_key = text
            sections.setdefault(current_key, [])
        elif current_key:
            sections[current_key].append(text)
    return {"slug": slug, "name": name, "sections": sections}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="scraper/plonkit_raw.json")
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    args = ap.parse_args()

    slugs = country_slugs()
    if args.limit:
        slugs = slugs[: args.limit]
    print(f"discovered {len(slugs)} country slugs")

    out: dict[str, dict] = {}
    for i, slug in enumerate(slugs, 1):
        try:
            data = scrape_country(slug)
            if data:
                out[slug] = data
                print(f"  [{i}/{len(slugs)}] {slug} \u2713")
        except Exception as e:
            print(f"  [{i}/{len(slugs)}] {slug} \u2717 {e}")
        time.sleep(SLEEP)

    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"wrote {args.out} ({len(out)} countries)")


if __name__ == "__main__":
    main()
