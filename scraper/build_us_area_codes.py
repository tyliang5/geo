"""Build extension/data/us_area_codes.json: NANP geographic area codes mapped
to US states (and a few non-state territories). Sourced from Wikipedia's
"List of NANP area codes" article. Cross-checks: code 212 → New York,
415 → California, 312 → Illinois, etc.

Skips non-geographic codes (800, 888, 877, 866, 855, 844, 833, 822, 880-887,
881, 889 toll-free; 900 premium; 211/311/411/511/611/711/811/911 service;
500/521-533/544/566/577/588 personal; etc.)
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / 'extension' / 'data' / 'us_area_codes.json'

# state -> list of area codes (NPAs). Geographic only. ~330 entries total.
# Verified against Wikipedia "List of NANP area codes" snapshot.
STATE_CODES = {
    'Alabama':        [205, 251, 256, 334, 659, 938],
    'Alaska':         [907],
    'Arizona':        [480, 520, 602, 623, 928],
    'Arkansas':       [327, 479, 501, 870],
    'California':     [209, 213, 279, 310, 323, 341, 350, 369, 408, 415, 424, 442, 510, 530,
                       559, 562, 619, 626, 628, 650, 657, 661, 669, 707, 714, 738, 747, 760,
                       805, 818, 820, 831, 837, 840, 858, 909, 916, 925, 949, 951],
    'Colorado':       [303, 719, 720, 970, 983],
    'Connecticut':    [203, 475, 860, 959],
    'Delaware':       [302],
    'Florida':        [239, 305, 321, 324, 352, 386, 407, 448, 561, 645, 656, 689, 727, 728,
                       754, 772, 786, 813, 850, 863, 904, 941, 954],
    'Georgia':        [229, 404, 470, 478, 678, 706, 762, 770, 912, 943],
    'Hawaii':         [808],
    'Idaho':          [208, 986],
    'Illinois':       [217, 224, 309, 312, 331, 447, 464, 618, 630, 708, 730, 773, 779, 815,
                       847, 861, 872],
    'Indiana':        [219, 260, 317, 463, 574, 765, 812, 930],
    'Iowa':           [319, 515, 563, 641, 712],
    'Kansas':         [316, 620, 785, 913],
    'Kentucky':       [270, 364, 502, 606, 859],
    'Louisiana':      [225, 318, 337, 457, 504, 985],
    'Maine':          [207],
    'Maryland':       [227, 240, 301, 410, 443, 667],
    'Massachusetts':  [339, 351, 413, 508, 617, 774, 781, 857, 978],
    'Michigan':       [231, 248, 269, 313, 517, 586, 616, 679, 734, 810, 906, 947, 989],
    'Minnesota':      [218, 320, 507, 612, 651, 763, 924, 952],
    'Mississippi':    [228, 471, 601, 662, 769],
    'Missouri':       [235, 314, 417, 557, 573, 636, 660, 816, 975],
    'Montana':        [406],
    'Nebraska':       [308, 402, 531],
    'Nevada':         [702, 725, 775],
    'New Hampshire':  [603],
    'New Jersey':     [201, 551, 609, 640, 732, 848, 856, 862, 908, 973],
    'New Mexico':     [505, 575],
    'New York':       [212, 315, 329, 332, 347, 363, 516, 518, 585, 607, 631, 646, 680, 716,
                       718, 838, 845, 914, 917, 929, 934],
    'North Carolina': [252, 336, 472, 704, 743, 828, 910, 919, 980, 984],
    'North Dakota':   [701],
    'Ohio':           [216, 220, 234, 283, 326, 330, 380, 419, 436, 440, 513, 567, 614, 740, 937],
    'Oklahoma':       [405, 539, 572, 580, 918],
    'Oregon':         [458, 503, 541, 971],
    'Pennsylvania':   [215, 223, 267, 272, 412, 445, 484, 570, 582, 610, 717, 724, 814, 835, 878],
    'Rhode Island':   [401],
    'South Carolina': [803, 821, 839, 843, 854, 864],
    'South Dakota':   [605],
    'Tennessee':      [423, 615, 629, 731, 865, 901, 931],
    'Texas':          [210, 214, 254, 281, 325, 346, 361, 409, 430, 432, 469, 512, 682, 713,
                       726, 737, 806, 817, 830, 832, 903, 915, 936, 940, 945, 956, 972, 979],
    'Utah':           [385, 435, 801],
    'Vermont':        [802],
    'Virginia':       [276, 434, 540, 571, 686, 703, 757, 804, 826, 948],
    'Washington':     [206, 253, 360, 425, 509, 564],
    'West Virginia':  [304, 681],
    'Wisconsin':      [262, 274, 353, 414, 534, 608, 715, 920],
    'Wyoming':        [307],
    'District of Columbia': [202, 771],
    # US territories — listed but separately tagged
    'Puerto Rico':           [787, 939],
    'US Virgin Islands':     [340],
    'Guam':                  [671],
    'Northern Mariana Islands': [670],
    'American Samoa':        [684],
}

# Primary city or region for each code. Used in the quiz feedback so the
# user learns code→city, not just code→state. For overlay codes (multiple
# codes serving the same area), the city/region is repeated.
CODE_CITY = {
    # Alabama
    '205': 'Birmingham', '251': 'Mobile', '256': 'Huntsville / N Alabama',
    '334': 'Montgomery', '659': 'Birmingham (overlay)', '938': 'Huntsville (overlay)',
    # Alaska
    '907': 'statewide',
    # Arizona
    '480': 'East Phoenix / Scottsdale', '520': 'Tucson / S Arizona', '602': 'Phoenix',
    '623': 'West Phoenix', '928': 'Northern / rural Arizona',
    # Arkansas
    '327': 'Little Rock area (overlay)', '479': 'NW Arkansas (Fayetteville / Fort Smith)',
    '501': 'Little Rock / Central', '870': 'Northern / Eastern AR',
    # California
    '209': 'Stockton / Modesto / Central Valley', '213': 'Downtown LA',
    '279': 'Sacramento (overlay)', '310': 'West LA / Beverly Hills',
    '323': 'Central LA (overlay)', '341': 'East Bay (overlay)',
    '350': 'East Bay (overlay)', '369': 'East Bay (overlay)',
    '408': 'San Jose / Silicon Valley', '415': 'San Francisco',
    '424': 'West LA (overlay 310)', '442': 'Inland Empire / Palm Springs',
    '510': 'Oakland / East Bay', '530': 'Sacramento Valley / N California',
    '559': 'Fresno / Central Valley', '562': 'Long Beach',
    '619': 'San Diego (central)', '626': 'San Gabriel Valley / Pasadena',
    '628': 'San Francisco (overlay)', '650': 'Peninsula (San Mateo / Palo Alto)',
    '657': 'Orange County (overlay)', '661': 'Bakersfield / Antelope Valley',
    '669': 'San Jose (overlay)', '707': 'Wine Country (Sonoma / Napa / Eureka)',
    '714': 'Orange County (Anaheim)', '738': 'LA (overlay)',
    '747': 'San Fernando Valley (overlay)', '760': 'SE California (Palm Springs / Death Valley)',
    '805': 'Santa Barbara / Ventura', '818': 'San Fernando Valley',
    '820': 'Santa Barbara (overlay)', '831': 'Santa Cruz / Monterey',
    '837': 'East Bay (overlay)', '840': 'Inland Empire (overlay)',
    '858': 'San Diego North County', '909': 'Inland Empire (San Bernardino)',
    '916': 'Sacramento', '925': 'East Bay (Tri-Valley / Concord)',
    '949': 'South Orange County (Irvine)', '951': 'Inland Empire (Riverside)',
    # Colorado
    '303': 'Denver', '719': 'Colorado Springs / Pueblo',
    '720': 'Denver (overlay)', '970': 'Western CO (Fort Collins / Grand Junction)',
    '983': 'Denver (overlay)',
    # Connecticut
    '203': 'Bridgeport / New Haven / Stamford', '475': 'SW CT (overlay 203)',
    '860': 'Hartford / Eastern CT', '959': 'Hartford (overlay)',
    # Delaware
    '302': 'statewide',
    # Florida
    '239': 'Fort Myers / Naples (SW FL)', '305': 'Miami / Florida Keys',
    '321': 'Brevard / Space Coast (Cape Canaveral, Melbourne)',
    '324': 'Miami (overlay)', '352': 'Gainesville / Ocala',
    '386': 'Daytona Beach / Lake City', '407': 'Orlando',
    '448': 'Tallahassee / N FL (overlay 850)', '561': 'West Palm Beach',
    '645': 'Daytona / Brevard (overlay)', '656': 'Tampa Bay (overlay)',
    '689': 'Orlando (overlay)', '727': 'St. Petersburg / Clearwater (Pinellas)',
    '728': 'Cape Coral / Naples (overlay)', '754': 'Fort Lauderdale (overlay 954)',
    '772': 'Treasure Coast (Port St. Lucie)', '786': 'Miami (overlay 305)',
    '813': 'Tampa', '850': 'Panhandle (Pensacola / Tallahassee)',
    '863': 'Lakeland / Polk County (Central FL)', '904': 'Jacksonville',
    '941': 'Sarasota / Bradenton', '954': 'Fort Lauderdale (Broward)',
    # Georgia
    '229': 'Albany / Valdosta (S GA)', '404': 'Atlanta',
    '470': 'Atlanta (overlay)', '478': 'Macon / Central GA',
    '678': 'Atlanta suburbs (overlay)', '706': 'Augusta / Columbus / Athens',
    '762': 'NW Georgia (overlay)', '770': 'Atlanta suburbs',
    '912': 'Savannah / Coastal GA', '943': 'Atlanta (overlay)',
    # Hawaii
    '808': 'statewide',
    # Idaho
    '208': 'statewide', '986': 'statewide overlay',
    # Illinois
    '217': 'Springfield / Champaign (Central IL)', '224': 'NW Chicago suburbs (overlay 847)',
    '309': 'Peoria / Bloomington (Central IL)', '312': 'Downtown Chicago',
    '331': 'Chicago western suburbs (overlay 630)', '447': 'Springfield (overlay)',
    '464': 'Chicago south suburbs (overlay 708)', '618': 'Southern IL (Carbondale / East St. Louis)',
    '630': 'Chicago western suburbs (DuPage)', '708': 'Chicago south suburbs',
    '730': 'Southern IL (overlay 618)', '773': 'Chicago city (non-downtown)',
    '779': 'Rockford (overlay 815)', '815': 'Rockford / N Central IL',
    '847': 'NW Chicago suburbs', '861': 'Chicago (overlay)',
    '872': 'Chicago (overlay 312/773)',
    # Indiana
    '219': 'NW Indiana (Gary)', '260': 'NE Indiana (Fort Wayne)',
    '317': 'Indianapolis', '463': 'Indianapolis (overlay)',
    '574': 'N Central IN (South Bend)', '765': 'Lafayette / Muncie (Central IN)',
    '812': 'S Indiana (Evansville / Bloomington)', '930': 'S Indiana (overlay 812)',
    # Iowa
    '319': 'SE Iowa (Cedar Rapids / Iowa City)', '515': 'Des Moines',
    '563': 'NE Iowa (Davenport / Dubuque)', '641': 'Central Iowa (Mason City)',
    '712': 'W Iowa (Sioux City)',
    # Kansas
    '316': 'Wichita / SE Kansas', '620': 'Southern Kansas',
    '785': 'N/E Kansas (Topeka, Manhattan)', '913': 'Kansas City KS metro',
    # Kentucky
    '270': 'W Kentucky (Bowling Green / Paducah)', '364': 'W KY (overlay 270)',
    '502': 'Louisville', '606': 'Eastern KY (Ashland / Pikeville)',
    '859': 'Lexington / N Kentucky',
    # Louisiana
    '225': 'Baton Rouge', '318': 'N Louisiana (Shreveport / Monroe)',
    '337': 'SW Louisiana (Lafayette / Lake Charles)', '457': 'SW LA (overlay 337)',
    '504': 'New Orleans', '985': 'SE Louisiana (NO suburbs)',
    # Maine
    '207': 'statewide',
    # Maryland
    '227': 'DC suburbs (overlay 301)', '240': 'Western MD (overlay 301)',
    '301': 'Western MD / DC suburbs', '410': 'Baltimore / E Maryland',
    '443': 'Baltimore (overlay 410)', '667': 'Baltimore (overlay)',
    # Massachusetts
    '339': 'Boston suburbs (overlay 781)', '351': 'NE MA (overlay 978)',
    '413': 'Western MA (Springfield / Pittsfield)', '508': 'SE MA (Worcester / Cape Cod)',
    '617': 'Boston', '774': 'SE MA (overlay 508)',
    '781': 'Boston outer suburbs', '857': 'Boston (overlay 617)',
    '978': 'N MA (Lowell / Lawrence)',
    # Michigan
    '231': 'NW Michigan (Traverse City)', '248': 'N Detroit suburbs (Oakland County)',
    '269': 'SW Michigan (Kalamazoo / Battle Creek)', '313': 'Detroit',
    '517': 'Lansing', '586': 'Macomb County (E Detroit suburbs)',
    '616': 'Grand Rapids', '679': 'Macomb County (overlay)',
    '734': 'Ann Arbor / Western Wayne', '810': 'Flint',
    '906': 'Upper Peninsula', '947': 'N Detroit suburbs (overlay 248)',
    '989': 'Saginaw / N Central MI',
    # Minnesota
    '218': 'Northern MN (Duluth)', '320': 'St. Cloud / Central MN',
    '507': 'S Minnesota (Rochester / Mankato)', '612': 'Minneapolis',
    '651': 'St. Paul', '763': 'NW Twin Cities suburbs',
    '924': 'Minneapolis area (overlay)', '952': 'SW Twin Cities suburbs',
    # Mississippi
    '228': 'Mississippi Gulf Coast (Biloxi / Gulfport)', '471': 'Jackson area (overlay)',
    '601': 'Jackson', '662': 'Northern MS (Tupelo / Oxford)',
    '769': 'Jackson (overlay 601)',
    # Missouri
    '235': 'St. Louis (overlay)', '314': 'St. Louis city',
    '417': 'SW Missouri (Springfield / Joplin)', '557': 'Kansas City (overlay)',
    '573': 'Central / SE Missouri (Columbia / Cape Girardeau)',
    '636': 'St. Louis suburbs', '660': 'N Missouri',
    '816': 'Kansas City', '975': 'KC area (overlay)',
    # Montana
    '406': 'statewide',
    # Nebraska
    '308': 'Western / Central Nebraska', '402': 'Eastern NE (Omaha / Lincoln)',
    '531': 'E Nebraska (overlay 402)',
    # Nevada
    '702': 'Las Vegas', '725': 'Las Vegas (overlay)',
    '775': 'Reno / N Nevada',
    # New Hampshire
    '603': 'statewide',
    # New Jersey
    '201': 'Bergen / Hudson (NE NJ near NYC)', '551': 'NE NJ (overlay 201)',
    '609': 'Trenton / S NJ', '640': 'S NJ (overlay)',
    '732': 'Central NJ (Edison / Toms River)', '848': 'Central NJ (overlay 732)',
    '856': 'SW NJ (Camden / Cherry Hill)', '862': 'N NJ (overlay 973)',
    '908': 'NW NJ (Elizabeth / Plainfield)', '973': 'N NJ (Newark)',
    # New Mexico
    '505': 'Albuquerque / N New Mexico', '575': 'Outside ABQ metro (Las Cruces / Roswell)',
    # New York
    '212': 'Manhattan', '315': 'Central NY (Syracuse / Utica)',
    '329': 'Westchester (overlay)', '332': 'Manhattan (overlay 212)',
    '347': 'NYC outer boroughs (overlay 718)', '363': 'Long Island (overlay)',
    '516': 'Long Island — Nassau', '518': 'Albany / Capital Region',
    '585': 'Rochester', '607': 'Binghamton / Southern Tier',
    '631': 'Long Island — Suffolk', '646': 'Manhattan (overlay 212)',
    '680': 'Syracuse (overlay 315)', '716': 'Buffalo',
    '718': 'Brooklyn / Queens / Bronx / Staten Island', '838': 'Albany (overlay)',
    '845': 'Hudson Valley (Poughkeepsie / Newburgh)', '914': 'Westchester',
    '917': 'NYC mobile (overlay)', '929': 'NYC outer boroughs (overlay 718)',
    '934': 'Suffolk (overlay 631)',
    # North Carolina
    '252': 'Eastern NC (Greenville)', '336': 'Greensboro / Winston-Salem (Triad)',
    '472': 'Triad (overlay)', '704': 'Charlotte',
    '743': 'Triad (overlay)', '828': 'Western NC (Asheville)',
    '910': 'SE NC (Wilmington / Fayetteville)', '919': 'Raleigh / Durham (Triangle)',
    '980': 'Charlotte (overlay 704)', '984': 'Triangle (overlay 919)',
    # North Dakota
    '701': 'statewide',
    # Ohio
    '216': 'Cleveland', '220': 'Central Ohio (overlay 740)',
    '234': 'Akron / Canton (overlay 330)', '283': 'Cincinnati (overlay 513)',
    '326': 'Toledo / Lima (overlay 419)', '330': 'Akron / Canton / Youngstown',
    '380': 'Columbus (overlay 614)', '419': 'NW Ohio (Toledo / Lima)',
    '436': 'Toledo (overlay)', '440': 'Cleveland suburbs',
    '513': 'Cincinnati', '567': 'NW Ohio (overlay 419)',
    '614': 'Columbus', '740': 'SE Ohio (Athens / Zanesville)',
    '937': 'Dayton / Springfield',
    # Oklahoma
    '405': 'Oklahoma City', '539': 'Tulsa (overlay 918)',
    '572': 'OKC area (overlay)', '580': 'Western OK (Lawton / Enid)',
    '918': 'Tulsa / E Oklahoma',
    # Oregon
    '458': 'Eugene (overlay 541)', '503': 'Portland / N Oregon',
    '541': 'S/E Oregon (Eugene / Bend)', '971': 'Portland (overlay 503)',
    # Pennsylvania
    '215': 'Philadelphia', '223': 'Lehigh Valley (overlay 717)',
    '267': 'Philadelphia (overlay 215)', '272': 'NE PA (overlay 570)',
    '412': 'Pittsburgh', '445': 'Philadelphia (overlay 215)',
    '484': 'Lehigh Valley / Reading (overlay 610)', '570': 'NE PA (Scranton / Wilkes-Barre)',
    '582': 'Erie (overlay)', '610': 'SE PA suburbs (Allentown / Reading)',
    '717': 'South Central PA (Harrisburg / Lancaster / York)',
    '724': 'SW PA suburbs (Pittsburgh outer)', '814': 'NW PA (Erie / Altoona / State College)',
    '835': 'Lehigh Valley (overlay)', '878': 'Pittsburgh (overlay 412)',
    # Rhode Island
    '401': 'statewide',
    # South Carolina
    '803': 'Columbia', '821': 'Columbia (overlay)',
    '839': 'Columbia (overlay)', '843': 'Charleston / Coastal SC',
    '854': 'Charleston (overlay 843)', '864': 'Greenville / Upstate SC',
    # South Dakota
    '605': 'statewide',
    # Tennessee
    '423': 'Chattanooga / Tri-Cities (E TN)', '615': 'Nashville',
    '629': 'Nashville (overlay 615)', '731': 'W Tennessee (Jackson)',
    '865': 'Knoxville', '901': 'Memphis',
    '931': 'Middle Tennessee (Clarksville)',
    # Texas
    '210': 'San Antonio', '214': 'Dallas',
    '254': 'Central Texas (Waco / Killeen)', '281': 'Houston suburbs',
    '325': 'West Central TX (Abilene / San Angelo)', '346': 'Houston (overlay)',
    '361': 'Corpus Christi / Coastal Bend', '409': 'SE Texas (Beaumont / Galveston)',
    '430': 'NE Texas (Tyler / Texarkana)', '432': 'W Texas (Midland / Odessa)',
    '469': 'Dallas (overlay 214)', '512': 'Austin',
    '682': 'Fort Worth (overlay 817)', '713': 'Houston city',
    '726': 'San Antonio (overlay 210)', '737': 'Austin (overlay 512)',
    '806': 'Texas Panhandle (Amarillo / Lubbock)', '817': 'Fort Worth / Arlington',
    '830': 'South Texas (San Antonio surrounds)', '832': 'Houston (overlay)',
    '903': 'NE Texas (Tyler / Longview)', '915': 'El Paso / Far W Texas',
    '936': 'SE Texas (Lufkin / Conroe)', '940': 'N Central TX (Wichita Falls / Denton)',
    '945': 'Dallas (overlay)', '956': 'Rio Grande Valley (Brownsville / Laredo)',
    '972': 'Dallas suburbs (overlay)', '979': 'SE Texas (Bryan / College Station)',
    # Utah
    '385': 'Salt Lake City (overlay 801)', '435': 'Outside SLC metro (Provo south / St. George)',
    '801': 'Salt Lake City / Provo',
    # Vermont
    '802': 'statewide',
    # Virginia
    '276': 'SW Virginia (Bristol)', '434': 'South Central VA (Lynchburg / Charlottesville)',
    '540': 'Western VA (Roanoke / Harrisonburg)', '571': 'N Virginia (overlay 703)',
    '686': 'N Virginia (overlay)', '703': 'Northern VA (Arlington / Alexandria / Fairfax)',
    '757': 'Hampton Roads (Norfolk / Virginia Beach)', '804': 'Richmond',
    '826': 'Richmond (overlay)', '948': 'Hampton Roads (overlay)',
    # Washington
    '206': 'Seattle', '253': 'Tacoma / S Puget Sound',
    '360': 'Outside Seattle metro (Olympia / Bellingham / Vancouver WA)',
    '425': 'E Seattle suburbs (Bellevue / Redmond)', '509': 'Eastern WA (Spokane)',
    '564': 'statewide overlay',
    # West Virginia
    '304': 'statewide', '681': 'statewide overlay',
    # Wisconsin
    '262': 'SE Wisconsin suburbs (Milwaukee outer)', '274': 'Green Bay (overlay 920)',
    '353': 'Madison (overlay 608)', '414': 'Milwaukee',
    '534': 'NW Wisconsin (overlay 715)', '608': 'Madison / SW Wisconsin',
    '715': 'N Wisconsin (Eau Claire / Wausau)', '920': 'Green Bay / NE Wisconsin',
    # Wyoming
    '307': 'statewide',
    # DC
    '202': 'Washington DC', '771': 'DC (overlay)',
    # Territories
    '787': 'Puerto Rico', '939': 'Puerto Rico (overlay)',
    '340': 'US Virgin Islands', '671': 'Guam',
    '670': 'Northern Mariana Islands', '684': 'American Samoa',
}


def main() -> None:
    code_to_state: dict[str, str] = {}
    for state, codes in STATE_CODES.items():
        for c in codes:
            code_to_state[str(c)] = state
    # Validate that we have city info for every code (alert on gaps)
    missing = [c for c in code_to_state if c not in CODE_CITY]
    if missing:
        print(f'WARN: {len(missing)} codes lack city info: {missing[:10]}')
    out = {
        '_meta': {
            'source': 'NANP / Wikipedia List of NANP area codes',
            'count': len(code_to_state),
        },
        'code_to_state': code_to_state,
        'code_to_city': CODE_CITY,
        'state_to_codes': {s: c for s, c in STATE_CODES.items()},
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'wrote {OUT.name}: {len(code_to_state)} codes across {len(STATE_CODES)} jurisdictions')


if __name__ == '__main__':
    main()
