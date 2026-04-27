"""
Builds the lean tips.json the extension bundles, by merging two sources:

1. learnablemeta_raw.json  — clean atomic country-level metas (Identify tab)
2. plonkit_raw.json        — narrative regional + spotlight content (General/
                             Regional/Spotlight tabs)

Per-country output schema (ISO-2 keyed):
{
  "AU": {
    "name": "Australia",
    "plonkit_slug": "australia",
    "key_meta": "...",                   # short anchor line shown above tabs

    "metas": [                           # learnablemeta atomic metas
      {
        "type": "Bollard",
        "title": "Bollard",
        "description": "Australian bollards are white with a red...",
        "comparison": "Turkish bollards are similar but lack a back reflector...",
        "images": ["https://learnablemeta.com/images/...avif"],
        "from_maps": ["A Learnable Meta World - Basics", ...]
      }
    ],

    "general_rules": [                   # plonkit Step 2 system rules
      {
        "topic": "Road numbers",
        "text": "Irish regional roads have 3-digit road numbers...",
        "images": ["https://www.plonkit.net/images/.../Ireland-road-numbers.png"]
      }
    ],

    "regions": {                         # plonkit Step 2 region-specific
      "Donegal": [
        { "text": "Small rural roads with G4 coverage in unusually hilly...",
          "images": ["https://www.plonkit.net/images/.../Donegal_Gen_4_roads.png"] }
      ]
    },

    "spotlight": [                       # plonkit Step 3 place-specific
      { "place": "Cairns",
        "text": "The northern QLD city of Cairns is distinct due to...",
        "images": ["..."] }
    ]
  }
}
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Slug -> ISO-2 (mirror of extension/src/data/country-slugs.js plus territory
# slugs that fold to a parent country).
# ---------------------------------------------------------------------------
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
    "guam":"GU","northern-mariana-islands":"MP","american-samoa":"AS",
    "us-minor-outlying-islands":"UM","us-virgin-islands":"VI","antarctica":"AQ",
    # Fold US states + Portuguese island groups into their parent country.
    "alaska":"US","hawaii":"US","azores":"PT","madeira":"PT",
}
SKIP_NON_COUNTRY = {"beginners-guide", "spillover-countries"}

# Display name (and a few common aliases) -> ISO-2. Used to resolve
# learnablemeta's `country` field. We accept several name variants so things
# like "USA" / "United States" / "United States of America" all map together.
_COUNTRY_NAME_TO_ISO2 = {
    "Albania":"AL","Andorra":"AD","Argentina":"AR","Armenia":"AM","Aruba":"AW","Australia":"AU",
    "Austria":"AT","Azerbaijan":"AZ","Bangladesh":"BD","Belarus":"BY","Belgium":"BE","Bermuda":"BM",
    "Bhutan":"BT","Bolivia":"BO","Botswana":"BW","Brazil":"BR","Bulgaria":"BG","Cambodia":"KH",
    "Canada":"CA","Cayman Islands":"KY","Chile":"CL","China":"CN","Colombia":"CO","Costa Rica":"CR",
    "Croatia":"HR","Cura\u00e7ao":"CW","Cyprus":"CY","Czechia":"CZ","Czech Republic":"CZ",
    "Denmark":"DK","Dominican Republic":"DO","Ecuador":"EC","Egypt":"EG","Estonia":"EE","Eswatini":"SZ",
    "Faroe Islands":"FO","Finland":"FI","France":"FR","French Guiana":"GF","Georgia":"GE","Germany":"DE",
    "Ghana":"GH","Gibraltar":"GI","Greece":"GR","Greenland":"GL","Guadeloupe":"GP","Guatemala":"GT",
    "Guernsey":"GG","Hong Kong":"HK","Hungary":"HU","Iceland":"IS","India":"IN","Indonesia":"ID",
    "Iraq":"IQ","Ireland":"IE","Isle of Man":"IM","Israel":"IL","Italy":"IT","Japan":"JP",
    "Jersey":"JE","Jordan":"JO","Kazakhstan":"KZ","Kenya":"KE","Kyrgyzstan":"KG","Laos":"LA",
    "Latvia":"LV","Lebanon":"LB","Lesotho":"LS","Liechtenstein":"LI","Lithuania":"LT","Luxembourg":"LU",
    "Macau":"MO","Madagascar":"MG","Malaysia":"MY","Mali":"ML","Malta":"MT","Martinique":"MQ",
    "Mexico":"MX","Monaco":"MC","Mongolia":"MN","Montenegro":"ME","Namibia":"NA","Nepal":"NP",
    "Netherlands":"NL","New Zealand":"NZ","Nigeria":"NG","North Macedonia":"MK","Norway":"NO",
    "Oman":"OM","Pakistan":"PK","Palestine":"PS","Panama":"PA","Peru":"PE","Philippines":"PH",
    "Poland":"PL","Portugal":"PT","Puerto Rico":"PR","Qatar":"QA","R\u00e9union":"RE","Reunion":"RE",
    "Romania":"RO","Russia":"RU","Rwanda":"RW","San Marino":"SM","Saudi Arabia":"SA","Senegal":"SN",
    "Serbia":"RS","Singapore":"SG","Slovakia":"SK","Slovenia":"SI","South Africa":"ZA",
    "South Korea":"KR","Spain":"ES","Sri Lanka":"LK","Svalbard":"SJ","Sweden":"SE","Switzerland":"CH",
    "Taiwan":"TW","Tanzania":"TZ","Thailand":"TH","Tunisia":"TN","Turkey":"TR","T\u00fcrkiye":"TR",
    "Uganda":"UG","Ukraine":"UA","United Arab Emirates":"AE","UAE":"AE",
    "United Kingdom":"GB","UK":"GB","Britain":"GB","Great Britain":"GB",
    "United States":"US","United States of America":"US","USA":"US","US":"US",
    "Uruguay":"UY","Vietnam":"VN","Zimbabwe":"ZW",
    "American Samoa":"AS","Guam":"GU","Northern Mariana Islands":"MP",
    "American Virgin Islands":"VI","US Virgin Islands":"VI",
    "Falkland Islands":"FK","Pitcairn Islands":"PN",
    "Antarctica":"AQ","Vanuatu":"VU",
}


def name_to_iso2(name: str) -> str | None:
    if not name:
        return None
    return _COUNTRY_NAME_TO_ISO2.get(name.strip()) or _COUNTRY_NAME_TO_ISO2.get(
        name.strip().rstrip(".").rstrip(",")
    )


# ---------------------------------------------------------------------------
# General-rule heuristic — same as before, slightly expanded.
# ---------------------------------------------------------------------------
GENERAL_RULE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(area code|phone number|postal code|zip code|postcode|post code)s?\b",
        r"\b(road number|first digit|starting with|begins? with|starts? with)s?\b",
        r"\b(throughout the country|across the country|nationwide|country-?wide)\b",
        r"\b(licen[cs]e plate|plate format|plate code|plate prefix|state plate|regional plate)s?\b",
        r"\bsee the (infographic|map|chart|graphic|diagram)\b",
        r"\b(mnemonic|grouped geographically)\b",
        r"\b(direction around|around the (island|country))\b",
        r"\b(area code|phone code|dialing code|dialling code)\b",
        r"\bregional letter\b",
    ]
]


def is_general_rule(text: str) -> bool:
    return any(p.search(text) for p in GENERAL_RULE_PATTERNS)


# ---------------------------------------------------------------------------
# Region extraction from plonkit image filenames.
# ---------------------------------------------------------------------------

# Stem prefixes/suffixes commonly found in plonkit image filenames that don't
# contribute region info. Stripped before tokenization.
_FILENAME_STRIP = re.compile(
    r"^(transparent[-_]+|copy[-_]of[-_]+|untitled[-_]design[-_]?\d*|0[-_]*summary[-_]?|"
    r"\d+[-_]+|copy[-_]of[-_]copy[-_]of[-_])",
    re.IGNORECASE,
)
_FILENAME_TAIL = re.compile(
    r"[-_](\d+|graphic|map|small|large|new|old|2024|2025|2026|final|"
    r"copy|summary|background|darkmode|lightmode)$",
    re.IGNORECASE,
)


def _filename_tokens(src: str, country_slug: str) -> list[str]:
    """Pull plausible region/topic tokens from a plonkit image URL."""
    m = re.search(r"/([^/]+)\.(?:png|jpe?g|webp|avif|gif)(?:\?|$)", src, re.IGNORECASE)
    if not m:
        return []
    name = m.group(1)
    name = _FILENAME_STRIP.sub("", name)
    while True:
        new = _FILENAME_TAIL.sub("", name)
        if new == name:
            break
        name = new
    raw_tokens = re.split(r"[-_\s]+", name)
    tokens = []
    for t in raw_tokens:
        if not t or t.isdigit() or len(t) < 3:
            continue
        # Drop the country slug if it sneaks into the filename ("us_..." for US).
        if t.lower() == country_slug.lower():
            continue
        # Drop common non-region tokens.
        if t.lower() in {
            "summary", "image", "img", "photo", "screenshot", "preview", "thumb",
            "side", "front", "back", "top", "type", "style", "version",
            "gen", "g2", "g3", "g4", "gen2", "gen3", "gen4",
            "ladybug", "ladybug3", "snorkel", "snorkelcam", "shitcam", "blurry",
            "north", "south", "east", "west", "central",
            "left", "right", "middle", "near", "far",
            "white", "black", "red", "blue", "green", "yellow", "orange", "purple",
            "pole", "poles", "sign", "signs", "bollard", "bollards", "plate", "plates",
            "road", "roads", "highway", "highways", "street", "streets",
            "house", "houses", "tree", "trees", "soil", "rock", "rocks",
            "car", "cars", "antenna", "snorkel", "ev", "truck",
            "lines", "line", "marking", "markings", "stripe", "stripes", "stripey",
            "border", "borders", "fence", "fences", "post", "posts",
            "transparent", "blurred", "rectangular", "square", "round", "circle",
            "graphic", "infographic", "diagram", "chart", "table",
            "step", "guide", "tip", "tips", "meta", "metas", "phase",
            "ladybug3", "google",
        }:
            continue
        tokens.append(t)
    return tokens


# Curated subdivisions for the major countries where plonkit's image filenames
# DON'T reliably carry region names (US, AU, CA, etc.). For these we restrict
# region detection to this list. For other countries we fall back to whatever
# tokens appear in image filenames (works well for IE, AT, FR, DE, etc.).
KNOWN_SUBDIVISIONS = {
    "US": [  # 50 states + DC + commonly-referenced regions
        "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut",
        "Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa",
        "Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan",
        "Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada",
        "New Hampshire","New Jersey","New Mexico","New York","North Carolina",
        "North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island",
        "South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont",
        "Virginia","Washington","West Virginia","Wisconsin","Wyoming",
        "DC","Washington DC","District of Columbia",
        "Northeast","Midwest","Southeast","Southwest","Pacific Northwest",
        "New England","Great Plains","Rocky Mountains","Appalachia","Deep South",
    ],
    "AU": [
        "New South Wales","Victoria","Queensland","South Australia","Western Australia",
        "Tasmania","Northern Territory","Australian Capital Territory",
        "NSW","Vic","Qld","SA","WA","Tas","NT","ACT",
    ],
    "CA": [
        "Alberta","British Columbia","Manitoba","New Brunswick","Newfoundland","Labrador",
        "Northwest Territories","Nova Scotia","Nunavut","Ontario","Prince Edward Island",
        "Quebec","Saskatchewan","Yukon",
        "BC","ON","QC","AB","MB","NB","NS","NL","NT","NU","PE","SK","YT",
    ],
    "BR": [
        "Acre","Alagoas","Amapa","Amazonas","Bahia","Ceara","Distrito Federal","Espirito Santo",
        "Goias","Maranhao","Mato Grosso","Mato Grosso do Sul","Minas Gerais","Para","Paraiba",
        "Parana","Pernambuco","Piaui","Rio de Janeiro","Rio Grande do Norte","Rio Grande do Sul",
        "Rondonia","Roraima","Santa Catarina","Sao Paulo","Sergipe","Tocantins",
    ],
    "DE": [
        "Baden-Wurttemberg","Bayern","Bavaria","Berlin","Brandenburg","Bremen","Hamburg",
        "Hessen","Hesse","Mecklenburg-Vorpommern","Niedersachsen","Lower Saxony",
        "Nordrhein-Westfalen","North Rhine-Westphalia","NRW","Rheinland-Pfalz","Rhineland-Palatinate",
        "Saarland","Sachsen","Saxony","Sachsen-Anhalt","Saxony-Anhalt","Schleswig-Holstein",
        "Thuringen","Thuringia",
    ],
    "FR": [
        "Auvergne","Bourgogne","Bretagne","Brittany","Centre","Champagne","Corse","Corsica",
        "Franche-Comte","Languedoc","Limousin","Lorraine","Midi","Normandie","Normandy",
        "Picardie","Poitou","Provence","Aquitaine","Alsace","Pays de la Loire",
        "Ile-de-France","Hauts-de-France","Grand Est","Nouvelle-Aquitaine","Occitanie",
        "Provence-Alpes-Cote d'Azur","Auvergne-Rhone-Alpes","Bourgogne-Franche-Comte",
    ],
    "IT": [
        "Abruzzo","Aosta","Apulia","Puglia","Basilicata","Calabria","Campania","Emilia-Romagna",
        "Friuli-Venezia Giulia","Lazio","Liguria","Lombardia","Lombardy","Marche",
        "Molise","Piemonte","Piedmont","Sardegna","Sardinia","Sicilia","Sicily","Toscana","Tuscany",
        "Trentino-Alto Adige","Umbria","Veneto",
    ],
    "ES": [
        "Andalucia","Aragon","Asturias","Cantabria","Castilla y Leon","Castilla-La Mancha",
        "Catalunya","Catalonia","Comunidad Valenciana","Valencia","Extremadura","Galicia",
        "Islas Baleares","Balearic Islands","Islas Canarias","Canary Islands","La Rioja",
        "Madrid","Murcia","Navarra","Pais Vasco","Basque Country","Ceuta","Melilla",
    ],
    "GB": [
        "England","Scotland","Wales","Northern Ireland",
        "London","Manchester","Birmingham","Liverpool","Edinburgh","Glasgow","Cardiff","Belfast",
        "Highlands","Lowlands","Yorkshire","Cornwall","Devon","Kent","Sussex","Essex","Cumbria",
    ],
    "IN": [
        "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat",
        "Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh",
        "Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan",
        "Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
        "Delhi","Puducherry","Ladakh","Jammu and Kashmir",
    ],
    "JP": [
        "Hokkaido","Aomori","Iwate","Miyagi","Akita","Yamagata","Fukushima","Ibaraki","Tochigi",
        "Gunma","Saitama","Chiba","Tokyo","Kanagawa","Niigata","Toyama","Ishikawa","Fukui",
        "Yamanashi","Nagano","Gifu","Shizuoka","Aichi","Mie","Shiga","Kyoto","Osaka","Hyogo",
        "Nara","Wakayama","Tottori","Shimane","Okayama","Hiroshima","Yamaguchi","Tokushima",
        "Kagawa","Ehime","Kochi","Fukuoka","Saga","Nagasaki","Kumamoto","Oita","Miyazaki",
        "Kagoshima","Okinawa",
    ],
    "RU": [
        "Moscow","Saint Petersburg","Karelia","Murmansk","Arkhangelsk","Komi","Vologda",
        "Kaliningrad","Pskov","Novgorod","Tver","Yaroslavl","Vladimir","Ivanovo","Kostroma",
        "Tula","Ryazan","Voronezh","Tambov","Lipetsk","Belgorod","Kursk","Bryansk","Smolensk",
        "Krasnodar","Stavropol","Rostov","Volgograd","Astrakhan","Dagestan","Chechnya",
        "Tatarstan","Bashkortostan","Mari El","Chuvashia","Mordovia","Udmurtia","Perm",
        "Sverdlovsk","Chelyabinsk","Tyumen","Khanty-Mansi","Yamalo-Nenets","Omsk","Tomsk",
        "Novosibirsk","Kemerovo","Altai","Krasnoyarsk","Khakassia","Tuva","Irkutsk","Buryatia",
        "Zabaykalsky","Yakutia","Sakha","Magadan","Kamchatka","Sakhalin","Primorsky","Khabarovsk",
        "Amur","Jewish Autonomous","Chukotka",
    ],
    "MX": [
        "Aguascalientes","Baja California","Baja California Sur","Campeche","Chiapas","Chihuahua",
        "Coahuila","Colima","Durango","Guanajuato","Guerrero","Hidalgo","Jalisco","Mexico City",
        "Michoacan","Morelos","Nayarit","Nuevo Leon","Oaxaca","Puebla","Queretaro","Quintana Roo",
        "San Luis Potosi","Sinaloa","Sonora","Tabasco","Tamaulipas","Tlaxcala","Veracruz",
        "Yucatan","Zacatecas","CDMX","Estado de Mexico",
    ],
    "AR": [
        "Buenos Aires","Catamarca","Chaco","Chubut","Cordoba","Corrientes","Entre Rios",
        "Formosa","Jujuy","La Pampa","La Rioja","Mendoza","Misiones","Neuquen","Rio Negro",
        "Salta","San Juan","San Luis","Santa Cruz","Santa Fe","Santiago del Estero",
        "Tierra del Fuego","Tucuman","Patagonia","Cuyo","Pampas","Mesopotamia",
    ],
    "AT": [  # 9 Bundeslander
        "Burgenland","Carinthia","Karnten","Lower Austria","Niederosterreich","Upper Austria",
        "Oberosterreich","Salzburg","Styria","Steiermark","Tyrol","Tirol","Vorarlberg","Vienna","Wien",
    ],
    "NL": [
        "Drenthe","Flevoland","Friesland","Gelderland","Groningen","Limburg","North Brabant",
        "Noord-Brabant","North Holland","Noord-Holland","Overijssel","South Holland","Zuid-Holland",
        "Utrecht","Zeeland","Amsterdam","Rotterdam","The Hague","Den Haag",
    ],
    "BE": [
        "Antwerp","Antwerpen","East Flanders","West Flanders","Flemish Brabant","Limburg",
        "Brussels","Walloon Brabant","Hainaut","Liege","Luxembourg","Namur","Flanders","Wallonia",
    ],
    "NO": [
        "Oslo","Viken","Innlandet","Vestfold","Telemark","Agder","Rogaland","Vestland",
        "More","Romsdal","Trondelag","Nordland","Troms","Finnmark","Svalbard",
    ],
    "SE": [
        "Stockholm","Uppsala","Sodermanland","Ostergotland","Jonkoping","Kronoberg","Kalmar",
        "Gotland","Blekinge","Skane","Halland","Vastra Gotaland","Varmland","Orebro","Vastmanland",
        "Dalarna","Gavleborg","Vasternorrland","Jamtland","Vasterbotten","Norrbotten","Lapland",
    ],
    "DK": [
        "Copenhagen","Kobenhavn","Aarhus","Odense","Aalborg","Esbjerg","Bornholm",
        "Capital Region","Central Denmark","Northern Denmark","Southern Denmark","Zealand",
        "Hovedstaden","Midtjylland","Nordjylland","Syddanmark","Sjaelland",
    ],
    "FI": [
        "Helsinki","Uusimaa","Lapland","Lappi","Kainuu","Karelia","Ostrobothnia","Pohjanmaa",
        "Pirkanmaa","Tampere","Turku","Oulu","Espoo","Vantaa","Aland",
    ],
    "PL": [
        "Mazovia","Mazowieckie","Lesser Poland","Malopolskie","Greater Poland","Wielkopolskie",
        "Silesia","Slaskie","Lower Silesia","Dolnoslaskie","Pomerania","Pomorskie","Lodz",
        "Lodzkie","Lublin","Lubelskie","Subcarpathian","Podkarpackie","Podlaskie","Warmia",
        "Warminsko-Mazurskie","West Pomerania","Zachodniopomorskie","Lubusz","Lubuskie",
        "Holy Cross","Swietokrzyskie","Opole","Opolskie","Kuyavia","Kujawsko-Pomorskie",
        "Warsaw","Krakow","Wroclaw","Gdansk",
    ],
    "CZ": [
        "Prague","Praha","Central Bohemia","South Bohemia","Plzen","Karlovy Vary","Usti nad Labem",
        "Liberec","Hradec Kralove","Pardubice","Vysocina","South Moravia","Brno","Olomouc",
        "Zlin","Moravia-Silesia","Ostrava","Bohemia","Moravia","Silesia",
    ],
    "RO": [
        "Bucharest","Transylvania","Wallachia","Moldavia","Banat","Crisana","Maramures",
        "Dobrogea","Oltenia","Cluj","Brasov","Sibiu","Iasi","Constanta","Timisoara",
    ],
    "HU": [
        "Budapest","Pest","Bacs-Kiskun","Baranya","Bekes","Borsod","Csongrad","Fejer",
        "Gyor-Moson-Sopron","Hajdu-Bihar","Heves","Jasz-Nagykun-Szolnok","Komarom-Esztergom",
        "Nograd","Somogy","Szabolcs-Szatmar-Bereg","Tolna","Vas","Veszprem","Zala",
    ],
    "ZA": [
        "Eastern Cape","Free State","Gauteng","KwaZulu-Natal","Limpopo","Mpumalanga",
        "Northern Cape","North West","Western Cape","Cape Town","Johannesburg","Durban",
        "Pretoria","Port Elizabeth","Gqeberha","Bloemfontein",
    ],
    "TH": [
        "Bangkok","Chiang Mai","Chiang Rai","Phuket","Pattaya","Hua Hin","Krabi","Koh Samui",
        "Northern Thailand","Northeast Thailand","Isan","Central Thailand","Southern Thailand",
        "Eastern Thailand","Western Thailand","Khon Kaen","Nakhon Ratchasima","Korat","Udon Thani",
    ],
    "TR": [
        "Istanbul","Ankara","Izmir","Bursa","Antalya","Adana","Konya","Gaziantep","Mersin",
        "Diyarbakir","Kayseri","Eskisehir","Trabzon","Erzurum","Van","Marmara","Aegean","Mediterranean",
        "Central Anatolia","Black Sea","Eastern Anatolia","Southeastern Anatolia",
    ],
    "ID": [
        "Jakarta","Bali","Sumatra","Java","Sulawesi","Kalimantan","Papua","Maluku","West Papua",
        "Aceh","Riau","Lampung","Yogyakarta","Surabaya","Medan","Bandung","Semarang","Makassar",
        "Sumatera","Borneo",
    ],
    "PH": [
        "Luzon","Visayas","Mindanao","Manila","Cebu","Davao","Quezon City","Cordillera","Bicol",
        "Ilocos","Cagayan","Zamboanga","Caraga","Calabarzon","Mimaropa","Soccsksargen",
    ],
    "MY": [
        "Selangor","Johor","Sabah","Sarawak","Perak","Kedah","Kelantan","Terengganu","Pahang",
        "Penang","Pulau Pinang","Negeri Sembilan","Malacca","Melaka","Perlis","Kuala Lumpur",
        "Putrajaya","Labuan",
    ],
    "VN": [
        "Hanoi","Ho Chi Minh","Saigon","Da Nang","Hue","Hai Phong","Can Tho","Mekong","Red River",
        "Northern Vietnam","Central Vietnam","Southern Vietnam","Highlands","Central Highlands",
    ],
    "KR": [
        "Seoul","Busan","Incheon","Daegu","Daejeon","Gwangju","Ulsan","Sejong","Gyeonggi",
        "Gangwon","Chungcheongbuk","Chungcheongnam","Jeollabuk","Jeollanam","Gyeongsangbuk",
        "Gyeongsangnam","Jeju","North Jeolla","South Jeolla","North Gyeongsang","South Gyeongsang",
    ],
    "NZ": [
        "Auckland","Wellington","Christchurch","Hamilton","Tauranga","Dunedin","Palmerston North",
        "Napier","Hastings","North Island","South Island","Northland","Waikato","Bay of Plenty",
        "Gisborne","Hawke's Bay","Taranaki","Manawatu","West Coast","Canterbury","Otago","Southland",
        "Marlborough","Nelson","Tasman",
    ],
    "PE": [
        "Lima","Cusco","Arequipa","Trujillo","Chiclayo","Iquitos","Puno","Ayacucho","Huancayo",
        "Tacna","Junin","Loreto","Madre de Dios","Ucayali","Ancash","Huanuco","La Libertad",
        "Cajamarca","Piura","Tumbes","Lambayeque",
    ],
    "CL": [
        "Santiago","Valparaiso","Concepcion","Antofagasta","Vina del Mar","La Serena","Iquique",
        "Arica","Punta Arenas","Puerto Montt","Temuco","Coquimbo","Atacama","Tarapaca","Maule",
        "Bio Bio","Araucania","Los Lagos","Aysen","Magallanes","Patagonia","O'Higgins","Nuble",
    ],
    "CO": [
        "Bogota","Medellin","Cali","Barranquilla","Cartagena","Cucuta","Bucaramanga","Pereira",
        "Antioquia","Cundinamarca","Valle del Cauca","Atlantico","Bolivar","Magdalena","Cesar",
        "Santander","Norte de Santander","Caldas","Risaralda","Quindio","Tolima","Huila",
        "Cauca","Narino","Putumayo","Caqueta","Amazonas","Vaupes","Vichada","Guainia","Guaviare",
        "Meta","Casanare","Arauca","Choco","Cordoba","Sucre","La Guajira","San Andres",
    ],
}


def detect_regions_for_country(plonkit_data: dict, country_slug: str,
                                 iso2: str | None = None) -> set[str]:
    """Build the set of region tokens we'll look for in image filenames.

    For countries in KNOWN_SUBDIVISIONS we use that curated list (avoids
    noise tokens like 'Stateflags', 'Topographic'). For all other countries
    we harvest plausible-looking tokens from image filenames — works well
    for the smaller covered countries like Ireland (Donegal, Wicklow,
    Cork) and Austria (Vorarlberg, Burgenland)."""
    if iso2 and iso2 in KNOWN_SUBDIVISIONS:
        return set(KNOWN_SUBDIVISIONS[iso2])
    counts: dict[str, int] = defaultdict(int)
    for items in plonkit_data["sections"].values():
        for it in items:
            if it.get("type") != "image":
                continue
            for tok in _filename_tokens(it["src"], country_slug):
                counts[tok.title()] += 1
    return {tok for tok, n in counts.items() if len(tok) >= 3 and not tok.isdigit()}


def region_for_image(src: str, country_slug: str, known_regions: set[str]) -> str | None:
    """Match the image filename against the country's known sub-region set.
    Also probes the surrounding text caption (filename's parent path), since
    some images use abbreviations like 'qld_coils.png' that need to resolve
    to 'Queensland'."""
    tokens = _filename_tokens(src, country_slug)
    if not tokens:
        return None
    known_norm = {k.lower(): k for k in known_regions}
    for n in range(min(4, len(tokens)), 0, -1):
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i:i + n])
            if phrase.lower() in known_norm:
                return known_norm[phrase.lower()]
            if phrase.endswith("s") and phrase[:-1].lower() in known_norm:
                return known_norm[phrase[:-1].lower()]
    return None


def region_for_text(text: str, known_regions: set[str]) -> str | None:
    """Find the first known sub-region name mentioned in the text."""
    if not known_regions or not text:
        return None
    # Sort by length descending so multi-word matches win over single-word.
    for region in sorted(known_regions, key=len, reverse=True):
        if len(region) < 3:
            continue
        # Word-boundary match, case-insensitive.
        if re.search(r"\b" + re.escape(region) + r"\b", text, re.IGNORECASE):
            return region
    return None


# ---------------------------------------------------------------------------
# Plonkit pairing: each image owns the next text(s) until the next image.
# ---------------------------------------------------------------------------

def pair_image_blocks(items: list[dict]) -> list[dict]:
    """Walk items in DOM order; produce a list of blocks where each block is
    either {image, texts[]} (image followed by 0+ texts that describe it),
    or {text-only} for text not preceded by an image."""
    blocks = []
    i = 0
    while i < len(items):
        it = items[i]
        if it.get("type") == "image":
            block = {"image": it, "texts": []}
            j = i + 1
            while j < len(items) and items[j].get("type") == "text":
                block["texts"].append(items[j])
                j += 1
            blocks.append(block)
            i = j
        elif it.get("type") == "text":
            blocks.append({"image": None, "texts": [it]})
            i += 1
        else:
            i += 1
    return blocks


def _section_id(name: str) -> str | None:
    n = name.lower()
    if "step 1" in n or "identif" in n:
        return "identify"
    if "step 2" in n or "regional" in n or "subdivision" in n or "region-specific" in n \
            or "county-specific" in n or "infrastruct" in n or "landscape" in n:
        return "regional"
    if "step 3" in n or "spotlight" in n:
        return "spotlight"
    return None


def _block_text(block: dict) -> str:
    return " ".join(t["text"] for t in block["texts"]).strip()


def _block_images(block: dict) -> list[str]:
    return [block["image"]["src"]] if block.get("image") else []


# ---------------------------------------------------------------------------
# Build per-country bundle
# ---------------------------------------------------------------------------

def build_country(iso2: str, slug: str, country_name: str,
                   plonkit_data: dict | None,
                   lm_metas: list[dict]) -> dict:
    out: dict = {
        "name": country_name,
        "plonkit_slug": slug,
        "key_meta": "",
        "metas": [],
        "general_rules": [],
        "regions": {},
        "spotlight": [],
    }

    # ---- Identify tab: learnablemeta atomic metas ----
    known_subdivisions = set(KNOWN_SUBDIVISIONS.get(iso2, []))

    _TRAIL_BAD = re.compile(
        r"\b(in|at|of|on|by|to|from|and|or|with|for|is|are|was|were|the|a|an)\.?$",
        re.IGNORECASE,
    )

    def _is_junk(m: dict) -> bool:
        desc = (m.get("description") or "").strip()
        if len(desc) < 50:
            return True
        if desc.startswith(("---", "***", "===")):
            return True
        if re.match(r"^(NOTE|Note|Recognition|Tip|Hint)[:.]?\s*$", desc):
            return True
        # Mid-sentence truncations end with a preposition / conjunction.
        # Strip trailing period for the check.
        tail = desc.rstrip(".").strip()
        if _TRAIL_BAD.search(tail):
            return True
        # Heuristic: very short descriptions that are basically just labels.
        if len(desc.split()) < 7:
            return True
        return False

    def _priority(m: dict) -> tuple:
        """Lower sorts first. Prefer Basics > Beginner > country-specific
        single-country map > World > themed (Architecture, City Names,
        Stop Signs, etc.). Within those, prefer descriptions that DON'T
        mention any of this country's sub-regions."""
        title = (m.get("_map_title") or "").lower()
        # 0: Basics, 1: Beginner/Novice, 2: country-specific (e.g. "A Learnable
        # Mexico", "A Learnable Russia"), 3: World, 4: themed/other.
        if "basics" in title:
            tier = 0
        elif "beginner" in title or "novice" in title:
            tier = 1
        elif iso2 == "US" and ("usa" in title or "united states" in title or "anglo-america" in title):
            tier = 2
        elif country_name.lower() in title and "world" not in title \
                and "europe" not in title and "asia" not in title \
                and "africa" not in title and "america" not in title:
            tier = 2
        elif "world" in title and "architecture" not in title \
                and "stop signs" not in title:
            tier = 3
        elif title.startswith("a learnable ") and not any(
            t in title for t in ("architecture", "city names", "stop signs",
                                  "license plates", "license plate",
                                  "regionguessing", "every country")
        ):
            tier = 3
        else:
            tier = 4

        desc = (m.get("description") or "")
        cmp_ = (m.get("comparison") or "")
        text_for_check = desc + " " + cmp_
        mentions_sub = any(
            re.search(r"\b" + re.escape(sub) + r"\b", text_for_check, re.IGNORECASE)
            for sub in known_subdivisions if len(sub) >= 3
        )
        return (tier, 1 if mentions_sub else 0, len(desc))

    def _detect_region(text: str) -> str | None:
        if not known_subdivisions:
            return None
        for sub in sorted(known_subdivisions, key=len, reverse=True):
            if len(sub) < 3:
                continue
            if re.search(r"\b" + re.escape(sub) + r"\b", text, re.IGNORECASE):
                return sub
        return None

    filtered = [m for m in lm_metas if not _is_junk(m)]
    sorted_metas = sorted(filtered, key=_priority)

    # Walk metas: each one goes to Identify (country-wide) OR Regional
    # (sub-region-specific). For Regional, the bucket key is the first
    # known sub-region mentioned in the description+comparison.
    seen_desc: dict[str, dict] = {}
    for m in sorted_metas:
        desc = m["description"].strip()
        cmp_ = m.get("comparison", "").strip()
        text_for_check = desc + " " + cmp_
        region = _detect_region(text_for_check)
        key = desc[:80].lower()
        if key in seen_desc:
            seen_desc[key]["from_maps"].append(m.get("_map_title", ""))
            continue
        record = {
            "type": (m.get("meta_label") or "").split(" - ")[0].title() or "Meta",
            "title": m.get("meta_label") or "Meta",
            "description": desc,
            "comparison": cmp_,
            "images": m.get("images", []),
            "from_maps": [m.get("_map_title", "")],
        }
        seen_desc[key] = record
        if region:
            out["regions"].setdefault(region, []).append({
                "text": desc + (("\n\n" + cmp_) if cmp_ else ""),
                "images": m.get("images", []),
                "type": record["type"],
            })
        else:
            out["metas"].append(record)

    if out["metas"]:
        first = out["metas"][0]["description"]
        out["key_meta"] = first.split(". ")[0].rstrip(".") + "."

    # ---- Plonkit-derived: general / regional / spotlight ----
    if plonkit_data:
        known_regions = detect_regions_for_country(plonkit_data, slug, iso2)

        for sec_name, items in plonkit_data["sections"].items():
            sid = _section_id(sec_name)
            if sid not in {"regional", "spotlight"}:
                continue

            blocks = pair_image_blocks(items)
            for block in blocks:
                text = _block_text(block)
                if len(text) < 20 or len(text) > 800:
                    continue
                images = _block_images(block)

                # General rule wins regardless of section.
                if is_general_rule(text):
                    topic = ""
                    if block.get("image"):
                        toks = _filename_tokens(block["image"]["src"], slug)
                        topic = " ".join(toks).title()[:40]
                    out["general_rules"].append({
                        "topic": topic or "General rule",
                        "text": text,
                        "images": images,
                    })
                    continue

                # Pull a region tag from filename, fall back to text scan.
                region = None
                if block.get("image"):
                    region = region_for_image(block["image"]["src"], slug, known_regions)
                if not region:
                    region = region_for_text(text, known_regions)

                if sid == "regional":
                    if region:
                        out["regions"].setdefault(region, []).append({
                            "text": text, "images": images,
                        })
                    # else: drop (no reliable region tag).
                elif sid == "spotlight":
                    if region:
                        out["spotlight"].append({
                            "place": region, "text": text, "images": images,
                        })

    # If we don't have an identify-tab key_meta from LM, fall back to the
    # first general rule.
    if not out["key_meta"] and out["general_rules"]:
        out["key_meta"] = out["general_rules"][0]["text"].split(". ")[0].rstrip(".") + "."

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plonkit", default="scraper/plonkit_raw.json")
    ap.add_argument("--learnable", default="scraper/learnablemeta_raw.json")
    ap.add_argument("--out", default="extension/data/tips.json")
    args = ap.parse_args()

    plonkit_path = Path(args.plonkit)
    learnable_path = Path(args.learnable)
    if not plonkit_path.exists():
        print(f"missing {plonkit_path}; run scrape_plonkit.py first")
        return
    if not learnable_path.exists():
        print(f"missing {learnable_path}; run scrape_learnablemeta.py first")
        return
    plonkit_raw = json.loads(plonkit_path.read_text(encoding="utf-8"))
    learnable_raw = json.loads(learnable_path.read_text(encoding="utf-8"))

    # Index learnablemeta metas by ISO-2 country.
    lm_by_iso2: dict[str, list[dict]] = defaultdict(list)
    for mp in learnable_raw:
        for meta in mp.get("metas", []):
            iso = name_to_iso2(meta.get("country", ""))
            if not iso:
                continue
            meta["_map_title"] = mp.get("title", "")
            lm_by_iso2[iso].append(meta)

    # Slug -> plonkit data.
    plonkit_by_slug = {slug: data for slug, data in plonkit_raw.items()
                       if slug not in SKIP_NON_COUNTRY}

    bundle = {"_meta": {"version": "0.7.0",
                        "source": "plonkit + learnablemeta (v2)"}}
    misses = []
    # Group plonkit data by ISO-2 (multiple slugs can fold into the same country
    # — e.g., alaska + hawaii + united-states all -> US).
    plonkit_by_iso2: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for slug, data in plonkit_by_slug.items():
        iso2 = SLUG_TO_ISO2.get(slug)
        if not iso2:
            misses.append(slug)
            continue
        plonkit_by_iso2[iso2].append((slug, data))

    # The canonical slug for each ISO-2 — used for plonkit URL building and
    # display name. Sub-territory slugs (alaska, hawaii, azores, madeira)
    # contribute their content but never become the canonical entry.
    CANONICAL_SLUGS = {
        "US": "united-states", "PT": "portugal",
    }

    for iso2, slug_data_list in plonkit_by_iso2.items():
        canonical_slug = CANONICAL_SLUGS.get(iso2)
        canonical_data = None
        if canonical_slug:
            for slug, data in slug_data_list:
                if slug == canonical_slug:
                    canonical_data = data
                    break
        if not canonical_data:
            # Fallback: prefer the LONGEST slug (so 'united-states' beats
            # 'hawaii' if no explicit canonical was set), tie-break alpha.
            canonical_slug, canonical_data = max(
                slug_data_list, key=lambda sd: (len(sd[0]), sd[0])
            )

        # Merge all sections from all folded slugs into one bundle input.
        merged_sections: dict[str, list] = {}
        for _, data in slug_data_list:
            for sec_name, items in data["sections"].items():
                merged_sections.setdefault(sec_name, []).extend(items)
        merged_data = {"name": canonical_data["name"], "sections": merged_sections}

        bundle[iso2] = build_country(
            iso2, canonical_slug, canonical_data["name"], merged_data,
            lm_by_iso2.get(iso2, [])
        )

    # Add LM-only countries (we have metas but no plonkit page).
    for iso2, metas in lm_by_iso2.items():
        if iso2 in bundle:
            continue
        # Try to look up the slug from any of the metas' country names.
        country_name = metas[0]["country"]
        bundle[iso2] = build_country(iso2, "", country_name, None, metas)

    Path(args.out).write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {args.out} ({len(bundle) - 1} countries)")
    if misses:
        print(f"unmapped plonkit slugs: {misses}")


if __name__ == "__main__":
    main()
