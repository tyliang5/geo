# -*- coding: utf-8 -*-
"""Build extension/data/meta_extras.json — additional categorical metas not
covered by country_facts.json or country_reference.json. Useful for richer
focus-quiz topics.

Includes:
  - vehicle_oval: UN distinguishing sign codes (oval stickers / plate codes)
  - mailbox_color: distinctive mailbox / postbox colours
  - police_car_color: dominant police vehicle livery colour scheme
  - phone_format: common written phone-number format

Sourced from Wikipedia "International vehicle registration code" article and
GeoGuessr meta lists. Hand-typed for the ~140 countries we cover.
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / 'extension' / 'data' / 'meta_extras.json'

# UN distinguishing sign (oval sticker / plate code). Mostly historic but
# still very identifying for older European cars in GG.
VEHICLE_OVAL = {
    'AD': 'AND', 'AE': 'UAE', 'AL': 'AL',  'AM': 'AM',  'AR': 'RA',
    'AT': 'A',   'AU': 'AUS', 'AZ': 'AZ',  'BA': 'BIH', 'BB': 'BDS',
    'BD': 'BD',  'BE': 'B',   'BG': 'BG',  'BO': 'BOL', 'BR': 'BR',
    'BS': 'BS',  'BT': 'BHT', 'BW': 'BW',  'BY': 'BY',  'BZ': 'BH',
    'CA': 'CDN', 'CH': 'CH',  'CL': 'RCH', 'CN': 'RC',  'CO': 'CO',
    'CR': 'CR',  'CU': 'CU',  'CY': 'CY',  'CZ': 'CZ',  'DE': 'D',
    'DK': 'DK',  'DO': 'DOM', 'EC': 'EC',  'EE': 'EST', 'EG': 'ET',
    'ES': 'E',   'FI': 'FIN', 'FK': 'FK',  'FO': 'FO',  'FR': 'F',
    'GB': 'UK',  'GE': 'GE',  'GH': 'GH',  'GI': 'GBZ', 'GR': 'GR',
    'GT': 'GCA', 'GY': 'GUY', 'HK': 'HK',  'HR': 'HR',  'HU': 'H',
    'ID': 'RI',  'IE': 'IRL', 'IL': 'IL',  'IM': 'GBM', 'IN': 'IND',
    'IQ': 'IRQ', 'IR': 'IR',  'IS': 'IS',  'IT': 'I',   'JE': 'GBJ',
    'JM': 'JA',  'JO': 'JOR', 'JP': 'J',   'KE': 'EAK', 'KG': 'KS',
    'KH': 'K',   'KP': 'KP',  'KR': 'ROK', 'KW': 'KWT', 'KZ': 'KZ',
    'LA': 'LAO', 'LB': 'RL',  'LI': 'FL',  'LK': 'CL',  'LT': 'LT',
    'LU': 'L',   'LV': 'LV',  'MA': 'MA',  'MC': 'MC',  'MD': 'MD',
    'ME': 'MNE', 'MG': 'RM',  'MK': 'NMK', 'ML': 'RMM', 'MN': 'MGL',
    'MO': 'MO',  'MQ': 'F',   'MT': 'M',   'MU': 'MS',  'MX': 'MEX',
    'MY': 'MAL', 'NA': 'NAM', 'NG': 'WAN', 'NL': 'NL',  'NO': 'N',
    'NP': 'NEP', 'NZ': 'NZ',  'OM': 'OM',  'PA': 'PA',  'PE': 'PE',
    'PH': 'RP',  'PK': 'PK',  'PL': 'PL',  'PT': 'P',   'PY': 'PY',
    'QA': 'Q',   'RO': 'RO',  'RS': 'SRB', 'RU': 'RUS', 'RW': 'RWA',
    'SA': 'KSA', 'SE': 'S',   'SG': 'SGP', 'SI': 'SLO', 'SK': 'SK',
    'SM': 'RSM', 'SN': 'SN',  'SR': 'SME', 'SZ': 'SD',  'TH': 'T',
    'TN': 'TN',  'TR': 'TR',  'TT': 'TT',  'TW': 'RC',  'TZ': 'EAT',
    'UA': 'UA',  'UG': 'EAU', 'US': 'USA', 'UY': 'ROU', 'VN': 'VN',
    'VU': 'VAN', 'YT': 'F',   'ZA': 'ZA',  'ZW': 'ZW',
}

# Mailbox / postbox dominant colour. Major GG meta — colour alone narrows.
MAILBOX_COLOR = {
    # Red
    'GB': 'red', 'IE': 'green', 'JE': 'red', 'GG': 'red', 'IM': 'red',
    'GI': 'red', 'MT': 'red',
    'CH': 'yellow', 'DE': 'yellow', 'AT': 'yellow', 'LU': 'yellow',
    'FR': 'yellow', 'GR': 'yellow', 'CY': 'yellow', 'BE': 'red',
    'NL': 'orange',
    'IT': 'red', 'ES': 'yellow', 'PT': 'red',
    'NO': 'red', 'SE': 'yellow', 'FI': 'orange', 'DK': 'red',
    'IS': 'red', 'FO': 'red',
    'PL': 'red', 'CZ': 'orange', 'SK': 'orange', 'HU': 'red',
    'RO': 'yellow', 'BG': 'red',
    'EE': 'orange', 'LV': 'yellow', 'LT': 'yellow',
    'RU': 'blue', 'BY': 'red', 'UA': 'yellow',
    'TR': 'yellow',
    'JP': 'red', 'KR': 'red', 'CN': 'green', 'TW': 'green', 'HK': 'green',
    'IN': 'red', 'PK': 'red', 'BD': 'red', 'LK': 'red', 'NP': 'red',
    'TH': 'red', 'VN': 'yellow', 'MY': 'red', 'SG': 'red',
    'PH': 'red', 'ID': 'orange',
    'AU': 'red', 'NZ': 'red', 'FJ': 'red', 'PG': 'red',
    'US': 'blue', 'CA': 'red', 'MX': 'red',
    'BR': 'yellow', 'AR': 'blue', 'CL': 'orange', 'CO': 'yellow',
    'PE': 'yellow', 'UY': 'orange', 'PY': 'orange',
    'EG': 'red', 'MA': 'yellow', 'TN': 'yellow', 'DZ': 'yellow',
    'ZA': 'red', 'KE': 'red', 'NG': 'red', 'GH': 'red',
    'IL': 'red', 'JO': 'yellow', 'SA': 'green', 'AE': 'red',
}

# Police car dominant livery colour. Very identifying.
POLICE_COLOR = {
    'US': 'black_white', 'CA': 'white', 'MX': 'white_blue',
    'GB': 'silver_yellow', 'IE': 'blue_yellow', 'FR': 'blue_white',
    'DE': 'blue_silver', 'NL': 'red_blue_yellow', 'BE': 'blue_yellow',
    'CH': 'silver', 'AT': 'silver_red', 'IT': 'blue_white',
    'ES': 'blue_white', 'PT': 'blue_white',
    'NO': 'white_blue', 'SE': 'blue_yellow', 'DK': 'white_blue',
    'FI': 'blue_white', 'IS': 'white_blue',
    'PL': 'silver_blue', 'CZ': 'silver_yellow_blue', 'SK': 'silver',
    'HU': 'blue_silver', 'RO': 'silver_yellow',
    'EE': 'blue_white', 'LV': 'silver_blue', 'LT': 'silver_blue',
    'RU': 'white_blue', 'UA': 'blue_yellow',
    'TR': 'blue_white',
    'JP': 'black_white', 'KR': 'silver_blue', 'CN': 'white_blue',
    'TW': 'white', 'HK': 'silver_blue',
    'IN': 'white_blue', 'PK': 'white_red',
    'TH': 'red_white', 'VN': 'white_blue',
    'AU': 'white_blue', 'NZ': 'white',
    'BR': 'white_blue', 'AR': 'white_blue', 'CL': 'green_white',
    'EG': 'black_white', 'MA': 'white_blue', 'ZA': 'white_blue',
    'IL': 'white_blue',
}

# Common written phone-number format. Useful for spotting on signs / business.
PHONE_FORMAT = {
    'US': '(XXX) XXX-XXXX', 'CA': '(XXX) XXX-XXXX',
    'GB': '0XXXX XXXXXX',
    'FR': 'XX XX XX XX XX', 'DE': '+49 XXXX XXXXX',
    'IT': 'XXX XXX XXXX',  'ES': 'XXX XX XX XX',
    'PT': 'XXX XXX XXX',   'NL': '0XX XXX XX XX',
    'BE': '04XX XX XX XX', 'CH': '0XX XXX XX XX',
    'AT': '0XXX XXX XXXX', 'PL': 'XXX XXX XXX',
    'CZ': 'XXX XXX XXX',   'SK': '0XXX XXX XXX',
    'HU': '+36 XX XXX XXXX', 'RO': '07XX XXX XXX',
    'BG': '+359 XX XXX XXXX',
    'GR': '210 XXX XXXX',  'TR': '+90 XXX XXX XX XX',
    'RU': '+7 XXX XXX-XX-XX', 'UA': '+380 XX XXX XX XX',
    'JP': '0X-XXXX-XXXX',  'KR': '0XX-XXXX-XXXX',
    'CN': '+86 XXX XXXX XXXX', 'TW': '0X XXXX XXXX',
    'IN': '+91 XXXXX XXXXX', 'PK': '+92 XXX XXXXXXX',
    'AU': '04XX XXX XXX',  'NZ': '02X XXX XXXX',
    'BR': '(XX) XXXXX-XXXX', 'AR': '+54 9 XX XXXX XXXX',
    'MX': '+52 XXX XXX XXXX',
    'ZA': '0XX XXX XXXX',  'EG': '+20 XXX XXX XXXX',
}


def main() -> None:
    out = {
        '_meta': {
            'source': 'Wikipedia "International vehicle registration code" + GeoGuessr meta lists',
            'fields': ['vehicle_oval', 'mailbox_color', 'police_color', 'phone_format'],
        },
    }
    all_iso2 = set(VEHICLE_OVAL) | set(MAILBOX_COLOR) | set(POLICE_COLOR) | set(PHONE_FORMAT)
    for iso2 in sorted(all_iso2):
        out[iso2] = {
            'vehicle_oval': VEHICLE_OVAL.get(iso2),
            'mailbox_color': MAILBOX_COLOR.get(iso2),
            'police_color': POLICE_COLOR.get(iso2),
            'phone_format': PHONE_FORMAT.get(iso2),
        }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {OUT.name} — {len(all_iso2)} countries')


if __name__ == '__main__':
    main()
