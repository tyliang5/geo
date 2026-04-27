"""
Scrapes plonkit.net per-country guide pages using Playwright (headless Chromium)
because plonkit is a Vite/React SPA whose country content is only present after
JS hydration. requests-only scraping returns an empty shell.

Usage:
    python -m playwright install chromium   # one-time
    python scraper/scrape_plonkit.py [--out scraper/plonkit_raw.json] [--limit N]
"""
import argparse
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from playwright.async_api import async_playwright

BASE = "https://www.plonkit.net"

SKIP_SLUGS = {
    "guide", "maps", "leaderboard", "regional", "highscores", "top",
    "speedruns", "rules", "rules-solo", "rules-assisted", "map",
    "tools", "submit", "feedback", "veteran", "discord", "patreon",
    "donate", "guide-editor", "changelog", "privacy", "submissions",
    "log", "analytics", "login",
}


async def discover_slugs(page) -> list[str]:
    """Hit the sitemap and filter to plausible country slugs."""
    sitemap_text = await page.evaluate(
        "fetch('/sitemap.xml').then(r => r.text())"
    )
    slugs = []
    for url in re.findall(r"<loc>(.*?)</loc>", sitemap_text):
        m = re.match(rf"^{re.escape(BASE)}/([a-z0-9-]+)/?$", url.strip())
        if not m:
            continue
        slug = m.group(1)
        if slug in SKIP_SLUGS:
            continue
        slugs.append(slug)
    return sorted(set(slugs))


async def scrape_country(page, slug: str) -> dict | None:
    await page.goto(f"{BASE}/{slug}", wait_until="networkidle", timeout=30000)
    # Give React a beat to render images
    try:
        await page.wait_for_selector("h1", timeout=10000)
        await page.wait_for_function(
            "document.querySelectorAll('img').length > 5",
            timeout=10000,
        )
    except Exception:
        pass

    # Extract DOM in reading order, grouped by H3/H4 sections.
    data = await page.evaluate("""(BASE) => {
        const root = document.querySelector('main') || document.querySelector('article') || document.body;
        const sections = {};
        let current = 'intro';
        sections[current] = [];
        const all = root.querySelectorAll('h1, h3, h4, p, li, img, figcaption');
        all.forEach((el) => {
            const tag = el.tagName;
            if (tag === 'H3' || tag === 'H4') {
                current = el.innerText.trim() || current;
                if (!sections[current]) sections[current] = [];
            } else if (tag === 'P' || tag === 'LI') {
                const text = el.innerText.trim();
                if (text) sections[current].push({ type: 'text', text });
            } else if (tag === 'IMG') {
                const src = el.src || el.dataset?.src;
                if (!src) return;
                if (src.includes('plonk-it') || src.includes('icon')) return;
                const fig = el.closest('figure');
                let caption = '';
                if (fig) {
                    const cap = fig.querySelector('figcaption');
                    if (cap) caption = cap.innerText.trim();
                }
                sections[current].push({
                    type: 'image',
                    src,
                    alt: el.alt || '',
                    caption,
                });
            }
        });
        return {
            name: document.querySelector('h1')?.innerText?.trim() || null,
            sections,
        };
    }""", BASE)
    if not data or not data.get("name"):
        return None
    data["slug"] = slug
    return data


async def main_async(args) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="PlonkerExtension/0.1 (personal study tool)"
        )
        page = await context.new_page()

        await page.goto(BASE, wait_until="networkidle", timeout=30000)
        slugs = await discover_slugs(page)
        if args.limit:
            slugs = slugs[: args.limit]
        print(f"discovered {len(slugs)} country slugs")

        out: dict[str, dict] = {}
        for i, slug in enumerate(slugs, 1):
            try:
                data = await scrape_country(page, slug)
                if data:
                    out[slug] = data
                    n_text = sum(1 for s in data["sections"].values() for x in s if x["type"] == "text")
                    n_img = sum(1 for s in data["sections"].values() for x in s if x["type"] == "image")
                    print(f"  [{i}/{len(slugs)}] {slug} ok ({n_text} text, {n_img} img)", flush=True)
                else:
                    print(f"  [{i}/{len(slugs)}] {slug} no data", flush=True)
            except Exception as e:
                print(f"  [{i}/{len(slugs)}] {slug} FAIL {e}", flush=True)

        await browser.close()

    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out} ({len(out)} countries)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="scraper/plonkit_raw.json")
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
