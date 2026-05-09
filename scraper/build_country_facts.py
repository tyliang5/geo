"""Build extension/data/country_facts.json from curated tables.

The tables here are seeded from the "10 Useful Maps" deck (driving side, sign
style, stop sign text, plate format, road-line scheme, speed limit, European
chevron colour, European pedestrian-sign stripe count) and cross-checked
against Wikipedia. Categorical only — perfect for the overlay's Quick Compare
strip that diffs actual vs your-guess country.

Run:
    python scraper/build_country_facts.py
"""
from __future__ import annotations
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SLUGS_JS = REPO / "extension" / "src" / "data" / "country-slugs.js"
OUT = REPO / "extension" / "data" / "country_facts.json"
WIKI_FACTS = REPO / "scraper" / "wikipedia_facts.json"
SLIDE_FACTS = REPO / "scraper" / "slide_facts.json"


def parse_iso2_codes() -> list[str]:
    """Pull the ISO2 list from country-slugs.js so we stay in sync."""
    text = SLUGS_JS.read_text(encoding="utf-8")
    return sorted(set(re.findall(r"^\s+([A-Z]{2}):\s*\{", text, re.MULTILINE)))


# ---------------------------------------------------------------------------
# Driving side. World map: countries that drive on the LEFT (everyone else
# drives on the right). Source: slide 1 + Wikipedia "Left- and right-hand
# traffic".
# ---------------------------------------------------------------------------
LEFT_HAND = {
    # British Isles + Mediterranean
    "GB", "IE", "IM", "JE", "GG", "MT", "CY",
    # Sub-Saharan Africa (former British colonies)
    "ZA", "ZW", "ZM", "MW", "MZ", "TZ", "KE", "UG", "BW", "LS", "SZ", "NA",
    "MU", "SC",
    # Indian subcontinent + South/SE Asia
    "IN", "PK", "BD", "NP", "BT", "LK", "MV",
    "JP", "TH", "ID", "MY", "SG", "BN", "TL", "HK", "MO",
    # Oceania
    "AU", "NZ", "PG", "FJ", "SB", "VU", "TO", "WS", "TV", "KI", "NR",
    # Caribbean / Atlantic
    "JM", "BS", "BB", "TT", "GY", "SR", "BM", "KY", "DM", "GD", "LC", "VC",
    "KN", "AG", "MS", "VG", "AI", "TC",
}


# ---------------------------------------------------------------------------
# Sign style. Slide 3: yellow = MUTCD, red/blue = European-style, green =
# Chinese style, "Other" = bespoke.
# Default for unlisted = "European" (the global majority).
# ---------------------------------------------------------------------------
SIGN_STYLE_OVERRIDES = {
    # MUTCD (yellow diamond warnings, "STOP" in English-speaking contexts)
    "US": "MUTCD", "CA": "MUTCD", "MX": "MUTCD",
    "BZ": "MUTCD", "GT": "MUTCD", "HN": "MUTCD", "SV": "MUTCD", "NI": "MUTCD",
    "CR": "MUTCD", "PA": "MUTCD",
    "CO": "MUTCD", "VE": "MUTCD", "EC": "MUTCD", "PE": "MUTCD", "BO": "MUTCD",
    "AR": "MUTCD", "PY": "MUTCD", "UY": "MUTCD", "CL": "MUTCD",
    "AU": "MUTCD", "NZ": "MUTCD",
    "ID": "MUTCD", "PH": "MUTCD", "TH": "MUTCD", "MY": "MUTCD", "SG": "MUTCD",
    "BN": "MUTCD", "JP": "MUTCD", "KR": "MUTCD",
    "IN": "MUTCD", "PK": "MUTCD", "BD": "MUTCD", "LK": "MUTCD", "BT": "MUTCD",
    "ZA": "MUTCD", "BW": "MUTCD", "ZW": "MUTCD", "NA": "MUTCD",
    "GY": "MUTCD", "SR": "MUTCD",
    # Chinese style (green-tinted variant in slide 3)
    "CN": "Chinese", "TW": "Chinese", "MO": "Chinese", "HK": "Chinese",
    # Everything else defaults to European
}

# Corrections for countries where slide pixel-sampling got the wrong colour.
# These take highest priority, overriding both SLIDE_SIGN and the fallback
# overrides above.
SIGN_STYLE_CORRECTIONS = {
    "KR": "MUTCD",    # sampled as "Other"; KR uses MUTCD-style diamond warning signs
    "TW": "Chinese",  # sampled as "Other"; TW uses Chinese-style signs
}


# ---------------------------------------------------------------------------
# Stop sign text. Slide 4 + Wikipedia "Stop sign".
# Most of the world uses English "STOP". Listed below are the exceptions.
# ---------------------------------------------------------------------------
STOP_TEXT_OVERRIDES = {
    # ---------- Latin script: distinctive non-English words ----------
    # Spanish-speaking — split between ALTO (Mexico + Central America) and
    # PARE (most of South America + Caribbean Spanish-speaking).
    "MX": "ALTO", "GT": "ALTO", "HN": "ALTO", "SV": "ALTO", "NI": "ALTO",
    "CR": "ALTO", "PA": "ALTO",
    "DO": "PARE", "CU": "PARE", "PR": "PARE",
    "BR": "PARE", "AR": "PARE", "UY": "PARE", "PY": "PARE", "CL": "PARE",
    "CO": "PARE", "PE": "PARE", "BO": "PARE", "EC": "PARE", "VE": "PARE",
    # Turkic — DUR
    "TR": "DUR", "TM": "DUR", "AZ": "DAYAN",
    # French (Quebec uses ARRÊT but Canada-wide is STOP — leave Canada as STOP)
    "MG": "ARRÊT",
    # Malay
    "MY": "BERHENTI", "BN": "BERHENTI",
    # Filipino — TIGIL appears on some signs but STOP dominates; leave as STOP

    # ---------- Cyrillic ----------
    "RU": "СТОП", "BY": "СТОП", "UA": "СТОП", "BG": "СТОП",
    "MK": "СТОП", "RS": "СТОП / STOP", "ME": "СТОП / STOP",
    "MN": "ЗОГС",
    "KZ": "ТОҚТА", "KG": "ТОКТО", "TJ": "ИСТ",

    # ---------- Caucasian scripts ----------
    "AM": "ԿԱՆԳ",
    "GE": "გაჩერდი",

    # ---------- Arabic script ----------
    # Arabian Peninsula + Levant + Iraq + Egypt + Sudan/Libya — single-Arabic
    "SA": "قف", "AE": "قف", "QA": "قف", "OM": "قف", "JO": "قف",
    "EG": "قف", "IQ": "قف", "YE": "قف", "LB": "قف", "SY": "قف", "PS": "قف",
    "KW": "قف", "BH": "قف", "LY": "قف", "SD": "قف",
    # North Africa (Maghreb) — bilingual French/Arabic
    "TN": "STOP / قف", "MA": "STOP / قف", "DZ": "STOP / قف", "MR": "قف",
    # Persian / Urdu (Arabic-derived scripts)
    "IR": "ایست",
    "AF": "STOP / توقف",  # Pashto "توقف" alongside English

    # ---------- CJK ----------
    "JP": "止まれ",
    "CN": "停", "TW": "停", "HK": "停", "MO": "停",
    "KR": "정지", "KP": "정지",

    # ---------- Other Asian scripts ----------
    "TH": "หยุด",
    "VN": "DỪNG LẠI",
    "KH": "ឈប់",
    "LA": "ຢຸດ",
    "MM": "ရပ်",
    "BD": "থামুন",       # Bengali "stop"
    "PK": "روكنا",       # Urdu "stop"
    "LK": "STOP",        # Sri Lanka officially uses STOP in English
    "NP": "रोक्नुहोस्",  # Devanagari (some signs)

    # ---------- Hebrew & Greek ----------
    "IL": "עצור",
    "GR": "STOP",        # Greek signs use English STOP almost universally

    # ---------- Other Africa ----------
    "ET": "ቁም",         # Amharic
    "ER": "ደው በል",     # Tigrinya — alongside English

    # All other countries default to "STOP" (English).
}


# ---------------------------------------------------------------------------
# Plate format. Slide 6 (US states), slide 7 (Canadian provinces). Most of the
# rest of the world is "front+rear". Listed exceptions are countries / regions
# that use rear-only on most vehicles.
# ---------------------------------------------------------------------------
PLATE_FORMAT_OVERRIDES = {
    # Sub-national variation — flagged so the UI can mention "varies by state"
    "US": "varies",
    "CA": "varies",
    "AU": "varies",
    # Rear-only countries. Mostly former British colonies in the Caribbean
    # plus a few Asian / African outliers. Cross-checked against Wikipedia
    # "Vehicle registration plates of <country>" articles.
    "BS": "rear_only", "BM": "rear_only", "JM": "rear_only",
    "KY": "rear_only", "TT": "rear_only", "BB": "rear_only",
    "BZ": "rear_only", "GD": "rear_only", "VC": "rear_only",
    "LC": "rear_only", "DM": "rear_only", "AG": "rear_only", "KN": "rear_only",
    "VG": "rear_only", "AI": "rear_only", "MS": "rear_only", "TC": "rear_only",
    "GY": "rear_only", "SR": "rear_only",
    # Most of Asia/Europe/Africa: front+rear (default).
}


# US state-level plate (for sub-national look-up). Slide 6.
US_STATE_PLATE = {
    # Rear-only (19 states + DC)
    "Alabama": "rear_only", "Arizona": "rear_only", "Arkansas": "rear_only",
    "Delaware": "rear_only", "Florida": "rear_only", "Georgia": "rear_only",
    "Indiana": "rear_only", "Kansas": "rear_only", "Kentucky": "rear_only",
    "Louisiana": "rear_only", "Michigan": "rear_only", "Mississippi": "rear_only",
    "New Mexico": "rear_only", "North Carolina": "rear_only", "Oklahoma": "rear_only",
    "Pennsylvania": "rear_only", "South Carolina": "rear_only",
    "Tennessee": "rear_only", "West Virginia": "rear_only",
    # Front+rear (30 states; everyone else)
}
US_FRONT_REAR = [
    "Alaska", "California", "Colorado", "Connecticut", "Hawaii", "Idaho",
    "Illinois", "Iowa", "Maine", "Maryland", "Massachusetts", "Minnesota",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New York", "North Dakota", "Ohio", "Oregon", "Rhode Island",
    "South Dakota", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "Wisconsin", "Wyoming", "District of Columbia",
]
for _s in US_FRONT_REAR:
    US_STATE_PLATE[_s] = "front+rear"


CA_PROV_PLATE = {
    # Rear-only (9 of 13 provinces/territories)
    "Alberta": "rear_only", "British Columbia": "rear_only",
    "New Brunswick": "rear_only", "Newfoundland and Labrador": "rear_only",
    "Nova Scotia": "rear_only", "Prince Edward Island": "rear_only",
    "Quebec": "rear_only", "Saskatchewan": "rear_only", "Yukon": "rear_only",
    # Front+rear (4)
    "Manitoba": "front+rear", "Northwest Territories": "front+rear",
    "Nunavut": "front+rear", "Ontario": "front+rear",
}


# ---------------------------------------------------------------------------
# Highway speed limit (max typical, kmh). Slide 10 + Wikipedia.
# ---------------------------------------------------------------------------
SPEED_LIMIT_KMH = {
    "AE": 140, "AR": 130, "AT": 130, "AU": 110, "BE": 120, "BG": 140,
    "BH": 120, "BO": 100, "BR": 110, "BY": 110, "CA": 110, "CH": 120,
    "CL": 120, "CN": 120, "CO": 100, "CR": 110, "CY": 100, "CZ": 130,
    "DE": 999, "DK": 130, "DO": 120, "EC": 100, "EE": 110, "EG": 100,
    "ES": 120, "FI": 120, "FR": 130, "GB": 113, "GE": 110, "GR": 130,
    "HK": 110, "HR": 130, "HU": 130, "ID": 100, "IE": 120, "IL": 120,
    "IN": 120, "IR": 120, "IS": 90, "IT": 130, "JO": 120, "JP": 100,
    "KE": 110, "KH": 100, "KR": 110, "KW": 120, "LA": 100, "LB": 100,
    "LI": 80, "LK": 100, "LT": 130, "LU": 130, "LV": 110, "MA": 120,
    "MC": 50, "MD": 90, "ME": 130, "MK": 130, "MN": 80, "MT": 80,
    "MX": 110, "MY": 110, "NG": 100, "NL": 100, "NO": 110, "NP": 80,
    "NZ": 110, "OM": 120, "PA": 100, "PE": 100, "PH": 100, "PK": 120,
    "PL": 140, "PT": 120, "PY": 110, "QA": 120, "RO": 130, "RS": 130,
    "RU": 130, "SA": 120, "SE": 120, "SG": 90, "SI": 130, "SK": 130,
    "SM": 70, "TH": 120, "TN": 110, "TR": 140, "TW": 110, "UA": 130,
    # US: 120 km/h (75 mph) is the most-common state max. 137 (85 mph)
    # exists only on a single Texas section — not what's typically posted.
    "UG": 100, "US": 120, "UY": 110, "UZ": 110, "VE": 100, "VN": 120,
    "ZA": 120, "ZW": 120,
    # Smaller territories / dependencies — fall through to "—" if missing
    "AD": 100, "GI": 50, "BM": 56, "FO": 80,
    "AS": 56, "BS": 100, "BB": 80, "BT": 80, "BW": 120, "CW": 80,
    "DM": 64, "JM": 110, "KY": 80, "MQ": 110, "GP": 110, "GF": 110,
    "RE": 110, "PR": 105, "PS": 100, "VG": 80,
    "JE": 64, "GG": 56, "IM": 96, "GL": 80, "FK": 64, "MS": 64,
    "AL": 110, "AM": 110, "AZ": 110, "AW": 80,
    "GT": 100, "HN": 90, "SV": 90, "NI": 100,
    "ET": 100, "GH": 100, "SN": 100, "TZ": 100,
    "AF": 80, "AO": 100, "DJ": 80, "ER": 80, "GW": 80, "GQ": 80,
    "GD": 64, "TT": 100, "VC": 64, "AG": 64, "AI": 64, "KN": 64, "LC": 64,
    "MM": 100, "MV": 80,
    "BJ": 100, "BF": 100, "CI": 100, "CD": 80, "CG": 100, "CM": 110,
    "CV": 100, "GA": 100, "ML": 100, "MR": 100, "NE": 100, "NF": 80,
    "RW": 100, "SC": 80, "SO": 80, "SS": 100, "ST": 80, "TG": 100,
    "TJ": 110, "TM": 110,
    # Filled-in gaps
    "KG": 110, "LS": 120, "MG": 90, "SJ": 80, "SZ": 120, "YT": 110,
    "CN": 120, "HK": 110, "MO": 80, "EG": 100, "IQ": 120, "NP": 80,
    "TZ": 110, "RW": 100, "ML": 100, "NA": 120, "VU": 50, "FK": 64,
    "JM": 110, "TT": 100, "BS": 100, "BB": 80, "KY": 80, "MU": 110,
    "AS": 56, "FM": 50, "PW": 50, "MH": 50, "WS": 70, "KI": 80,
    "TV": 50, "TO": 80, "VU": 50, "FJ": 100, "SB": 50, "PG": 80,
    "BO": 100, "BS": 100, "BZ": 88, "GY": 80, "SR": 90,
}

# ---------------------------------------------------------------------------
# Road line colour scheme (slide 9). Most of the world uses "middle white,
# outer white". Notable exceptions: yellow-centred (Americas, JP, CN, KR,
# parts of MENA), white centred + yellow outer.
# ---------------------------------------------------------------------------
ROAD_LINES_OVERRIDES = {
    # Middle yellow, outer white
    "US": "yellow_center_white_edge",
    "CA": "yellow_center_white_edge",
    "MX": "yellow_center_white_edge",
    "GT": "yellow_center_white_edge", "HN": "yellow_center_white_edge",
    "SV": "yellow_center_white_edge", "NI": "yellow_center_white_edge",
    "CR": "yellow_center_white_edge", "PA": "yellow_center_white_edge",
    "BZ": "yellow_center_white_edge",
    "JP": "yellow_center_white_edge", "KR": "yellow_center_white_edge",
    "TW": "yellow_center_white_edge", "CN": "yellow_center_white_edge",
    "VN": "yellow_center_white_edge",
    # Middle yellow OR white, outer white
    "BR": "yellow_or_white_center_white_edge",
    "AR": "yellow_or_white_center_white_edge",
    "PY": "yellow_or_white_center_white_edge",
    "UY": "yellow_or_white_center_white_edge",
    # Middle white, outer yellow (notable: South Africa, parts of MENA)
    "ZA": "white_center_yellow_edge",
    "BW": "white_center_yellow_edge", "NA": "white_center_yellow_edge",
    "ZW": "white_center_yellow_edge",
    "IL": "white_center_yellow_edge", "PS": "white_center_yellow_edge",
    "JO": "white_center_yellow_edge", "AE": "white_center_yellow_edge",
    # Default (unset) = "white_center_white_edge"
}

ROAD_LINES_CORRECTIONS = {
    "KR": "yellow_center_white_edge",  # sampled as white_center; KR uses yellow center lines
}


# ---------------------------------------------------------------------------
# European-only: chevron colour scheme on warning curves (slide 5) and number
# of stripes on the pedestrian-crossing sign (slide 8).
# ---------------------------------------------------------------------------
CHEVRON_COLOR = {
    # Yellow + black — Nordics, British Isles + LHD-via-British colonies
    "NO": "yellow_black", "SE": "yellow_black", "FI": "yellow_black",
    "IS": "yellow_black", "IE": "yellow_black", "GB": "yellow_black",
    "FO": "yellow_black", "GI": "yellow_black", "MT": "yellow_black",
    "CY": "yellow_black", "JE": "yellow_black", "GG": "yellow_black",
    "IM": "yellow_black", "SJ": "yellow_black",
    # Blue + yellow
    "FR": "blue_yellow", "ES": "blue_yellow", "PT": "blue_yellow",
    "BE": "blue_yellow", "LU": "blue_yellow",
    # Red + white
    "DE": "red_white", "AT": "red_white", "CH": "red_white", "IT": "red_white",
    "PL": "red_white", "CZ": "red_white", "SK": "red_white", "HU": "red_white",
    "RO": "red_white", "BG": "red_white", "GR": "red_white", "TR": "red_white",
    "RU": "red_white", "UA": "red_white", "BY": "red_white",
    "HR": "red_white", "RS": "red_white", "BA": "red_white", "SI": "red_white",
    "ME": "red_white", "MK": "red_white", "AL": "red_white", "XK": "red_white",
    "EE": "red_white", "LV": "red_white", "LT": "red_white",
    "MD": "red_white", "LI": "red_white", "SM": "red_white",
    "MC": "blue_yellow", "AD": "blue_yellow",
    # Black + white
    "DK": "black_white", "NL": "black_white",
}


PED_STRIPES = {
    "ES": 8, "AD": 8,
    "CH": 7,
    "FR": 5, "BE": 5, "DE": 5, "AT": 5, "CZ": 5, "SK": 5,
    "HU": 5, "RO": 5, "BG": 5, "RS": 5, "HR": 5, "SI": 5,
    "IT": 5, "PT": 5, "NL": 5, "DK": 5, "LU": 5, "MC": 5, "SM": 5,
    "BA": 5, "ME": 5, "MK": 5, "AL": 5, "MD": 5,
    "NO": 4, "SE": 4, "FI": 4,
    "EE": 4, "LV": 4, "LT": 4,
    "RU": 3, "BY": 3, "UA": 3,
    "GR": 2, "TR": 2,
    "PL": 1,
    # Filled-in EU territories
    "CY": 5, "MT": 5, "LI": 5, "FO": 4, "SJ": 4,
    # UK, IE, Channel Islands, Isle of Man, Gibraltar: yellow zigzag, no
    # Vienna-style ped sign — leave as null.
}


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def load_wikipedia() -> dict:
    if WIKI_FACTS.exists():
        return json.loads(WIKI_FACTS.read_text(encoding="utf-8"))
    return {}


def load_slide_facts() -> dict:
    if SLIDE_FACTS.exists():
        return json.loads(SLIDE_FACTS.read_text(encoding="utf-8"))
    return {}


WIKI = load_wikipedia()
SLIDE = load_slide_facts()
WIKI_DRIVING = WIKI.get("driving_side", {})
WIKI_SPEED = WIKI.get("speed_limit_max_kmh", {})
SLIDE_SIGN = SLIDE.get("sign_style", {})
SLIDE_LINES = SLIDE.get("road_lines", {})


def driving_side(iso2: str) -> str:
    if iso2 in WIKI_DRIVING:
        return WIKI_DRIVING[iso2]
    return "left" if iso2 in LEFT_HAND else "right"


def sign_style(iso2: str) -> str:
    if iso2 in SIGN_STYLE_CORRECTIONS:
        return SIGN_STYLE_CORRECTIONS[iso2]
    if iso2 in SLIDE_SIGN:
        return SLIDE_SIGN[iso2]
    return SIGN_STYLE_OVERRIDES.get(iso2, "European")


def road_lines(iso2: str) -> str:
    if iso2 in ROAD_LINES_CORRECTIONS:
        return ROAD_LINES_CORRECTIONS[iso2]
    if iso2 in SLIDE_LINES:
        return SLIDE_LINES[iso2]
    return ROAD_LINES_OVERRIDES.get(iso2, "white_center_white_edge")


def stop_text(iso2: str) -> str:
    return STOP_TEXT_OVERRIDES.get(iso2, "STOP")


def plate_format(iso2: str) -> str:
    return PLATE_FORMAT_OVERRIDES.get(iso2, "front+rear")


def fact_for(iso2: str) -> dict:
    # Wikipedia stores absolute-maximum posted speed (e.g. 85 mph in one
    # Texas section for US). For GeoGuessr study purposes, the most-common
    # state-level max is more useful — those overrides win for specific cases.
    SPEED_OVERRIDES_OVER_WIKI = {"US": 120, "AU": 110}
    out = {
        "driving_side": driving_side(iso2),
        "sign_style": sign_style(iso2),
        "stop_text": stop_text(iso2),
        "plate_format": plate_format(iso2),
        "speed_limit_max_kmh": SPEED_OVERRIDES_OVER_WIKI.get(iso2) or WIKI_SPEED.get(iso2) or SPEED_LIMIT_KMH.get(iso2),
        "road_lines": road_lines(iso2),
        "chevron_color": CHEVRON_COLOR.get(iso2),
        "ped_stripes": PED_STRIPES.get(iso2),
    }
    if iso2 == "US":
        out["plate_subnational"] = US_STATE_PLATE
    if iso2 == "CA":
        out["plate_subnational"] = CA_PROV_PLATE
    return out


def main() -> None:
    iso2_codes = parse_iso2_codes()
    out: dict = {
        "_meta": {
            "version": "0.8.0",
            "source": "10 Useful Maps deck + Wikipedia (driving side, plates, signs, stop signs, road lines, speed limits, chevron colour, ped-sign stripes)",
            "fields": [
                "driving_side", "sign_style", "stop_text", "plate_format",
                "speed_limit_max_kmh", "road_lines", "chevron_color",
                "ped_stripes",
            ],
        },
    }
    for iso2 in iso2_codes:
        out[iso2] = fact_for(iso2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(iso2_codes)} countries)")


if __name__ == "__main__":
    main()
