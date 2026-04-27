"""
Distills plonkit_raw.json into the lean tips.json the extension bundles.

Usage:
    python scraper/build_bundle.py

Output schema (per country, ISO-2 keyed):
{
  "AU": {
    "name": "Australia",
    "plonkit_slug": "australia",
    "identify": ["short bullet 1", ...],   # up to 8
    "key_meta": ["short label 1", ...],    # up to 3
    "images":   [{"src": "...", "caption": "..."}, ...],   # up to 6
    "vs": { "NZ": "one-line distinguisher" }
  }, ...
}

Distillation heuristics:
- "Identify" bullets come from the first text items under any "Step 1 / Identifying"
  section, capped at sentence #1 if the paragraph is long.
- "Key meta" labels come from "Step 3 / Spotlight" sub-headings.
- Images: prefer those under "Step 1" + "Spotlight"; max 6 per country.
"""
import argparse
import json
import re
from pathlib import Path

# slug -> ISO-2. Includes covered territories that GG returns as their parent
# country code (e.g., Hawaii rounds come back as US, so hawaii also maps to US).
# When two slugs map to the same ISO-2, last-write-wins — main country pages
# come first to ensure they take precedence.
SLUG_TO_ISO2 = {
    # Main country pages
    "albania":"AL","andorra":"AD","argentina":"AR","armenia":"AM","aruba":"AW","australia":"AU",
    "austria":"AT","azerbaijan":"AZ","bangladesh":"BD","belarus":"BY","belgium":"BE","bermuda":"BM",
    "bhutan":"BT","bolivia":"BO","botswana":"BW","brazil":"BR","bulgaria":"BG","cambodia":"KH",
    "canada":"CA","cayman-islands":"KY","chile":"CL","china":"CN","colombia":"CO","costa-rica":"CR",
    "croatia":"HR","curacao":"CW","cyprus":"CY","czechia":"CZ","denmark":"DK","dominican-republic":"DO",
    "ecuador":"EC","egypt":"EG","estonia":"EE","eswatini":"SZ","faroe-islands":"FO","finland":"FI",
    "france":"FR","french-guiana":"GF","georgia":"GE","germany":"DE","ghana":"GH","gibraltar":"GI",
    "greece":"GR","greenland":"GL","guadeloupe":"GP","guatemala":"GT","guernsey":"GG","hong-kong":"HK",
    "hungary":"HU","iceland":"IS","india":"IN","indonesia":"ID","iraq":"IQ","ireland":"IE",
    "isle-of-man":"IM","israel-west-bank":"IL","italy":"IT","japan":"JP","jersey":"JE","jordan":"JO",
    "kazakhstan":"KZ","kenya":"KE","kyrgyzstan":"KG","laos":"LA","latvia":"LV","lebanon":"LB",
    "lesotho":"LS","liechtenstein":"LI","lithuania":"LT","luxembourg":"LU","macau":"MO",
    "madagascar":"MG","malaysia":"MY","mali":"ML","malta":"MT","martinique":"MQ","mexico":"MX",
    "monaco":"MC","mongolia":"MN","montenegro":"ME","namibia":"NA","nepal":"NP","netherlands":"NL",
    "new-zealand":"NZ","nigeria":"NG","north-macedonia":"MK","norway":"NO","oman":"OM","pakistan":"PK",
    "panama":"PA","peru":"PE","philippines":"PH","poland":"PL","portugal":"PT","puerto-rico":"PR",
    "qatar":"QA","reunion":"RE","romania":"RO","russia":"RU","rwanda":"RW",
    "saint-pierre-and-miquelon":"PM","san-marino":"SM","sao-tome-and-principe":"ST","senegal":"SN",
    "serbia":"RS","singapore":"SG","slovakia":"SK","slovenia":"SI","south-africa":"ZA",
    "south-korea":"KR","spain":"ES","sri-lanka":"LK","svalbard":"SJ","sweden":"SE","switzerland":"CH",
    "taiwan":"TW","tanzania":"TZ","thailand":"TH","tunisia":"TN","turkey":"TR","uganda":"UG",
    "ukraine":"UA","united-arab-emirates":"AE","united-kingdom":"GB","united-states":"US","uruguay":"UY",
    "vanuatu":"VU","vietnam":"VN","zimbabwe":"ZW",
    # GG returns parent country codes for these territories. Last-write-wins
    # so a later collision overrides United States/etc., but we order so the
    # mainland country guide stays the canonical entry.
    "falkland-islands":"FK", "british-indian-ocean-territory":"IO",
    "christmas-island":"CX", "cocos-islands":"CC", "pitcairn-islands":"PN",
    "south-georgia-sandwich-islands":"GS",
    "azores":"PT-AZ",     # store under sub-key so PT mainland wins
    "madeira":"PT-MA",
    "alaska":"US-AK", "hawaii":"US-HI",
    "guam":"GU", "northern-mariana-islands":"MP", "american-samoa":"AS",
    "us-minor-outlying-islands":"UM", "us-virgin-islands":"VI",
    "antarctica":"AQ",
}
# Slugs that aren't real country guides (skip during distillation).
SKIP_NON_COUNTRY = {"beginners-guide", "spillover-countries"}


def first_sentences(text: str, n: int = 1) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n]).strip()


def section_matches(name: str, *needles: str) -> bool:
    n = name.lower()
    return any(needle in n for needle in needles)


def distill_country(slug: str, raw: dict) -> dict:
    name = raw["name"]
    sections: dict[str, list[dict]] = raw.get("sections", {})

    identify_bullets: list[str] = []
    spotlight_labels: list[str] = []
    images: list[dict] = []

    for sec_name, items in sections.items():
        is_id = section_matches(sec_name, "identif", "step 1")
        is_spot = section_matches(sec_name, "spotlight", "step 3")
        is_landscape = section_matches(sec_name, "landscape", "infrastruct", "step 2")

        for item in items:
            if item["type"] == "text":
                if is_id and len(identify_bullets) < 8:
                    s = first_sentences(item["text"], 2)
                    if 25 < len(s) < 260:
                        identify_bullets.append(s)
                elif is_spot and len(spotlight_labels) < 3:
                    s = first_sentences(item["text"], 1)
                    if 8 < len(s) < 80:
                        spotlight_labels.append(s)
                elif is_landscape and len(identify_bullets) < 8:
                    s = first_sentences(item["text"], 1)
                    if 25 < len(s) < 220:
                        identify_bullets.append(s)
            elif item["type"] == "image" and (is_id or is_spot or is_landscape) and len(images) < 8:
                images.append({
                    "src": item["src"],
                    "caption": item.get("caption") or item.get("alt") or "",
                })

    # Dedup images by URL.
    seen = set()
    images_unique = []
    for img in images:
        if img["src"] in seen:
            continue
        seen.add(img["src"])
        images_unique.append(img)

    return {
        "name": name,
        "plonkit_slug": slug,
        "identify": identify_bullets[:8],
        "key_meta": spotlight_labels[:3] or (identify_bullets[:1] if identify_bullets else []),
        "images": images_unique[:6],
        "vs": {},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plonkit", default="scraper/plonkit_raw.json")
    ap.add_argument("--out", default="extension/data/tips.json")
    args = ap.parse_args()

    plonkit_path = Path(args.plonkit)
    if not plonkit_path.exists():
        print(f"missing {plonkit_path}; run scrape_plonkit.py first")
        return
    plonkit_raw = json.loads(plonkit_path.read_text(encoding="utf-8"))

    bundle: dict[str, dict] = {
        "_meta": {"version": "0.2.0", "source": "plonkit + curated"}
    }
    misses = []
    for slug, raw in plonkit_raw.items():
        if slug in SKIP_NON_COUNTRY:
            continue
        iso2 = SLUG_TO_ISO2.get(slug)
        if not iso2:
            misses.append(slug)
            continue
        bundle[iso2] = distill_country(slug, raw)

    Path(args.out).write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out} ({len(bundle) - 1} countries)")
    if misses:
        print(f"unmapped slugs (add to SLUG_TO_ISO2): {misses}")


if __name__ == "__main__":
    main()
