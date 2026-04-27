"""
Distills plonkit_raw.json into the lean tips.json the extension bundles.

Per-country output schema (ISO-2 keyed):
{
  "AU": {
    "name": "Australia",
    "plonkit_slug": "australia",
    "key_meta": "short one-liner that anchors the country",
    "sections": [
      {
        "id": "identify",     # stable id used by overlay tabs
        "title": "Identify",  # tab label
        "bullets": ["...", "..."],
        "images":  [{"src": "...", "caption": "..."}, ...]
      },
      ...
    ]
  }, ...
}

Distillation logic:
- Walk every plonkit section (H3/H4) in reading order.
- Classify each section into one of: identify, regional, spotlight (others
  dropped — Step 4 "Maps and resources" is just outbound links).
- Within each, take up to 8 bullets (first ~2 sentences each) and up to 6
  images.
- key_meta is the very first bullet of "identify" — the elevator-pitch tip.
"""
import argparse
import json
import re
from pathlib import Path

SLUG_TO_ISO2 = {
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
    "falkland-islands":"FK","british-indian-ocean-territory":"IO","christmas-island":"CX",
    "cocos-islands":"CC","pitcairn-islands":"PN","south-georgia-sandwich-islands":"GS",
    "azores":"PT-AZ","madeira":"PT-MA","alaska":"US-AK","hawaii":"US-HI",
    "guam":"GU","northern-mariana-islands":"MP","american-samoa":"AS",
    "us-minor-outlying-islands":"UM","us-virgin-islands":"VI","antarctica":"AQ",
}
SKIP_NON_COUNTRY = {"beginners-guide", "spillover-countries"}

SECTION_BUCKETS = [
    ("identify", "Identify", ("identif", "step 1")),
    ("regional", "Regional", ("regional", "step 2", "subdivision", "landscape",
                              "infrastruct", "region-specific", "county-specific",
                              "island specific", "island-specific")),
    ("spotlight", "Spotlight", ("spotlight", "step 3", "very specific")),
]


def classify_section(name: str) -> str | None:
    n = name.lower()
    for sid, _label, needles in SECTION_BUCKETS:
        if any(x in n for x in needles):
            return sid
    return None


def first_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n]).strip()


# Words that look proper-noun-y but are not place names. Trimmed by hand from
# inspecting the scraper output. Add as needed.
PLACE_STOP = frozenset([
    "The", "A", "An", "In", "On", "Of", "At", "And", "But", "For", "To", "With", "By",
    "Note", "Notes", "Generation", "Google", "European", "American", "African",
    "Asian", "EU", "US", "USA", "UK", "Street", "View", "License", "Plate", "Plates",
    "GeoGuessr", "Spotlight", "Step", "Identify", "Identifying", "Country", "Countries",
    "World", "Map", "Maps", "Coverage", "Cars", "Car", "Roads", "Road", "Highway",
    "Interstate", "Bridge", "Bridges", "Style", "Some", "Most", "Many", "All", "These",
    "Those", "Looking", "Note", "Generally", "However", "Therefore", "Northern",
    "Southern", "Eastern", "Western", "North", "South", "East", "West", "Central",
    "Latin", "Old", "New", "Big", "Small", "Long", "Short", "Top", "Front", "Back",
    "Side", "Local", "Public", "Private", "Mass", "Pass", "Forest", "Forests",
    "Mountain", "Mountains", "Valley", "Valleys", "River", "Rivers", "Lake", "Lakes",
    "Sea", "Ocean", "Coast", "Island", "Islands", "Plate.", "Coverage.", "Map.",
    "Hood", "Suv", "Suvs", "Truck", "Trucks", "Camera", "Government", "Official",
    "British", "Spanish", "French", "German", "Italian", "English", "Russian",
    "Chinese", "Japanese", "Korean", "Arabic", "Cyrillic", "Roman",
    "Christian", "Catholic", "Buddhist", "Muslim", "Hindu",
    "Federal", "State", "States", "City", "Cities", "Town", "Towns", "Village",
    "Villages", "County", "Counties", "Province", "Provinces", "Region", "Regions",
    "Department", "District", "Districts", "Capital", "Border", "Borders",
])


def extract_places(text: str, country_name: str) -> list[str]:
    """Pull proper-noun phrases that look like place names. Best-effort — the
    runtime filter is forgiving, and we always fall back to showing everything
    when the filter eliminates all items in a section."""
    matches = re.findall(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3}\b", text)
    seen, out = set(), []
    cn = country_name.lower()
    for m in matches:
        # Skip stop words and any phrase containing the country name.
        first = m.split()[0]
        if first in PLACE_STOP:
            continue
        if cn in m.lower():
            continue
        # Skip ALL-CAPS acronyms (e.g., NOTE, MPH).
        if m.isupper():
            continue
        # Skip leading-of-sentence false positives — single capitalized word
        # at sentence start that's also a common verb/adverb.
        key = m.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


def distill_country(slug: str, raw: dict) -> dict:
    """Preserve plonkit's reading order so each image stays right after the
    text that describes it. Each section becomes an ordered `items` array
    of {type: 'text', text} or {type: 'image', src, caption} entries."""
    name = raw["name"]
    sections_raw: dict[str, list[dict]] = raw.get("sections", {})

    buckets: dict[str, dict] = {sid: {"items": [], "seen_text": set(), "seen_img": set(),
                                        "n_text": 0, "n_img": 0}
                                 for sid, _, _ in SECTION_BUCKETS}

    # Caps per section to keep tips.json reasonable. We allow more than the
    # old flat-bullets cap because images riding alongside the text don't add
    # much weight (URLs only).
    MAX_TEXT, MAX_IMG = 14, 14

    for sec_name, items in sections_raw.items():
        sid = classify_section(sec_name)
        if not sid:
            continue
        b = buckets[sid]
        for item in items:
            if item["type"] == "text" and b["n_text"] < MAX_TEXT:
                s = first_sentences(item["text"], 2)
                if 20 < len(s) < 400 and s not in b["seen_text"]:
                    rec = {"type": "text", "text": s}
                    # Only tag places for region/spotlight; identify stays
                    # unfiltered at runtime so no point computing places.
                    if sid in {"regional", "spotlight"}:
                        places = extract_places(s, raw["name"])
                        if places:
                            rec["places"] = places
                    b["items"].append(rec)
                    b["seen_text"].add(s)
                    b["n_text"] += 1
            elif item["type"] == "image" and b["n_img"] < MAX_IMG:
                src = item["src"]
                if src in b["seen_img"]:
                    continue
                b["items"].append({
                    "type": "image",
                    "src": src,
                    "caption": item.get("caption") or item.get("alt") or "",
                })
                b["seen_img"].add(src)
                b["n_img"] += 1

    sections_out = []
    for sid, label, _ in SECTION_BUCKETS:
        b = buckets[sid]
        if b["items"]:
            sections_out.append({
                "id": sid,
                "title": label,
                "items": b["items"],
            })

    key_meta = ""
    for sec in sections_out:
        if sec["id"] == "identify":
            for it in sec["items"]:
                if it["type"] == "text":
                    key_meta = first_sentences(it["text"], 1)
                    break
            break

    return {
        "name": name,
        "plonkit_slug": slug,
        "key_meta": key_meta,
        "sections": sections_out,
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
        "_meta": {"version": "0.3.0", "source": "plonkit (Playwright scrape)"}
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

    Path(args.out).write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {args.out} ({len(bundle) - 1} countries)")
    if misses:
        print(f"unmapped slugs: {misses}")


if __name__ == "__main__":
    main()
