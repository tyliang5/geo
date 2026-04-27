"""
Scrapes learnablemeta.com map pages and extracts the embedded `metaList` from
each page's SvelteKit hydration script.

Each map page is a SPA, so we use Playwright to render. The relevant data is
embedded inline as a serialized JS object inside one of the page's <script>
tags — no API calls happen. We pull that script's text, find the metaList
substring, and parse it out as JSON.

Output schema (per map):
    {
      "id": "66fda352ee1c8ee4735e1aa8",
      "title": "A Learnable Meta World - Basics",
      "metas": [
        {
          "id": 159,
          "name": "Australia - Bollard",
          "country": "Australia",
          "meta_label": "Bollard",
          "description": "Australian bollards are white with a red reflector...",
          "comparison": "Turkish bollards are similar but lack a back reflector...",
          "images": ["https://learnablemeta.com/images/...avif"],
          "locations_count": "20"
        },
        ...
      ]
    }

Usage:
    python scraper/scrape_learnablemeta.py [--out scraper/learnablemeta_raw.json]
"""
import argparse
import asyncio
import html
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

BASE = "https://learnablemeta.com"

# The full set of map IDs we currently allowlist as "learnable meta maps" in
# the extension. Mirror of extension/src/data/learnable-meta-map-ids.js.
MAP_IDS = [
    "66fda352ee1c8ee4735e1aa8", "66c0d3feff4dbe492e06174e", "66fd7c30b34ca9145ec96a6a",
    "66fda32fbc5afd45d3eb187d", "6447040b0517cbd5807a5145", "67695a0a9c0874b92709eedb",
    "671f7d0a62423ae866572ba6", "66fda3097e08dc03b5bb3f0e", "66fda319b477f9e4abdd34fa",
    "66ab2cd85d18e95700fa096c", "679b5be42a42846e1a272282", "66fda2e27e08dc03b5bb3d6e",
    "67d990c22e001b61f4f12506", "67272d30e0770225ea846f20", "66fda342413f41ca32ef9d54",
    "66f455342063e93655dd047f", "67168e876b79c3cb4f964543", "66fda2f8ee1c8ee4735e167f",
    "679147020f521520242a97ad", "675fe6bf117a221c9f194ec5", "6730c7e71067595212e11a4d",
    "676c62e2f11f44713bb8a065", "67e32dde197792448ea33941", "67e4d8067f5a6ee78d3bd341",
    "6748ebd3ed709aab5ee74207", "67c4fd74c75d31e7ef0cdf16", "67c4a232522c482a8f7e9f3b",
    "680c5b37bf69f2103accaa9d", "6800370db17342310c1d87e3", "676f42551d0a37970a864bfe",
    "674f2fe42744d629924fb50c", "6845e983ef3ea9aea22825e1", "67af2aa7df4bac71b8fd0351",
    "67655173ff4ef64687b7ac08", "675de699d65a0013685f1fab", "675de935a43ee75565c82221",
    "678f7bc66a1f9e050835ef24", "6820f52c8d3f928d3dac4dfd", "67438c0a2e55e7ece126724f",
    "675dda62d4778cbeacd16ed2", "67d85ff8515a6aec219cd249", "67cfb3b298062e90c425123e",
    "67695421f11f44713ba7e2a3", "675deba1117a221c9f109bc7", "6857bcf673045641271a96df",
    "672537918a593cd5d6ad4cc0",
]


# Quick & dirty bracket-balanced extractor for `metaList:[...]` from the JS
# hydration script. Avoids pulling in a real JS parser.
def extract_meta_list(script_text: str) -> str | None:
    needle = "metaList:["
    i = script_text.find(needle)
    if i < 0:
        return None
    start = i + len(needle) - 1  # position of '['
    depth = 0
    in_str = False
    str_char = None
    escape = False
    for j in range(start, len(script_text)):
        c = script_text[j]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == str_char:
                in_str = False
        else:
            if c == '"' or c == "'":
                in_str = True
                str_char = c
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return script_text[start:j + 1]
    return None


# The hydration script uses unquoted keys (id, name, ...) plus \u003C escapes
# for HTML brackets. We can't json.loads it directly. The simplest reliable
# approach is to pull each meta object out with a balanced-brace walker, then
# extract fields with targeted regexes.
def parse_metas(meta_list_text: str) -> list[dict]:
    # First strip the outer brackets.
    inner = meta_list_text.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]

    metas = []
    # Walk top-level objects in inner.
    depth = 0
    in_str = False
    str_char = None
    escape = False
    obj_start = None
    for i, c in enumerate(inner):
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == str_char:
                in_str = False
            continue
        if c == '"' or c == "'":
            in_str = True
            str_char = c
            continue
        if c == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and obj_start is not None:
                obj = inner[obj_start:i + 1]
                metas.append(parse_meta_obj(obj))
                obj_start = None
    return [m for m in metas if m]


def _decode_js_string(s: str) -> str:
    """Unescape a JS string literal (the value between the surrounding quotes)."""
    s = s.encode("utf-8").decode("unicode_escape")
    return html.unescape(s)


def parse_meta_obj(obj_text: str) -> dict | None:
    # obj_text is like: {id:159,name:"X",note:"...",images:["..."],locationsCount:"20",footer:"..."}
    def grab_string(field: str) -> str | None:
        m = re.search(rf'\b{field}:"((?:[^"\\]|\\.)*)"', obj_text)
        return _decode_js_string(m.group(1)) if m else None

    def grab_int(field: str) -> int | None:
        m = re.search(rf'\b{field}:(\d+)', obj_text)
        return int(m.group(1)) if m else None

    def grab_string_array(field: str) -> list[str]:
        m = re.search(rf'\b{field}:\[((?:[^\]]|\\.)*?)\]', obj_text)
        if not m:
            return []
        body = m.group(1)
        return [
            _decode_js_string(x.group(1))
            for x in re.finditer(r'"((?:[^"\\]|\\.)*)"', body)
        ]

    name = grab_string("name") or ""
    note_html = grab_string("note") or ""
    note_text = _html_to_paragraphs(note_html)

    country, meta_label = "", ""
    if " - " in name:
        country, meta_label = name.split(" - ", 1)
    else:
        country = name

    description = note_text[0] if note_text else ""
    comparison = " ".join(note_text[1:]) if len(note_text) > 1 else ""

    return {
        "id": grab_int("id"),
        "name": name,
        "country": country.strip(),
        "meta_label": meta_label.strip(),
        "description": description,
        "comparison": comparison,
        "images": grab_string_array("images"),
        "locations_count": grab_string("locationsCount") or "",
    }


def _html_to_paragraphs(html_text: str) -> list[str]:
    # Note has <p>...</p> blocks, strip tags, return as list of paragraph strings.
    paragraphs = re.findall(r"<p>(.*?)</p>", html_text, re.DOTALL)
    if not paragraphs:
        return [re.sub(r"<[^>]+>", "", html_text).strip()] if html_text.strip() else []
    out = []
    for p in paragraphs:
        clean = re.sub(r"<[^>]+>", "", p)
        clean = clean.strip()
        if clean:
            out.append(clean)
    return out


async def scrape_map(page, map_id: str) -> dict | None:
    await page.goto(f"{BASE}/maps/{map_id}", wait_until="networkidle", timeout=30000)
    try:
        await page.wait_for_function(
            "[...document.querySelectorAll('script')].some(s => s.textContent.includes('metaList:['))",
            timeout=10000,
        )
    except Exception:
        return None

    script_text = await page.evaluate("""() => {
        const scripts = [...document.querySelectorAll('script')]
            .filter(s => s.textContent.includes('metaList:['));
        return scripts[0]?.textContent || '';
    }""")
    title = await page.evaluate("document.querySelector('h1')?.innerText?.trim() || ''")

    list_text = extract_meta_list(script_text)
    if not list_text:
        return {"id": map_id, "title": title, "metas": []}
    metas = parse_metas(list_text)
    return {"id": map_id, "title": title, "metas": metas}


async def main_async(args) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="PlonkerExtension/0.7 (personal study tool)"
        )
        page = await context.new_page()

        out = []
        for i, mid in enumerate(MAP_IDS, 1):
            try:
                data = await scrape_map(page, mid)
                if data:
                    out.append(data)
                    print(f"  [{i}/{len(MAP_IDS)}] {mid} ok ({len(data['metas'])} metas) — {data['title'][:60]}", flush=True)
                else:
                    print(f"  [{i}/{len(MAP_IDS)}] {mid} no data", flush=True)
            except Exception as e:
                print(f"  [{i}/{len(MAP_IDS)}] {mid} FAIL {e}", flush=True)

        await browser.close()

    Path(args.out).write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    total = sum(len(m["metas"]) for m in out)
    print(f"wrote {args.out} ({len(out)} maps, {total} total metas)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="scraper/learnablemeta_raw.json")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
