"""
Scrapes learnablemeta.com for the canonical map IDs and per-map meta lists.

Usage:
    python scraper/scrape_learnablemeta.py [--out scraper/learnablemeta_raw.json]
"""
import argparse
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://learnablemeta.com"
HEADERS = {"User-Agent": "PlonkerExtension/0.1 (personal study tool)"}
SLEEP = 1.0


def fetch(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def list_maps() -> list[dict]:
    soup = fetch(f"{BASE}/maps")
    maps = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/maps/") and len(href) > len("/maps/"):
            map_id = href.split("/maps/")[1].split("?")[0]
            if len(map_id) == 24:
                maps.append({"id": map_id, "url": f"{BASE}{href}"})
    seen, dedup = set(), []
    for m in maps:
        if m["id"] in seen:
            continue
        seen.add(m["id"])
        dedup.append(m)
    return dedup


def scrape_map(map_id: str) -> dict:
    soup = fetch(f"{BASE}/maps/{map_id}")
    title_el = soup.find("h1") or soup.find("title")
    title = title_el.get_text(strip=True) if title_el else map_id
    metas = []
    for el in soup.find_all(["h2", "h3", "h4"]):
        txt = el.get_text(" ", strip=True)
        if " - " in txt:
            country, meta = txt.split(" - ", 1)
            metas.append({"country": country.strip(), "meta": meta.strip()})
    return {"id": map_id, "title": title, "metas": metas}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="scraper/learnablemeta_raw.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    maps = list_maps()
    if args.limit:
        maps = maps[: args.limit]
    print(f"discovered {len(maps)} maps")

    out = []
    for i, m in enumerate(maps, 1):
        try:
            out.append(scrape_map(m["id"]))
            print(f"  [{i}/{len(maps)}] {m['id']} \u2713")
        except Exception as e:
            print(f"  [{i}/{len(maps)}] {m['id']} \u2717 {e}")
        time.sleep(SLEEP)

    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
