"""
Downloads every image referenced in plonkit_raw.json + learnablemeta_raw.json
to extension/assets/img/ so the bundle can render them offline (and so the
OCR step can run on local files without re-fetching).

Adds a `local_path` field next to each image's `src`. The path is relative
to the extension root, e.g. `assets/img/plonkit/ireland/Donegal_Gen_4_roads.png`.

Usage:
    python scraper/download_images.py
"""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path("extension/assets/img")
HEADERS = {"User-Agent": "PlonkerExtension/0.8 (personal study tool)"}
TIMEOUT = 30
RETRIES = 3


def safe_filename(name: str) -> str:
    """Allow only ASCII letters, digits, dot, underscore, dash, and forward slash."""
    return re.sub(r"[^A-Za-z0-9._\-]", "_", name)


def plonkit_local_path(src: str) -> Path | None:
    """Map a plonkit CDN URL to its local relative path."""
    # https://www.plonkit.net/images/resize/600/80/senegal/0_summary.png
    m = re.search(r"/images/(?:resize/\d+/\d+/)?([^/]+)/([^/?#]+)$", src)
    if not m:
        return None
    country, fname = m.group(1), m.group(2)
    return ROOT / "plonkit" / safe_filename(country) / safe_filename(fname)


def learnablemeta_local_path(src: str) -> Path | None:
    """Map a learnablemeta CDN URL to its local relative path."""
    # https://learnablemeta.com/images/HY8vZ...avif
    m = re.search(r"/images/([^/?#]+)$", src)
    if not m:
        return None
    fname = m.group(1)
    if "." not in fname:
        # add an extension based on hash so filename is unique
        fname += ".avif"
    return ROOT / "lm" / safe_filename(fname)


def fetch(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return True
        except Exception as e:
            if attempt == RETRIES - 1:
                print(f"  fail {url}: {e}")
                return False
            time.sleep(2 ** attempt)
    return False


def process_plonkit(plonkit_path: Path) -> tuple[int, int]:
    raw = json.loads(plonkit_path.read_text(encoding="utf-8"))
    n_total = 0
    n_ok = 0
    for slug, data in raw.items():
        for sec_items in data.get("sections", {}).values():
            for item in sec_items:
                if item.get("type") != "image":
                    continue
                src = item.get("src", "")
                local = plonkit_local_path(src)
                if not local:
                    continue
                n_total += 1
                if fetch(src, local):
                    n_ok += 1
                    item["local_path"] = str(local).replace("\\", "/").replace(
                        "extension/", ""
                    )
        if n_total % 50 == 0 and n_total:
            print(f"  plonkit {n_ok}/{n_total} ...", flush=True)
    plonkit_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return n_ok, n_total


def process_learnablemeta(lm_path: Path) -> tuple[int, int]:
    raw = json.loads(lm_path.read_text(encoding="utf-8"))
    n_total = 0
    n_ok = 0
    seen: set[str] = set()
    for mp in raw:
        for meta in mp.get("metas", []):
            local_paths = []
            for src in meta.get("images", []):
                local = learnablemeta_local_path(src)
                if not local:
                    local_paths.append(None)
                    continue
                if src not in seen:
                    seen.add(src)
                    n_total += 1
                    if fetch(src, local):
                        n_ok += 1
                        local_paths.append(str(local).replace("\\", "/").replace("extension/", ""))
                    else:
                        local_paths.append(None)
                else:
                    n_ok += 1
                    local_paths.append(str(local).replace("\\", "/").replace("extension/", ""))
            meta["local_paths"] = local_paths
            if n_total % 50 == 0 and n_total:
                print(f"  lm {n_ok}/{n_total} ...", flush=True)
    lm_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return n_ok, n_total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plonkit", default="scraper/plonkit_raw.json")
    ap.add_argument("--learnable", default="scraper/learnablemeta_raw.json")
    args = ap.parse_args()

    print("downloading plonkit images...")
    p_ok, p_total = process_plonkit(Path(args.plonkit))
    print(f"plonkit: {p_ok}/{p_total} ok")

    print("downloading learnablemeta images...")
    l_ok, l_total = process_learnablemeta(Path(args.learnable))
    print(f"learnablemeta: {l_ok}/{l_total} ok")


if __name__ == "__main__":
    main()
