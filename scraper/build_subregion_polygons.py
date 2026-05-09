"""Build a trimmed admin-1 GeoJSON + a name-to-polygon mapping for countries
with regional metas in tips.json.

Strategy:
- For each country with regions{} in tips.json, fuzzy-match each clean region
  name against admin-1 polygons (name, gn_name, name_alt, latin name).
- Skip junk region labels we know won't match (General Region, "South Of",
  bare directions, etc.).
- Output:
    extension/data/admin1_trim.geojson (only matched polygons, ~3-5 MB)
    extension/data/subregion_polygons.json  ({cc: {regionName: featureId}})
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parents[1]
ADMIN1 = REPO / 'extension' / 'data' / 'admin1.geojson'
TIPS = REPO / 'extension' / 'data' / 'tips.json'
OUT_GEO = REPO / 'extension' / 'data' / 'admin1_trim.geojson'
OUT_MAP = REPO / 'extension' / 'data' / 'subregion_polygons.json'

# Region keys that we KNOW are too vague / too messy to match. Skip outright.
SKIP_REGION_KEYS = {
    'General Region', 'North', 'South', 'East', 'West',
    'North Of', 'South Of', 'East Of', 'West Of',
    'North Coast', 'South Coast', 'East Coast', 'West Coast',
    'North Half', 'South Half', 'East Half', 'West Half',
    'North And', 'South And', 'East And', 'West And',
    'East Parts', 'West Parts', 'North Parts', 'South Parts',
    'Northern', 'Southern', 'Eastern', 'Western',
}

# Cultural / multi-state regions that need a SET of admin-1 polygons. Clicks
# anywhere in the set count as correct.
POLYGON_SETS: dict[tuple[str, str], list[str]] = {
    # US cultural regions — by US state postal code
    ('US', 'New England'):       ['Maine','New Hampshire','Vermont','Massachusetts','Rhode Island','Connecticut'],
    ('US', 'Midwest'):           ['North Dakota','South Dakota','Nebraska','Kansas','Minnesota','Iowa','Missouri','Wisconsin','Illinois','Indiana','Ohio','Michigan'],
    ('US', 'Deep South'):        ['Alabama','Georgia','Louisiana','Mississippi','South Carolina'],
    ('US', 'Pacific Northwest'): ['Washington','Oregon','Idaho'],
    ('US', 'Appalachia'):        ['West Virginia','Kentucky','Tennessee','Virginia','North Carolina','Pennsylvania','Ohio','Maryland'],
    ('US', 'Western US'):        ['Washington','Oregon','California','Nevada','Idaho','Montana','Wyoming','Utah','Colorado','Arizona','New Mexico','Alaska','Hawaii'],
    ('US', 'Eastern US'):        ['Maine','New Hampshire','Vermont','Massachusetts','Rhode Island','Connecticut','New York','New Jersey','Pennsylvania','Delaware','Maryland','Virginia','West Virginia','North Carolina','South Carolina','Georgia','Florida'],
    ('US', 'Southern US'):       ['Texas','Oklahoma','Arkansas','Louisiana','Mississippi','Alabama','Tennessee','Kentucky','Georgia','Florida','South Carolina','North Carolina','Virginia','West Virginia'],
    ('US', 'Southeast'):         ['North Carolina','South Carolina','Georgia','Florida','Alabama','Mississippi','Tennessee','Kentucky','Arkansas','Louisiana','Virginia','West Virginia'],
    ('US', 'Southwest'):         ['Texas','New Mexico','Arizona','Nevada','California','Oklahoma','Utah','Colorado'],
    ('US', 'Northeast'):         ['Maine','New Hampshire','Vermont','Massachusetts','Rhode Island','Connecticut','New York','New Jersey','Pennsylvania'],
    ('US', 'Rocky Mountains'):   ['Idaho','Montana','Wyoming','Colorado','Utah','New Mexico'],
    ('US', 'Great Plains'):      ['North Dakota','South Dakota','Nebraska','Kansas','Oklahoma','Texas','Montana'],
    ('US', 'New York'):          ['New York'],
    # Brazil cultural regions
    ('BR', 'Northeast Brazil'):  ['Maranhão','Piauí','Ceará','Rio Grande do Norte','Paraíba','Pernambuco','Alagoas','Sergipe','Bahia'],
    ('BR', 'Southern Brazil'):   ['Paraná','Santa Catarina','Rio Grande do Sul'],
    ('BR', 'Southeast Brazil'):  ['São Paulo','Rio de Janeiro','Minas Gerais','Espírito Santo'],
    ('BR', 'North Brazil'):      ['Acre','Amazonas','Roraima','Pará','Amapá','Tocantins','Rondônia'],
    ('BR', 'Central-West Brazil'): ['Mato Grosso','Mato Grosso do Sul','Goiás','Distrito Federal'],
    # Germany rough halves
    ('DE', 'Eastern Germany'):   ['Mecklenburg-Vorpommern','Brandenburg','Berlin','Sachsen-Anhalt','Sachsen','Thüringen'],
    ('DE', 'Western Germany'):   ['Schleswig-Holstein','Hamburg','Bremen','Niedersachsen','Nordrhein-Westfalen','Rheinland-Pfalz','Saarland','Hessen','Baden-Württemberg','Bayern'],
    # Italy
    ('IT', 'Northern Italy'):    ['Piemonte','Valle d\'Aosta','Liguria','Lombardia','Trentino-Alto Adige','Veneto','Friuli-Venezia Giulia','Emilia-Romagna'],
    ('IT', 'Southern Italy'):    ['Abruzzo','Molise','Campania','Puglia','Basilicata','Calabria','Sicilia','Sardegna'],
    ('IT', 'Central Italy'):     ['Toscana','Umbria','Marche','Lazio'],
    # Australia
    ('AU', 'Outback'):           ['Northern Territory','Western Australia','South Australia','Queensland'],
    # Russia rough divisions
    ('RU', 'Siberia'):           ['Krasnoyarsk Krai','Irkutsk Oblast','Yakutia','Tyumen Oblast','Khabarovsk Krai','Magadan Oblast','Kamchatka Krai','Chukotka Autonomous Okrug','Primorsky Krai','Buryatia','Zabaykalsky Krai','Tomsk Oblast','Novosibirsk Oblast','Kemerovo Oblast','Altai Krai'],
    ('RU', 'Far East'):          ['Khabarovsk Krai','Magadan Oblast','Kamchatka Krai','Chukotka Autonomous Okrug','Primorsky Krai','Sakhalin Oblast','Yakutia','Jewish Autonomous Oblast','Amur Oblast'],
    ('RU', 'Caucasus'):          ['Krasnodar Krai','Stavropol Krai','Dagestan','Chechnya','Ingushetia','North Ossetia','Kabardino-Balkaria','Karachay-Cherkessia','Adygea'],
    # Indonesia island groups
    ('ID', 'Sumatra'):           ['Aceh','North Sumatra','West Sumatra','Riau','Riau Islands','Jambi','South Sumatra','Bengkulu','Lampung','Bangka Belitung Islands'],
    ('ID', 'Java'):              ['Banten','Jakarta','West Java','Central Java','Yogyakarta','East Java'],
    ('ID', 'Sulawesi'):          ['North Sulawesi','Gorontalo','Central Sulawesi','West Sulawesi','South Sulawesi','Southeast Sulawesi'],
    ('ID', 'Kalimantan'):        ['West Kalimantan','Central Kalimantan','South Kalimantan','East Kalimantan','North Kalimantan'],
    ('ID', 'Bali'):              ['Bali'],
    ('ID', 'Papua'):             ['Papua','West Papua'],
    # Philippines island groups
    ('PH', 'Luzon'):             ['Ilocos','Cagayan Valley','Central Luzon','Calabarzon','Mimaropa','Bicol','Cordillera Administrative Region','Metropolitan Manila'],
    ('PH', 'Visayas'):           ['Western Visayas','Central Visayas','Eastern Visayas'],
    ('PH', 'Mindanao'):          ['Zamboanga Peninsula','Northern Mindanao','Davao','Soccsksargen','Caraga','Bangsamoro Autonomous Region in Muslim Mindanao'],
    # Japan main islands (each maps to its prefectures)
    ('JP', 'Hokkaido'):          ['Hokkaido'],
    ('JP', 'Kyushu'):            ['Fukuoka','Saga','Nagasaki','Kumamoto','Oita','Miyazaki','Kagoshima','Okinawa'],
    ('JP', 'Shikoku'):           ['Tokushima','Kagawa','Ehime','Kochi'],
    ('JP', 'Okinawa'):           ['Okinawa'],
    # France cultural regions (some map to multiple admin-1)
    ('FR', 'Provence'):          ["Provence-Alpes-Côte d'Azur"],
    ('FR', 'Alsace'):            ['Grand Est'],
    # Canada cultural groupings
    ('CA', 'Prairies'):          ['Alberta','Saskatchewan','Manitoba'],
    ('CA', 'Maritimes'):         ['New Brunswick','Nova Scotia','Prince Edward Island'],
    ('CA', 'Atlantic Canada'):   ['New Brunswick','Nova Scotia','Prince Edward Island','Newfoundland and Labrador'],
    # India geographic regions
    ('IN', 'Kashmir'):           ['Jammu and Kashmir','Ladakh'],
    ('IN', 'Northeast India'):   ['Assam','Arunachal Pradesh','Manipur','Meghalaya','Mizoram','Nagaland','Tripura','Sikkim'],
    ('IN', 'South India'):       ['Kerala','Tamil Nadu','Karnataka','Andhra Pradesh','Telangana','Goa'],
    # Thailand
    ('TH', 'Northern Thailand'): ['Chiang Mai','Chiang Rai','Lamphun','Lampang','Phrae','Nan','Phayao','Mae Hong Son'],
    ('TH', 'Southern Thailand'): ['Chumphon','Surat Thani','Nakhon Si Thammarat','Phuket','Krabi','Trang','Phatthalung','Songkhla','Yala','Pattani','Narathiwat','Satun','Phangnga','Ranong'],
    ('TH', 'Isaan'):             ['Khon Kaen','Udon Thani','Nong Khai','Loei','Sakon Nakhon','Nakhon Phanom','Mukdahan','Yasothon','Roi Et','Maha Sarakham','Kalasin','Ubon Ratchathani','Amnat Charoen','Buriram','Surin','Si Sa Ket','Nakhon Ratchasima','Chaiyaphum','Nong Bua Lamphu','Bueng Kan'],
    # Norway
    ('NO', 'Northern Norway'):   ['Nordland','Troms og Finnmark'],
    ('NO', 'Western Norway'):    ['Møre og Romsdal','Vestland','Rogaland'],
    ('NO', 'Eastern Norway'):    ['Oslo','Viken','Innlandet','Vestfold og Telemark','Agder'],
    # Turkey
    ('TR', 'Anatolia'):          ['Ankara','Konya','Kayseri','Sivas','Erzurum'],
    ('TR', 'Eastern Anatolia'):  ['Erzurum','Erzincan','Bitlis','Van','Hakkari','Kars','Ardahan','Iğdır','Ağrı','Tunceli','Bingöl','Muş','Elazığ','Malatya'],
    ('TR', 'Aegean'):            ['İzmir','Aydın','Muğla','Manisa','Denizli','Kütahya','Afyonkarahisar','Uşak'],
    # Argentina + Chile
    ('AR', 'Patagonia'):         ['Río Negro','Neuquén','Chubut','Santa Cruz','Tierra del Fuego'],
    ('AR', 'Pampas'):            ['Buenos Aires','La Pampa','Córdoba','Santa Fe','Entre Ríos'],
    ('CL', 'Patagonia'):         ['Aysén','Magallanes y Antártica Chilena','Los Lagos'],
    ('CL', 'Atacama'):           ['Atacama','Antofagasta'],
    # Peru
    ('PE', 'Andes'):             ['Cusco','Puno','Apurímac','Ayacucho','Huancavelica','Junín','Pasco','Huánuco','Áncash','Cajamarca','Arequipa'],
    # Kenya
    ('KE', 'Coast'):             ['Mombasa','Kwale','Kilifi','Tana River','Lamu','Taita-Taveta'],
    ('KE', 'Highlands'):         ['Nairobi','Kiambu','Murang\'a','Nyeri','Kirinyaga','Embu','Meru','Tharaka-Nithi'],
    # China
    ('CN', 'Tibet'):             ['Tibet'],
    ('CN', 'Xinjiang'):           ['Xinjiang Uyghur Autonomous Region'],
    ('CN', 'Inner Mongolia'):    ['Inner Mongolia'],
    ('CN', 'Yunnan'):            ['Yunnan'],
    ('CN', 'Sichuan'):           ['Sichuan'],
    ('CN', 'Hainan'):            ['Hainan'],
    # GB extras
    ('GB', 'Cornwall'):          ['Cornwall'],
}

# Hand-curated aliases for region names that don't match admin-1 by name but
# DO map cleanly to a single admin-1 polygon. iso2 + alias -> canonical name.
ALIASES = {
    ('US', 'Hawaii'): 'Hawaii',
    ('US', 'Alaska'): 'Alaska',
    ('US', 'Texas'): 'Texas',
    ('US', 'California'): 'California',
    ('US', 'Florida'): 'Florida',
    # British Isles regions that map to admin-1 names
    ('GB', 'Scotland'): 'Scotland',
    ('GB', 'Wales'): 'Wales',
    ('GB', 'Northern Ireland'): 'Northern Ireland',
    ('GB', 'England'): 'England',
    # Spain
    ('ES', 'Catalonia'): 'Cataluña',
    ('ES', 'Andalusia'): 'Andalucía',
    ('ES', 'Basque Country'): 'País Vasco',
    ('ES', 'Galicia'): 'Galicia',
    # Italy
    ('IT', 'Sicily'): 'Sicilia',
    ('IT', 'Sardinia'): 'Sardegna',
    ('IT', 'Tuscany'): 'Toscana',
    ('IT', 'Lombardy'): 'Lombardia',
    # Germany
    ('DE', 'Bavaria'): 'Bayern',
    ('DE', 'Saxony'): 'Sachsen',
    # Japan prefectures usually match by name with -ken stripped
    # Brazil
    ('BR', 'São Paulo'): 'São Paulo',
    ('BR', 'Sao Paulo'): 'São Paulo',
    ('BR', 'Sao Paulo State'): 'São Paulo',
    ('BR', 'Rio de Janeiro'): 'Rio de Janeiro',
    ('BR', 'Rio de Janeiro State'): 'Rio de Janeiro',
    # Australia abbreviations (very common in tips)
    ('AU', 'NSW'): 'New South Wales',
    ('AU', 'Qld'): 'Queensland',
    ('AU', 'Vic'): 'Victoria',
    ('AU', 'Tas'): 'Tasmania',
    ('AU', 'WA'): 'Western Australia',
    ('AU', 'SA'): 'South Australia',
    ('AU', 'NT'): 'Northern Territory',
    ('AU', 'ACT'): 'Australian Capital Territory',
    # France
    ('FR', 'Brittany'): 'Bretagne',
    ('FR', 'Normandy'): 'Normandie',
    ('FR', 'Burgundy'): 'Bourgogne-Franche-Comté',
    ('FR', 'Corsica'): 'Corse',
    # Mexico
    ('MX', 'San Luis Potosi'): 'San Luis Potosí',
    ('MX', 'Yucatan'): 'Yucatán',
    # Spain (extras)
    ('ES', 'Canary Islands'): 'Canarias',
    # Italy (extras)
    ('IT', 'Veneto'): 'Veneto',
    # India
    ('IN', 'Goa'): 'Goa',
    # New Zealand
    ('NZ', 'North Island'): 'North Island',
    ('NZ', 'South Island'): 'South Island',
    # Tanzania
    ('TZ', 'Zanzibar'): 'Zanzibar',
}


def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def looks_like_clean_region(key: str) -> bool:
    if key in SKIP_REGION_KEYS:
        return False
    # Reject keys that are bare directions or fragments
    parts = key.split()
    if len(parts) == 1 and parts[0].lower() in {'north','south','east','west','northern','southern','eastern','western','central','around','near'}:
        return False
    # Reject overly long keys (probably parsed garbage)
    if len(key) > 60:
        return False
    return True


def main() -> None:
    print('loading admin-1 polygons...')
    admin = json.loads(ADMIN1.read_text(encoding='utf-8'))
    # Index by (iso_a2, normalized name)
    by_cc_name: dict[tuple[str, str], dict] = {}
    for feat in admin['features']:
        p = feat['properties']
        cc = p.get('iso_a2')
        if not cc or cc == '-99':
            continue
        names = [
            p.get('name'),
            p.get('name_en'),
            p.get('gn_name'),
            p.get('woe_name'),
            p.get('name_alt'),
        ]
        for n in names:
            if not n:
                continue
            key = (cc.upper(), normalize(n))
            by_cc_name.setdefault(key, feat)
    print(f'  indexed {len(by_cc_name)} (cc, name) -> polygon entries')

    tips = json.loads(TIPS.read_text(encoding='utf-8'))

    matched_features: dict[int, dict] = {}     # polygon's iso_3166_2 / fid -> feature
    region_map: dict[str, dict[str, str]] = defaultdict(dict)  # cc -> {regionName: polygonKey}
    unmatched: list[tuple[str, str]] = []
    matched_count = 0

    for cc, c in tips.items():
        if cc == '_meta':
            continue
        regions = c.get('regions') or {}
        if not regions:
            continue
        cc_u = cc.upper()
        for region_name in regions:
            if not looks_like_clean_region(region_name):
                continue
            # Polygon-set fallback (cultural / multi-state regions)
            poly_set = POLYGON_SETS.get((cc_u, region_name))
            if poly_set:
                fids = []
                for n in poly_set:
                    feat = by_cc_name.get((cc_u, normalize(n)))
                    if not feat:
                        continue
                    p = feat['properties']
                    fid = p.get('iso_3166_2') or p.get('code_local') or f"{cc_u}-{normalize(p.get('name') or 'X')[:8]}"
                    matched_features[fid] = feat
                    fids.append(fid)
                if fids:
                    region_map[cc_u][region_name] = fids if len(fids) > 1 else fids[0]
                    matched_count += 1
                    continue
            # Single-polygon match
            lookup_name = ALIASES.get((cc_u, region_name), region_name)
            key = (cc_u, normalize(lookup_name))
            feat = by_cc_name.get(key)
            if not feat:
                # Try removing leading directional words
                stripped = re.sub(r'^(northern|southern|eastern|western|central|north|south|east|west)\s+', '', region_name, flags=re.I)
                if stripped != region_name:
                    feat = by_cc_name.get((cc_u, normalize(stripped)))
            if feat:
                p = feat['properties']
                fid = p.get('iso_3166_2') or p.get('code_local') or f"{cc_u}-{normalize(p.get('name') or 'X')[:8]}"
                matched_features[fid] = feat
                region_map[cc_u][region_name] = fid
                matched_count += 1
            else:
                unmatched.append((cc_u, region_name))

    print(f'matched {matched_count} regions across {len(region_map)} countries')
    print(f'unmatched: {len(unmatched)}')
    print('  sample unmatched:')
    for cc, name in unmatched[:15]:
        print(f'    {cc}: {name!r}')

    # Write trimmed geojson — only the polygons we actually use
    trim = {
        'type': 'FeatureCollection',
        'features': list(matched_features.values()),
    }
    OUT_GEO.write_text(json.dumps(trim, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {OUT_GEO.relative_to(REPO)} ({OUT_GEO.stat().st_size // 1024} KB, {len(trim["features"])} features)')

    OUT_MAP.write_text(json.dumps(region_map, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {OUT_MAP.relative_to(REPO)} ({len(region_map)} countries)')


if __name__ == '__main__':
    main()
