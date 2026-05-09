# -*- coding: utf-8 -*-
"""Build extension/data/country_reference.json — comprehensive per-country
data for meta-focused quiz topics: ISO codes, calling codes, TLDs, currency,
official languages, scripts, capitals.

Sourced from the standard ISO references (3166-1, 4217, 639) and well-known
e.164 calling codes. Hand-typed and cross-checked against Wikipedia for the
~120 countries already in country-slugs.js.

Run:
    python scraper/build_country_reference.py
"""
from __future__ import annotations
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SLUGS_JS = REPO / 'extension' / 'src' / 'data' / 'country-slugs.js'
OUT = REPO / 'extension' / 'data' / 'country_reference.json'

# (iso2, iso3, calling_code, tld, currency_code, currency_symbol, capital,
#  primary_language, scripts (set), official_languages (list))
# Scripts use codes: Latin, Cyrillic, Arabic, Hebrew, Greek, Devanagari,
# Bengali, Tamil, Sinhala, Thai, Lao, Myanmar, Khmer, Hangul, Han (CJK),
# Kana (Japanese), Tibetan, Armenian, Georgian, Amharic.
DATA = {
    'AD': ('AND', '+376', '.ad', 'EUR', '€', 'Andorra la Vella', 'Catalan', ['Latin'], ['Catalan']),
    'AE': ('ARE', '+971', '.ae', 'AED', 'د.إ', 'Abu Dhabi', 'Arabic', ['Arabic'], ['Arabic']),
    'AL': ('ALB', '+355', '.al', 'ALL', 'L', 'Tirana', 'Albanian', ['Latin'], ['Albanian']),
    'AM': ('ARM', '+374', '.am', 'AMD', '֏', 'Yerevan', 'Armenian', ['Armenian'], ['Armenian']),
    'AR': ('ARG', '+54', '.ar', 'ARS', '$', 'Buenos Aires', 'Spanish', ['Latin'], ['Spanish']),
    'AS': ('ASM', '+1-684', '.as', 'USD', '$', 'Pago Pago', 'Samoan', ['Latin'], ['English', 'Samoan']),
    'AT': ('AUT', '+43', '.at', 'EUR', '€', 'Vienna', 'German', ['Latin'], ['German']),
    'AU': ('AUS', '+61', '.au', 'AUD', '$', 'Canberra', 'English', ['Latin'], ['English']),
    'AW': ('ABW', '+297', '.aw', 'AWG', 'ƒ', 'Oranjestad', 'Dutch', ['Latin'], ['Dutch', 'Papiamento']),
    'AZ': ('AZE', '+994', '.az', 'AZN', '₼', 'Baku', 'Azerbaijani', ['Latin'], ['Azerbaijani']),
    'BD': ('BGD', '+880', '.bd', 'BDT', '৳', 'Dhaka', 'Bengali', ['Bengali'], ['Bengali']),
    'BE': ('BEL', '+32', '.be', 'EUR', '€', 'Brussels', 'Dutch', ['Latin'], ['Dutch', 'French', 'German']),
    'BG': ('BGR', '+359', '.bg', 'BGN', 'лв', 'Sofia', 'Bulgarian', ['Cyrillic'], ['Bulgarian']),
    'BM': ('BMU', '+1-441', '.bm', 'BMD', '$', 'Hamilton', 'English', ['Latin'], ['English']),
    'BO': ('BOL', '+591', '.bo', 'BOB', 'Bs', 'Sucre', 'Spanish', ['Latin'], ['Spanish', 'Quechua', 'Aymara']),
    'BR': ('BRA', '+55', '.br', 'BRL', 'R$', 'Brasília', 'Portuguese', ['Latin'], ['Portuguese']),
    'BT': ('BTN', '+975', '.bt', 'BTN', 'Nu', 'Thimphu', 'Dzongkha', ['Tibetan'], ['Dzongkha']),
    'BW': ('BWA', '+267', '.bw', 'BWP', 'P', 'Gaborone', 'English', ['Latin'], ['English', 'Tswana']),
    'BY': ('BLR', '+375', '.by', 'BYN', 'Br', 'Minsk', 'Belarusian', ['Cyrillic'], ['Belarusian', 'Russian']),
    'CA': ('CAN', '+1', '.ca', 'CAD', '$', 'Ottawa', 'English', ['Latin'], ['English', 'French']),
    'CH': ('CHE', '+41', '.ch', 'CHF', 'CHF', 'Bern', 'German', ['Latin'], ['German', 'French', 'Italian', 'Romansh']),
    'CL': ('CHL', '+56', '.cl', 'CLP', '$', 'Santiago', 'Spanish', ['Latin'], ['Spanish']),
    'CO': ('COL', '+57', '.co', 'COP', '$', 'Bogotá', 'Spanish', ['Latin'], ['Spanish']),
    'CR': ('CRI', '+506', '.cr', 'CRC', '₡', 'San José', 'Spanish', ['Latin'], ['Spanish']),
    'CW': ('CUW', '+599', '.cw', 'ANG', 'ƒ', 'Willemstad', 'Dutch', ['Latin'], ['Dutch', 'English', 'Papiamento']),
    'CY': ('CYP', '+357', '.cy', 'EUR', '€', 'Nicosia', 'Greek', ['Greek', 'Latin'], ['Greek', 'Turkish']),
    'CZ': ('CZE', '+420', '.cz', 'CZK', 'Kč', 'Prague', 'Czech', ['Latin'], ['Czech']),
    'DE': ('DEU', '+49', '.de', 'EUR', '€', 'Berlin', 'German', ['Latin'], ['German']),
    'DK': ('DNK', '+45', '.dk', 'DKK', 'kr', 'Copenhagen', 'Danish', ['Latin'], ['Danish']),
    'DO': ('DOM', '+1-809', '.do', 'DOP', 'RD$', 'Santo Domingo', 'Spanish', ['Latin'], ['Spanish']),
    'EC': ('ECU', '+593', '.ec', 'USD', '$', 'Quito', 'Spanish', ['Latin'], ['Spanish']),
    'EE': ('EST', '+372', '.ee', 'EUR', '€', 'Tallinn', 'Estonian', ['Latin'], ['Estonian']),
    'ES': ('ESP', '+34', '.es', 'EUR', '€', 'Madrid', 'Spanish', ['Latin'], ['Spanish', 'Catalan', 'Basque', 'Galician']),
    'FI': ('FIN', '+358', '.fi', 'EUR', '€', 'Helsinki', 'Finnish', ['Latin'], ['Finnish', 'Swedish']),
    'FK': ('FLK', '+500', '.fk', 'FKP', '£', 'Stanley', 'English', ['Latin'], ['English']),
    'FO': ('FRO', '+298', '.fo', 'DKK', 'kr', 'Tórshavn', 'Faroese', ['Latin'], ['Faroese', 'Danish']),
    'FR': ('FRA', '+33', '.fr', 'EUR', '€', 'Paris', 'French', ['Latin'], ['French']),
    'GB': ('GBR', '+44', '.uk', 'GBP', '£', 'London', 'English', ['Latin'], ['English']),
    'GE': ('GEO', '+995', '.ge', 'GEL', '₾', 'Tbilisi', 'Georgian', ['Georgian'], ['Georgian']),
    'GF': ('GUF', '+594', '.gf', 'EUR', '€', 'Cayenne', 'French', ['Latin'], ['French']),
    'GG': ('GGY', '+44-1481', '.gg', 'GBP', '£', 'St Peter Port', 'English', ['Latin'], ['English']),
    'GH': ('GHA', '+233', '.gh', 'GHS', '₵', 'Accra', 'English', ['Latin'], ['English']),
    'GI': ('GIB', '+350', '.gi', 'GIP', '£', 'Gibraltar', 'English', ['Latin'], ['English']),
    'GL': ('GRL', '+299', '.gl', 'DKK', 'kr', 'Nuuk', 'Greenlandic', ['Latin'], ['Greenlandic']),
    'GP': ('GLP', '+590', '.gp', 'EUR', '€', 'Basse-Terre', 'French', ['Latin'], ['French']),
    'GR': ('GRC', '+30', '.gr', 'EUR', '€', 'Athens', 'Greek', ['Greek'], ['Greek']),
    'GT': ('GTM', '+502', '.gt', 'GTQ', 'Q', 'Guatemala City', 'Spanish', ['Latin'], ['Spanish']),
    'HR': ('HRV', '+385', '.hr', 'EUR', '€', 'Zagreb', 'Croatian', ['Latin'], ['Croatian']),
    'HU': ('HUN', '+36', '.hu', 'HUF', 'Ft', 'Budapest', 'Hungarian', ['Latin'], ['Hungarian']),
    'ID': ('IDN', '+62', '.id', 'IDR', 'Rp', 'Jakarta', 'Indonesian', ['Latin'], ['Indonesian']),
    'IE': ('IRL', '+353', '.ie', 'EUR', '€', 'Dublin', 'English', ['Latin'], ['English', 'Irish']),
    'IL': ('ISR', '+972', '.il', 'ILS', '₪', 'Jerusalem', 'Hebrew', ['Hebrew'], ['Hebrew', 'Arabic']),
    'IM': ('IMN', '+44-1624', '.im', 'GBP', '£', 'Douglas', 'English', ['Latin'], ['English', 'Manx']),
    'IN': ('IND', '+91', '.in', 'INR', '₹', 'New Delhi', 'Hindi', ['Devanagari', 'Latin'], ['Hindi', 'English']),
    'IS': ('ISL', '+354', '.is', 'ISK', 'kr', 'Reykjavík', 'Icelandic', ['Latin'], ['Icelandic']),
    'IT': ('ITA', '+39', '.it', 'EUR', '€', 'Rome', 'Italian', ['Latin'], ['Italian']),
    'JE': ('JEY', '+44-1534', '.je', 'GBP', '£', 'Saint Helier', 'English', ['Latin'], ['English']),
    'JO': ('JOR', '+962', '.jo', 'JOD', 'د.أ', 'Amman', 'Arabic', ['Arabic'], ['Arabic']),
    'JP': ('JPN', '+81', '.jp', 'JPY', '¥', 'Tokyo', 'Japanese', ['Kana', 'Han'], ['Japanese']),
    'KE': ('KEN', '+254', '.ke', 'KES', 'KSh', 'Nairobi', 'Swahili', ['Latin'], ['Swahili', 'English']),
    'KG': ('KGZ', '+996', '.kg', 'KGS', 'с', 'Bishkek', 'Kyrgyz', ['Cyrillic'], ['Kyrgyz', 'Russian']),
    'KH': ('KHM', '+855', '.kh', 'KHR', '៛', 'Phnom Penh', 'Khmer', ['Khmer'], ['Khmer']),
    'KP': ('PRK', '+850', '.kp', 'KPW', '₩', 'Pyongyang', 'Korean', ['Hangul'], ['Korean']),
    'KR': ('KOR', '+82', '.kr', 'KRW', '₩', 'Seoul', 'Korean', ['Hangul'], ['Korean']),
    'KY': ('CYM', '+1-345', '.ky', 'KYD', '$', 'George Town', 'English', ['Latin'], ['English']),
    'KZ': ('KAZ', '+7', '.kz', 'KZT', '₸', 'Astana', 'Kazakh', ['Cyrillic', 'Latin'], ['Kazakh', 'Russian']),
    'LA': ('LAO', '+856', '.la', 'LAK', '₭', 'Vientiane', 'Lao', ['Lao'], ['Lao']),
    'LB': ('LBN', '+961', '.lb', 'LBP', 'ل.ل', 'Beirut', 'Arabic', ['Arabic'], ['Arabic']),
    'LI': ('LIE', '+423', '.li', 'CHF', 'CHF', 'Vaduz', 'German', ['Latin'], ['German']),
    'LK': ('LKA', '+94', '.lk', 'LKR', 'Rs', 'Colombo', 'Sinhala', ['Sinhala', 'Tamil'], ['Sinhala', 'Tamil']),
    'LS': ('LSO', '+266', '.ls', 'LSL', 'L', 'Maseru', 'Sesotho', ['Latin'], ['Sesotho', 'English']),
    'LT': ('LTU', '+370', '.lt', 'EUR', '€', 'Vilnius', 'Lithuanian', ['Latin'], ['Lithuanian']),
    'LU': ('LUX', '+352', '.lu', 'EUR', '€', 'Luxembourg City', 'Luxembourgish', ['Latin'], ['Luxembourgish', 'French', 'German']),
    'LV': ('LVA', '+371', '.lv', 'EUR', '€', 'Riga', 'Latvian', ['Latin'], ['Latvian']),
    'MA': ('MAR', '+212', '.ma', 'MAD', 'د.م.', 'Rabat', 'Arabic', ['Arabic'], ['Arabic', 'Berber']),
    'MC': ('MCO', '+377', '.mc', 'EUR', '€', 'Monaco', 'French', ['Latin'], ['French']),
    'ME': ('MNE', '+382', '.me', 'EUR', '€', 'Podgorica', 'Montenegrin', ['Latin', 'Cyrillic'], ['Montenegrin']),
    'MG': ('MDG', '+261', '.mg', 'MGA', 'Ar', 'Antananarivo', 'Malagasy', ['Latin'], ['Malagasy', 'French']),
    'MK': ('MKD', '+389', '.mk', 'MKD', 'ден', 'Skopje', 'Macedonian', ['Cyrillic'], ['Macedonian']),
    'MN': ('MNG', '+976', '.mn', 'MNT', '₮', 'Ulaanbaatar', 'Mongolian', ['Cyrillic'], ['Mongolian']),
    'MQ': ('MTQ', '+596', '.mq', 'EUR', '€', 'Fort-de-France', 'French', ['Latin'], ['French']),
    'MT': ('MLT', '+356', '.mt', 'EUR', '€', 'Valletta', 'Maltese', ['Latin'], ['Maltese', 'English']),
    'MX': ('MEX', '+52', '.mx', 'MXN', '$', 'Mexico City', 'Spanish', ['Latin'], ['Spanish']),
    'MY': ('MYS', '+60', '.my', 'MYR', 'RM', 'Kuala Lumpur', 'Malay', ['Latin'], ['Malay']),
    'NG': ('NGA', '+234', '.ng', 'NGN', '₦', 'Abuja', 'English', ['Latin'], ['English']),
    'NL': ('NLD', '+31', '.nl', 'EUR', '€', 'Amsterdam', 'Dutch', ['Latin'], ['Dutch']),
    'NO': ('NOR', '+47', '.no', 'NOK', 'kr', 'Oslo', 'Norwegian', ['Latin'], ['Norwegian']),
    'NZ': ('NZL', '+64', '.nz', 'NZD', '$', 'Wellington', 'English', ['Latin'], ['English', 'Maori']),
    'OM': ('OMN', '+968', '.om', 'OMR', 'ر.ع.', 'Muscat', 'Arabic', ['Arabic'], ['Arabic']),
    'PA': ('PAN', '+507', '.pa', 'PAB', 'B/.', 'Panama City', 'Spanish', ['Latin'], ['Spanish']),
    'PE': ('PER', '+51', '.pe', 'PEN', 'S/', 'Lima', 'Spanish', ['Latin'], ['Spanish', 'Quechua', 'Aymara']),
    'PH': ('PHL', '+63', '.ph', 'PHP', '₱', 'Manila', 'Filipino', ['Latin'], ['Filipino', 'English']),
    'PK': ('PAK', '+92', '.pk', 'PKR', 'Rs', 'Islamabad', 'Urdu', ['Arabic'], ['Urdu', 'English']),
    'PL': ('POL', '+48', '.pl', 'PLN', 'zł', 'Warsaw', 'Polish', ['Latin'], ['Polish']),
    'PR': ('PRI', '+1-787', '.pr', 'USD', '$', 'San Juan', 'Spanish', ['Latin'], ['Spanish', 'English']),
    'PS': ('PSE', '+970', '.ps', 'ILS', '₪', 'Ramallah', 'Arabic', ['Arabic'], ['Arabic']),
    'PT': ('PRT', '+351', '.pt', 'EUR', '€', 'Lisbon', 'Portuguese', ['Latin'], ['Portuguese']),
    'QA': ('QAT', '+974', '.qa', 'QAR', 'ر.ق', 'Doha', 'Arabic', ['Arabic'], ['Arabic']),
    'RE': ('REU', '+262', '.re', 'EUR', '€', 'Saint-Denis', 'French', ['Latin'], ['French']),
    'RO': ('ROU', '+40', '.ro', 'RON', 'lei', 'Bucharest', 'Romanian', ['Latin'], ['Romanian']),
    'RS': ('SRB', '+381', '.rs', 'RSD', 'дин', 'Belgrade', 'Serbian', ['Cyrillic', 'Latin'], ['Serbian']),
    'RU': ('RUS', '+7', '.ru', 'RUB', '₽', 'Moscow', 'Russian', ['Cyrillic'], ['Russian']),
    'SA': ('SAU', '+966', '.sa', 'SAR', 'ر.س', 'Riyadh', 'Arabic', ['Arabic'], ['Arabic']),
    'SE': ('SWE', '+46', '.se', 'SEK', 'kr', 'Stockholm', 'Swedish', ['Latin'], ['Swedish']),
    'SG': ('SGP', '+65', '.sg', 'SGD', '$', 'Singapore', 'English', ['Latin', 'Han', 'Tamil'], ['English', 'Mandarin', 'Malay', 'Tamil']),
    'SI': ('SVN', '+386', '.si', 'EUR', '€', 'Ljubljana', 'Slovenian', ['Latin'], ['Slovenian']),
    'SJ': ('SJM', '+47', '.sj', 'NOK', 'kr', 'Longyearbyen', 'Norwegian', ['Latin'], ['Norwegian']),
    'SK': ('SVK', '+421', '.sk', 'EUR', '€', 'Bratislava', 'Slovak', ['Latin'], ['Slovak']),
    'SM': ('SMR', '+378', '.sm', 'EUR', '€', 'San Marino', 'Italian', ['Latin'], ['Italian']),
    'SN': ('SEN', '+221', '.sn', 'XOF', 'CFA', 'Dakar', 'French', ['Latin'], ['French', 'Wolof']),
    'SZ': ('SWZ', '+268', '.sz', 'SZL', 'L', 'Mbabane', 'Swazi', ['Latin'], ['Swazi', 'English']),
    'TH': ('THA', '+66', '.th', 'THB', '฿', 'Bangkok', 'Thai', ['Thai'], ['Thai']),
    'TN': ('TUN', '+216', '.tn', 'TND', 'د.ت', 'Tunis', 'Arabic', ['Arabic'], ['Arabic']),
    'TR': ('TUR', '+90', '.tr', 'TRY', '₺', 'Ankara', 'Turkish', ['Latin'], ['Turkish']),
    'TW': ('TWN', '+886', '.tw', 'TWD', 'NT$', 'Taipei', 'Mandarin', ['Han'], ['Mandarin']),
    'UA': ('UKR', '+380', '.ua', 'UAH', '₴', 'Kyiv', 'Ukrainian', ['Cyrillic'], ['Ukrainian']),
    'UG': ('UGA', '+256', '.ug', 'UGX', 'USh', 'Kampala', 'English', ['Latin'], ['English', 'Swahili']),
    'US': ('USA', '+1', '.us', 'USD', '$', 'Washington', 'English', ['Latin'], ['English']),
    'UY': ('URY', '+598', '.uy', 'UYU', '$U', 'Montevideo', 'Spanish', ['Latin'], ['Spanish']),
    'VN': ('VNM', '+84', '.vn', 'VND', '₫', 'Hanoi', 'Vietnamese', ['Latin'], ['Vietnamese']),
    'YT': ('MYT', '+262', '.yt', 'EUR', '€', 'Mamoudzou', 'French', ['Latin'], ['French']),
    'ZA': ('ZAF', '+27', '.za', 'ZAR', 'R', 'Pretoria', 'Afrikaans', ['Latin'], ['Afrikaans', 'English', 'Zulu', 'Xhosa']),
    'ZW': ('ZWE', '+263', '.zw', 'ZWL', '$', 'Harare', 'English', ['Latin'], ['English', 'Shona', 'Ndebele']),
    # Caribbean — most former British, all rear-only plates
    'BB': ('BRB', '+1-246', '.bb', 'BBD', '$', 'Bridgetown', 'English', ['Latin'], ['English']),
    'BS': ('BHS', '+1-242', '.bs', 'BSD', '$', 'Nassau', 'English', ['Latin'], ['English']),
    'BZ': ('BLZ', '+501', '.bz', 'BZD', '$', 'Belmopan', 'English', ['Latin'], ['English']),
    'JM': ('JAM', '+1-876', '.jm', 'JMD', '$', 'Kingston', 'English', ['Latin'], ['English']),
    'TT': ('TTO', '+1-868', '.tt', 'TTD', '$', 'Port of Spain', 'English', ['Latin'], ['English']),
    'GY': ('GUY', '+592', '.gy', 'GYD', '$', 'Georgetown', 'English', ['Latin'], ['English']),
    'SR': ('SUR', '+597', '.sr', 'SRD', '$', 'Paramaribo', 'Dutch', ['Latin'], ['Dutch']),
    # Asia
    'CN': ('CHN', '+86', '.cn', 'CNY', '¥', 'Beijing', 'Mandarin', ['Han'], ['Mandarin']),
    'HK': ('HKG', '+852', '.hk', 'HKD', '$', 'Hong Kong', 'Cantonese', ['Han', 'Latin'], ['Cantonese', 'English']),
    'MO': ('MAC', '+853', '.mo', 'MOP', '$', 'Macau', 'Cantonese', ['Han', 'Latin'], ['Cantonese', 'Portuguese']),
    'IQ': ('IRQ', '+964', '.iq', 'IQD', 'ع.د', 'Baghdad', 'Arabic', ['Arabic'], ['Arabic', 'Kurdish']),
    'NP': ('NPL', '+977', '.np', 'NPR', 'Rs', 'Kathmandu', 'Nepali', ['Devanagari'], ['Nepali']),
    # Africa
    'EG': ('EGY', '+20', '.eg', 'EGP', '£', 'Cairo', 'Arabic', ['Arabic'], ['Arabic']),
    'ML': ('MLI', '+223', '.ml', 'XOF', 'CFA', 'Bamako', 'French', ['Latin'], ['French']),
    'NA': ('NAM', '+264', '.na', 'NAD', '$', 'Windhoek', 'English', ['Latin'], ['English']),
    'RW': ('RWA', '+250', '.rw', 'RWF', 'FRw', 'Kigali', 'Kinyarwanda', ['Latin'], ['Kinyarwanda', 'English', 'French']),
    'TZ': ('TZA', '+255', '.tz', 'TZS', 'TSh', 'Dodoma', 'Swahili', ['Latin'], ['Swahili', 'English']),
    'MU': ('MUS', '+230', '.mu', 'MUR', 'Rs', 'Port Louis', 'English', ['Latin'], ['English', 'French']),
    # Pacific
    'VU': ('VUT', '+678', '.vu', 'VUV', 'Vt', 'Port Vila', 'Bislama', ['Latin'], ['Bislama', 'English', 'French']),
}


def main() -> None:
    out: dict = {
        '_meta': {
            'source': 'ISO 3166-1, ISO 4217, ITU-T E.164 + Wikipedia infoboxes',
            'fields': ['iso3', 'calling_code', 'tld', 'currency_code',
                       'currency_symbol', 'capital', 'primary_language',
                       'scripts', 'official_languages'],
        },
    }
    # Cross-check against country-slugs.js so we know what's missing
    slugs_text = SLUGS_JS.read_text(encoding='utf-8')
    slugs_iso2 = sorted(set(re.findall(r'^\s+([A-Z]{2}):\s*\{', slugs_text, re.MULTILINE)))

    missing = [cc for cc in slugs_iso2 if cc not in DATA]
    extra = [cc for cc in DATA if cc not in slugs_iso2]
    print(f'country-slugs.js has {len(slugs_iso2)} countries')
    print(f'reference data has {len(DATA)} countries')
    if missing:
        print(f'MISSING (in slugs but not data): {missing}')
    if extra:
        print(f'EXTRA (in data but not slugs): {extra}')

    for iso2, (iso3, calling, tld, ccy, sym, cap, primary, scripts, langs) in DATA.items():
        out[iso2] = {
            'iso3': iso3,
            'calling_code': calling,
            'tld': tld,
            'currency_code': ccy,
            'currency_symbol': sym,
            'capital': cap,
            'primary_language': primary,
            'scripts': scripts,
            'official_languages': langs,
        }

    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {OUT.relative_to(REPO)} ({len(DATA)} countries)')


if __name__ == '__main__':
    main()
