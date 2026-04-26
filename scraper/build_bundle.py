"""
Distills plonkit_raw.json + learnablemeta_raw.json into the lean tips.json
that the extension bundles.

Usage:
    python scraper/build_bundle.py [--plonkit ... --learnable ... --out ...]

Output schema (per country, ISO-2 keyed):
{
  "AU": {
    "name": "Australia",
    "plonkit_slug": "australia",
    "identify": ["short bullet 1", "short bullet 2", ...],   # max 5
    "key_meta": ["short label 1", "short label 2"],
    "vs": { "NZ": "one-line distinguisher" }
  }, ...
}

We rely on a static slug -> ISO-2 mapping for now (sourced from plonkit's
country directory). Distillation is intentionally heuristic: take first ~5
sentences from "Step 1 - Identifying" sections, plus first sentence from
"Spotlight" subsections.
"""
import argparse
import json
import re
from pathlib import Path

# Bare-minimum slug -> iso2. Extend by hand as plonkit covers more countries.
SLUG_TO_ISO2 = {
    "albania":"AL","andorra":"AD","argentina":"AR","australia":"AU","austria":"AT","bangladesh":"BD",
    "belarus":"BY","belgium":"BE","bhutan":"BT","bolivia":"BO","botswana":"BW","brazil":"BR","bulgaria":"BG",
    "cambodia":"KH","canada":"CA","chile":"CL","colombia":"CO","costa-rica":"CR","croatia":"HR","cyprus":"CY",
    "czechia":"CZ","denmark":"DK","dominican-republic":"DO","ecuador":"EC","estonia":"EE","eswatini":"SZ",
    "faroe-islands":"FO","finland":"FI","france":"FR","germany":"DE","ghana":"GH","greece":"GR","greenland":"GL",
    "guatemala":"GT","hungary":"HU","iceland":"IS","india":"IN","indonesia":"ID","ireland":"IE","israel":"IL",
    "italy":"IT","japan":"JP","jordan":"JO","kazakhstan":"KZ","kenya":"KE","kyrgyzstan":"KG","laos":"LA",
    "latvia":"LV","lebanon":"LB","lesotho":"LS","liechtenstein":"LI","lithuania":"LT","luxembourg":"LU",
    "madagascar":"MG","malaysia":"MY","malta":"MT","mexico":"MX","monaco":"MC","mongolia":"MN","montenegro":"ME",
    "netherlands":"NL","new-zealand":"NZ","nigeria":"NG","north-macedonia":"MK","norway":"NO","oman":"OM",
    "pakistan":"PK","palestine":"PS","panama":"PA","peru":"PE","philippines":"PH","poland":"PL","portugal":"PT",
    "puerto-rico":"PR","qatar":"QA","romania":"RO","russia":"RU","saudi-arabia":"SA","senegal":"SN","serbia":"RS",
    "singapore":"SG","slovakia":"SK","slovenia":"SI","south-africa":"ZA","south-korea":"KR","spain":"ES",
    "sri-lanka":"LK","svalbard":"SJ","sweden":"SE","switzerland":"CH","taiwan":"TW","thailand":"TH","tunisia":"TN",
    "turkey":"TR","uganda":"UG","ukraine":"UA","united-arab-emirates":"AE","united-kingdom":"GB",
    "united-states":"US","uruguay":"UY","vietnam":"VN","zimbabwe":"ZW","san-marino":"SM","azerbaijan":"AZ",
    "armenia":"AM","georgia":"GE","north-korea":"KP","jersey":"JE","gibraltar":"GI","isle-of-man":"IM",
    "guernsey":"GG","martinique":"MQ","reunion":"RE","french-guiana":"GF","guadeloupe":"GP","mayotte":"YT",
    "curacao":"CW","aruba":"AW","american-samoa":"AS","bermuda":"BM","cayman-islands":"KY",
}


def first_sentences(text: str, n: int = 1) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n]).strip()


def distill_country(slug: str, raw: dict) -> dict:
    name = raw["name"]
    sections = raw.get("sections", {})
    identify_keys = [k for k in sections if "identif" in k.lower() or "step 1" in k.lower()]
    spotlight_keys = [k for k in sections if "spotlight" in k.lower() or "step 3" in k.lower()]

    identify_bullets: list[str] = []
    for k in identify_keys:
        for para in sections[k]:
            s = first_sentences(para, 1)
            if 20 < len(s) < 220:
                identify_bullets.append(s)
            if len(identify_bullets) >= 5:
                break
        if len(identify_bullets) >= 5:
            break

    key_meta: list[str] = []
    for k in spotlight_keys:
        for para in sections[k][:3]:
            s = first_sentences(para, 1)
            if 10 < len(s) < 80:
                key_meta.append(s)
            if len(key_meta) >= 2:
                break

    return {
        "name": name,
        "plonkit_slug": slug,
        "identify": identify_bullets[:5],
        "key_meta": key_meta[:2] or [identify_bullets[0]] if identify_bullets else [],
        "vs": {},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plonkit", default="scraper/plonkit_raw.json")
    ap.add_argument("--learnable", default="scraper/learnablemeta_raw.json")
    ap.add_argument("--out", default="extension/data/tips.json")
    args = ap.parse_args()

    plonkit_path = Path(args.plonkit)
    if not plonkit_path.exists():
        print(f"missing {plonkit_path}; run scrape_plonkit.py first")
        return
    plonkit_raw = json.loads(plonkit_path.read_text())

    bundle: dict[str, dict] = {
        "_meta": {"version": "0.1.0", "source": "plonkit + learnablemeta scrape"}
    }
    for slug, raw in plonkit_raw.items():
        iso2 = SLUG_TO_ISO2.get(slug)
        if not iso2:
            continue
        bundle[iso2] = distill_country(slug, raw)

    Path(args.out).write_text(json.dumps(bundle, indent=2, ensure_ascii=False))
    print(f"wrote {args.out} ({len(bundle) - 1} countries)")


if __name__ == "__main__":
    main()
