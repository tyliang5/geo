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


def distill_country(slug: str, raw: dict) -> dict:
    name = raw["name"]
    sections_raw: dict[str, list[dict]] = raw.get("sections", {})

    # Gather per-bucket bullets + images, preserving plonkit's reading order.
    buckets: dict[str, dict] = {sid: {"bullets": [], "images": [], "seen": set()}
                                 for sid, _, _ in SECTION_BUCKETS}

    for sec_name, items in sections_raw.items():
        sid = classify_section(sec_name)
        if not sid:
            continue
        b = buckets[sid]
        for item in items:
            if item["type"] == "text" and len(b["bullets"]) < 8:
                s = first_sentences(item["text"], 2)
                if 25 < len(s) < 320 and s not in b["seen"]:
                    b["bullets"].append(s)
                    b["seen"].add(s)
            elif item["type"] == "image" and len(b["images"]) < 6:
                src = item["src"]
                if src in b["seen"]:
                    continue
                b["seen"].add(src)
                b["images"].append({
                    "src": src,
                    "caption": item.get("caption") or item.get("alt") or "",
                })

    sections_out = []
    for sid, label, _ in SECTION_BUCKETS:
        b = buckets[sid]
        if b["bullets"] or b["images"]:
            sections_out.append({
                "id": sid,
                "title": label,
                "bullets": b["bullets"],
                "images": b["images"],
            })

    key_meta = ""
    for sec in sections_out:
        if sec["id"] == "identify" and sec["bullets"]:
            key_meta = first_sentences(sec["bullets"][0], 1)
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
