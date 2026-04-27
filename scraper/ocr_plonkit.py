"""
Runs EasyOCR over every downloaded plonkit image and extracts any text that
matches a known sub-region of the image's country. Annotates plonkit_raw.json
in-place with an `ocr_regions` field per image.

Why: plonkit's images often embed a small inset map highlighting which state
or region the meta applies to, with the region name printed nearby. Filename
heuristics catch some of these but miss many. OCR + a per-country
known-subdivisions lookup gives us authoritative tagging.

Usage:
    python scraper/ocr_plonkit.py [--plonkit scraper/plonkit_raw.json]
                                  [--limit N]   # only process first N images
                                  [--country slug]  # only this country

Notes:
    - Loads EasyOCR English model on first call (~100 MB download).
    - Scans all plonkit images flagged with local_path. Skips the rest.
    - Throughput ~1-3 seconds per image on CPU; overall ~30 min for ~5000
      plonkit images. Cached: re-running skips already-OCR'd entries.
"""
import argparse
import json
import re
import sys
import warnings
from pathlib import Path

# EasyOCR is noisy on first import.
warnings.filterwarnings("ignore")

import easyocr  # noqa: E402

# Mirror of KNOWN_SUBDIVISIONS in build_bundle.py (ISO-2 -> list of names).
# Keep in sync — duplicating here so the OCR script doesn't pull build_bundle's
# heavy imports.
KNOWN_SUBDIVISIONS = {
    "US": [
        "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut",
        "Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa",
        "Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan",
        "Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada",
        "New Hampshire","New Jersey","New Mexico","New York","North Carolina",
        "North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island",
        "South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont",
        "Virginia","Washington","West Virginia","Wisconsin","Wyoming",
    ],
    "AU": ["New South Wales","Victoria","Queensland","South Australia","Western Australia",
           "Tasmania","Northern Territory","Australian Capital Territory",
           "NSW","VIC","QLD","SA","WA","TAS","NT","ACT"],
    "CA": ["Alberta","British Columbia","Manitoba","New Brunswick","Newfoundland","Labrador",
           "Northwest Territories","Nova Scotia","Nunavut","Ontario","Prince Edward Island",
           "Quebec","Saskatchewan","Yukon"],
    "BR": ["Acre","Alagoas","Amapa","Amazonas","Bahia","Ceara","Distrito Federal","Espirito Santo",
           "Goias","Maranhao","Mato Grosso","Mato Grosso do Sul","Minas Gerais","Para","Paraiba",
           "Parana","Pernambuco","Piaui","Rio de Janeiro","Rio Grande do Norte","Rio Grande do Sul",
           "Rondonia","Roraima","Santa Catarina","Sao Paulo","Sergipe","Tocantins"],
    "DE": ["Baden-Wurttemberg","Bayern","Bavaria","Berlin","Brandenburg","Bremen","Hamburg",
           "Hessen","Hesse","Mecklenburg-Vorpommern","Niedersachsen","Lower Saxony",
           "Nordrhein-Westfalen","North Rhine-Westphalia","NRW","Rheinland-Pfalz","Rhineland-Palatinate",
           "Saarland","Sachsen","Saxony","Sachsen-Anhalt","Saxony-Anhalt","Schleswig-Holstein",
           "Thuringen","Thuringia"],
    "FR": ["Auvergne","Bourgogne","Bretagne","Brittany","Centre","Champagne","Corse","Corsica",
           "Franche-Comte","Languedoc","Limousin","Lorraine","Midi","Normandie","Normandy",
           "Picardie","Poitou","Provence","Aquitaine","Alsace","Pays de la Loire",
           "Ile-de-France","Hauts-de-France","Grand Est","Nouvelle-Aquitaine","Occitanie"],
    "IT": ["Abruzzo","Aosta","Apulia","Puglia","Basilicata","Calabria","Campania","Emilia-Romagna",
           "Friuli-Venezia Giulia","Lazio","Liguria","Lombardia","Lombardy","Marche",
           "Molise","Piemonte","Piedmont","Sardegna","Sardinia","Sicilia","Sicily","Toscana","Tuscany",
           "Trentino-Alto Adige","Umbria","Veneto"],
    "ES": ["Andalucia","Aragon","Asturias","Cantabria","Castilla y Leon","Castilla-La Mancha",
           "Catalunya","Catalonia","Comunidad Valenciana","Valencia","Extremadura","Galicia",
           "Islas Baleares","Balearic Islands","Islas Canarias","Canary Islands","La Rioja",
           "Madrid","Murcia","Navarra","Pais Vasco","Basque Country","Ceuta","Melilla"],
    "GB": ["England","Scotland","Wales","Northern Ireland","London","Manchester","Birmingham",
           "Liverpool","Edinburgh","Glasgow","Cardiff","Belfast","Yorkshire","Cornwall","Devon"],
    "IN": ["Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh","Goa","Gujarat",
           "Haryana","Himachal Pradesh","Jharkhand","Karnataka","Kerala","Madhya Pradesh",
           "Maharashtra","Manipur","Meghalaya","Mizoram","Nagaland","Odisha","Punjab","Rajasthan",
           "Sikkim","Tamil Nadu","Telangana","Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
           "Delhi","Puducherry","Ladakh","Jammu and Kashmir"],
    "JP": ["Hokkaido","Aomori","Iwate","Miyagi","Akita","Yamagata","Fukushima","Ibaraki","Tochigi",
           "Gunma","Saitama","Chiba","Tokyo","Kanagawa","Niigata","Toyama","Ishikawa","Fukui",
           "Yamanashi","Nagano","Gifu","Shizuoka","Aichi","Mie","Shiga","Kyoto","Osaka","Hyogo",
           "Nara","Wakayama","Tottori","Shimane","Okayama","Hiroshima","Yamaguchi","Tokushima",
           "Kagawa","Ehime","Kochi","Fukuoka","Saga","Nagasaki","Kumamoto","Oita","Miyazaki",
           "Kagoshima","Okinawa"],
    "RU": ["Moscow","Saint Petersburg","Karelia","Murmansk","Arkhangelsk","Komi","Vologda",
           "Kaliningrad","Pskov","Novgorod","Tver","Yaroslavl","Vladimir","Krasnodar","Stavropol",
           "Rostov","Volgograd","Astrakhan","Dagestan","Tatarstan","Bashkortostan","Perm",
           "Sverdlovsk","Chelyabinsk","Tyumen","Omsk","Tomsk","Novosibirsk","Kemerovo","Altai",
           "Krasnoyarsk","Irkutsk","Buryatia","Yakutia","Sakha","Magadan","Kamchatka","Sakhalin",
           "Primorsky","Khabarovsk","Amur","Chukotka"],
    "MX": ["Aguascalientes","Baja California","Baja California Sur","Campeche","Chiapas","Chihuahua",
           "Coahuila","Colima","Durango","Guanajuato","Guerrero","Hidalgo","Jalisco","Mexico City",
           "Michoacan","Morelos","Nayarit","Nuevo Leon","Oaxaca","Puebla","Queretaro","Quintana Roo",
           "San Luis Potosi","Sinaloa","Sonora","Tabasco","Tamaulipas","Tlaxcala","Veracruz",
           "Yucatan","Zacatecas","CDMX"],
    "AR": ["Buenos Aires","Catamarca","Chaco","Chubut","Cordoba","Corrientes","Entre Rios",
           "Formosa","Jujuy","La Pampa","La Rioja","Mendoza","Misiones","Neuquen","Rio Negro",
           "Salta","San Juan","San Luis","Santa Cruz","Santa Fe","Santiago del Estero",
           "Tierra del Fuego","Tucuman","Patagonia"],
    "AT": ["Burgenland","Carinthia","Karnten","Lower Austria","Niederosterreich","Upper Austria",
           "Oberosterreich","Salzburg","Styria","Steiermark","Tyrol","Tirol","Vorarlberg","Vienna","Wien"],
    "TH": ["Bangkok","Chiang Mai","Chiang Rai","Phuket","Pattaya","Hua Hin","Krabi","Koh Samui",
           "Khon Kaen","Nakhon Ratchasima","Korat","Udon Thani","Isan"],
    "TR": ["Istanbul","Ankara","Izmir","Bursa","Antalya","Adana","Konya","Gaziantep","Mersin",
           "Diyarbakir","Kayseri","Eskisehir","Trabzon","Erzurum","Van","Marmara","Aegean"],
    "ID": ["Jakarta","Bali","Sumatra","Java","Sulawesi","Kalimantan","Papua","Maluku","West Papua",
           "Aceh","Riau","Lampung","Yogyakarta","Surabaya","Medan","Bandung","Semarang","Makassar"],
    "ZA": ["Eastern Cape","Free State","Gauteng","KwaZulu-Natal","Limpopo","Mpumalanga",
           "Northern Cape","North West","Western Cape","Cape Town","Johannesburg","Durban","Pretoria"],
    "NL": ["Drenthe","Flevoland","Friesland","Gelderland","Groningen","Limburg","North Brabant",
           "Noord-Brabant","North Holland","Noord-Holland","Overijssel","South Holland","Zuid-Holland",
           "Utrecht","Zeeland","Amsterdam","Rotterdam"],
    "PL": ["Mazovia","Mazowieckie","Lesser Poland","Malopolskie","Greater Poland","Wielkopolskie",
           "Silesia","Slaskie","Lower Silesia","Pomerania","Pomorskie","Lodz","Lublin","Lubelskie",
           "Subcarpathian","Podkarpackie","Podlaskie","Warsaw","Krakow","Wroclaw","Gdansk"],
    "SE": ["Stockholm","Uppsala","Sodermanland","Ostergotland","Jonkoping","Kronoberg","Kalmar",
           "Gotland","Blekinge","Skane","Halland","Vastra Gotaland","Varmland","Orebro","Vastmanland",
           "Dalarna","Gavleborg","Vasternorrland","Jamtland","Vasterbotten","Norrbotten","Lapland"],
    "NO": ["Oslo","Viken","Innlandet","Vestfold","Telemark","Agder","Rogaland","Vestland",
           "Trondelag","Nordland","Troms","Finnmark"],
    "FI": ["Helsinki","Uusimaa","Lapland","Lappi","Kainuu","Karelia","Ostrobothnia","Pohjanmaa",
           "Pirkanmaa","Tampere","Turku","Oulu","Espoo","Vantaa","Aland"],
    "PE": ["Lima","Cusco","Arequipa","Trujillo","Chiclayo","Iquitos","Puno","Ayacucho","Huancayo",
           "Tacna","Junin","Loreto","Madre de Dios","Ucayali","Ancash","Huanuco","La Libertad"],
    "CL": ["Santiago","Valparaiso","Concepcion","Antofagasta","Vina del Mar","La Serena","Iquique",
           "Arica","Punta Arenas","Puerto Montt","Temuco","Atacama","Maule","Bio Bio","Araucania",
           "Los Lagos","Aysen","Magallanes","Patagonia"],
    "CO": ["Bogota","Medellin","Cali","Barranquilla","Cartagena","Antioquia","Cundinamarca",
           "Valle del Cauca","Atlantico","Bolivar","Magdalena","Santander","Tolima","Huila"],
    "MY": ["Selangor","Johor","Sabah","Sarawak","Perak","Kedah","Kelantan","Terengganu","Pahang",
           "Penang","Negeri Sembilan","Malacca","Melaka","Perlis","Kuala Lumpur"],
    "PH": ["Luzon","Visayas","Mindanao","Manila","Cebu","Davao","Quezon City"],
    "VN": ["Hanoi","Ho Chi Minh","Saigon","Da Nang","Hue","Hai Phong","Can Tho","Mekong"],
    "KR": ["Seoul","Busan","Incheon","Daegu","Daejeon","Gwangju","Ulsan","Sejong","Gyeonggi",
           "Gangwon","Jeju","Jeolla","Gyeongsang"],
    "NZ": ["Auckland","Wellington","Christchurch","Hamilton","Tauranga","Dunedin","Palmerston North",
           "Napier","Hastings","North Island","South Island","Northland","Waikato","Bay of Plenty",
           "Gisborne","Hawke's Bay","Taranaki","Manawatu","West Coast","Canterbury","Otago","Southland"],
    "RO": ["Bucharest","Transylvania","Wallachia","Moldavia","Banat","Cluj","Brasov","Sibiu","Iasi"],
    "HU": ["Budapest","Pest","Bekes","Borsod","Csongrad","Fejer","Hajdu-Bihar","Heves","Somogy"],
    "CZ": ["Prague","Praha","Bohemia","Moravia","Silesia","Brno","Ostrava"],
    "BE": ["Antwerp","Antwerpen","East Flanders","West Flanders","Brussels","Hainaut","Liege",
           "Luxembourg","Namur","Flanders","Wallonia"],
    "DK": ["Copenhagen","Aarhus","Odense","Aalborg","Bornholm","Zealand","Sjaelland","Jutland"],
    "IE": ["Donegal","Dublin","Cork","Galway","Limerick","Wicklow","Wexford","Connemara",
           "Munster","Leinster","Connacht","Ulster","Western"],
}

# Plonkit slug -> ISO-2 (only the ones we have subdivisions for; others get
# skipped during OCR since we have no list to match against).
SLUG_TO_ISO2 = {
    "australia":"AU","austria":"AT","argentina":"AR","brazil":"BR","canada":"CA",
    "chile":"CL","colombia":"CO","czechia":"CZ","denmark":"DK","france":"FR",
    "germany":"DE","hungary":"HU","india":"IN","indonesia":"ID","ireland":"IE",
    "italy":"IT","japan":"JP","kazakhstan":"KZ","malaysia":"MY","mexico":"MX",
    "netherlands":"NL","new-zealand":"NZ","norway":"NO","peru":"PE","philippines":"PH",
    "poland":"PL","romania":"RO","russia":"RU","south-africa":"ZA","south-korea":"KR",
    "spain":"ES","sweden":"SE","thailand":"TH","turkey":"TR","ukraine":"UA",
    "united-kingdom":"GB","united-states":"US","vietnam":"VN","finland":"FI","belgium":"BE",
    # Plonkit US substate slugs fold to US.
    "alaska":"US","hawaii":"US",
    # Portuguese substates.
    "azores":"PT","madeira":"PT",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plonkit", default="scraper/plonkit_raw.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--country", default=None, help="Only process this slug")
    args = ap.parse_args()

    plonkit_path = Path(args.plonkit)
    raw = json.loads(plonkit_path.read_text(encoding="utf-8"))

    # Init reader once. EasyOCR will download a ~100 MB English model on first
    # run.
    print("loading EasyOCR English model (first run downloads ~100 MB)...", flush=True)
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    all_targets: list[tuple[dict, str, list[str]]] = []
    for slug, data in raw.items():
        if args.country and slug != args.country:
            continue
        iso2 = SLUG_TO_ISO2.get(slug)
        if not iso2:
            continue
        subs = KNOWN_SUBDIVISIONS.get(iso2)
        if not subs:
            continue
        for sec_items in data.get("sections", {}).values():
            for item in sec_items:
                if item.get("type") != "image":
                    continue
                if item.get("ocr_done"):
                    continue
                lp = item.get("local_path")
                if not lp:
                    continue
                full = Path("extension") / lp
                if not full.exists():
                    continue
                all_targets.append((item, iso2, subs))

    if args.limit:
        all_targets = all_targets[: args.limit]

    print(f"{len(all_targets)} images to OCR", flush=True)

    # Lowercase set for fast contains-check.
    sub_index: dict[str, dict[str, str]] = {}
    for iso2, subs in {iso: KNOWN_SUBDIVISIONS[iso] for iso in {t[1] for t in all_targets}}.items():
        sub_index[iso2] = {s.lower(): s for s in subs if len(s) >= 3}

    n_with_match = 0
    for i, (item, iso2, _subs) in enumerate(all_targets, 1):
        full = Path("extension") / item["local_path"]
        try:
            results = reader.readtext(str(full), detail=0, paragraph=False)
        except Exception as e:
            print(f"  [{i}/{len(all_targets)}] ocr fail {full.name}: {e}", flush=True)
            item["ocr_done"] = True
            item["ocr_text"] = []
            item["ocr_regions"] = []
            continue
        text_blob = " ".join(results)
        item["ocr_text"] = results
        # Match each substring against KNOWN_SUBDIVISIONS for this country.
        idx = sub_index[iso2]
        matched: list[str] = []
        text_lower = text_blob.lower()
        for sub_lc, sub_orig in idx.items():
            if re.search(r"\b" + re.escape(sub_lc) + r"\b", text_lower):
                matched.append(sub_orig)
        item["ocr_regions"] = matched
        item["ocr_done"] = True
        if matched:
            n_with_match += 1
        if i % 25 == 0 or i == len(all_targets):
            print(f"  [{i}/{len(all_targets)}] {full.name[:40]} -> {matched}", flush=True)
            # Save progress periodically.
            plonkit_path.write_text(
                json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    plonkit_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"done. {n_with_match}/{len(all_targets)} images matched a known subdivision.")


if __name__ == "__main__":
    main()
