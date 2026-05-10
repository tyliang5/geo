// Meta-focus quiz topic registry. Each topic builds a pool of cards where
// each card has a prompt (image OR text) and a correct answer (country code,
// or set of country codes for multi-answer topics).
//
// Topic shape:
//   id:          stable string id
//   label:       human-readable name
//   group:       grouping in the picker dropdown
//   description: short hover blurb
//   buildPool:   (state) => Card[]
//
// Card shape:
//   img: optional URL (image-based topics)
//   text: optional string (text-card topics, like "+44" or "СТОП")
//   subtext: optional small label below the main text (e.g., "currency code")
//   correctCcs: array — clicking ANY of these countries scores correct
//                       (single-element array for unique answers)
//   description: explanation shown after answer
//   regionRestrict: optional array of cc to limit map to (otherwise all eligible)

// Continents we offer as a tiering filter for big topics. Each entry is
// { key: continent code, label: human-readable name }. The order matches the
// region-groups dropdown so topics appear in a familiar sequence.
const CONTINENT_TIERS = [
  { key: 'EU', label: 'Europe' },
  { key: 'AS', label: 'Asia' },
  { key: 'AF', label: 'Africa' },
  { key: 'NA', label: 'North America' },
  { key: 'SA', label: 'South America' },
  { key: 'OC', label: 'Oceania' },
];

// Wrap a buildPool() call to keep only cards whose answer country is in the
// given set of ISO2 codes. Works for both correctCcs (single-answer) and
// correctSubregionNames (sub-region) cards because it filters by .correctCcs.
function continentFilter(buildPool, continentCcs) {
  const wanted = new Set(continentCcs);
  return (state) => {
    const all = buildPool(state);
    return all.filter(c => {
      const ccs = c.correctCcs || (c.cc ? [c.cc] : []);
      return ccs.some(cc => wanted.has(cc));
    });
  };
}

// Spawn continent-tiered copies of an image-based topic. Returns an array
// containing the original "all" topic FIRST, followed by 6 continent-scoped
// copies. The continent variants share the original's id-prefix so user
// stats / blacklists by cardKey remain compatible.
function tieredImageTopic(id, label, types, description) {
  const all = imageGroupTopic(id, label, 'Visual', types, description);
  const tiers = CONTINENT_TIERS.map(({ key, label: cLabel }) => ({
    id: `${id}_${key.toLowerCase()}`,
    label: `${label} — ${cLabel} only`,
    group: 'Visual (by continent)',
    description: `${description} Filtered to ${cLabel} so you can master one continent at a time before tackling the global pool.`,
    mode: 'image_country',
    buildPool: continentFilter(all.buildPool, REGION_GROUPS_FOR_TIERS[key]),
  }));
  return [all, ...tiers];
}

// Same idea for reference-data text topics (calling code, TLD, capital, …)
function tieredRefTopic(id, label, refField, description, opts = {}) {
  const all = refTopic(id, label, 'Reference data', refField, description, opts);
  const tiers = CONTINENT_TIERS.map(({ key, label: cLabel }) => ({
    id: `${id}_${key.toLowerCase()}`,
    label: `${label} — ${cLabel} only`,
    group: 'Reference data (by continent)',
    description: `${description} Restricted to ${cLabel}.`,
    mode: 'text_country',
    buildPool: continentFilter(all.buildPool, REGION_GROUPS_FOR_TIERS[key]),
  }));
  return [all, ...tiers];
}

// Hand-curated "famous" sets for the starter tiers — the values you'll
// actually encounter most often, picked for memorability rather than
// alphabetical/numerical order.
const STARTER_CALLING_CODES = new Set([
  '+1','+7','+20','+27','+30','+31','+32','+33','+34','+39','+44','+45',
  '+46','+47','+48','+49','+52','+55','+61','+64','+65','+81','+82','+86','+91','+92','+886',
]);
const STARTER_TLDS = new Set([
  '.uk','.de','.fr','.es','.it','.nl','.be','.ch','.at','.se','.no','.dk','.fi','.pl','.cz','.ru',
  '.ca','.mx','.br','.ar','.cl','.co','.pe','.au','.nz','.jp','.kr','.cn','.in','.tw','.hk','.sg','.za',
]);
const STARTER_CAPITALS = new Set([
  'Paris','London','Berlin','Madrid','Rome','Amsterdam','Brussels','Vienna','Bern','Stockholm','Oslo',
  'Copenhagen','Helsinki','Warsaw','Prague','Moscow','Athens','Lisbon','Dublin','Reykjavík',
  'Washington','Ottawa','Mexico City','Brasília','Buenos Aires','Santiago',
  'Tokyo','Seoul','Beijing','New Delhi','Bangkok','Jakarta','Manila','Hanoi','Singapore',
  'Cairo','Pretoria','Nairobi','Canberra','Wellington',
]);

function starterRefTopic(id, label, refField, valueSet, description, opts = {}) {
  return {
    id, label, group: 'Reference data',
    description,
    mode: 'text_country',
    buildPool(state) {
      const ref = state.reference || {};
      const ccsByValue = new Map();
      for (const [cc, r] of Object.entries(ref)) {
        if (cc === '_meta') continue;
        const v = r[refField];
        if (v == null || v === '') continue;
        if (!valueSet.has(v)) continue;
        if (!ccsByValue.has(v)) ccsByValue.set(v, []);
        ccsByValue.get(v).push(cc);
      }
      const cards = [];
      for (const [value, ccs] of ccsByValue) {
        const display = opts.format ? opts.format(value) : value;
        cards.push({
          text: display,
          subtext: opts.subtext || label,
          correctCcs: ccs,
          description: ccs.length > 1 ? `${ccs.length} countries: ${ccs.join(', ')}` : '',
          cardKey: `${id}:${value}`,
        });
      }
      return cards;
    },
  };
}

// Local copy of the continent → ISO2 map (mirrors REGION_GROUPS in app.js).
// Defined here so topics.js stays self-contained.
const REGION_GROUPS_FOR_TIERS = {
  EU: ['AL','AD','AT','BY','BE','BA','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IS','IE','IM','IT','JE','XK','LV','LI','LT','LU','MT','MD','MC','ME','NL','MK','NO','PL','PT','RO','SM','RS','SK','SI','ES','SE','CH','UA','GB','VA','GG','FO','SJ','GI'],
  AS: ['AF','AM','AZ','BH','BD','BT','BN','KH','CN','GE','HK','IN','ID','IR','IQ','IL','JP','JO','KZ','KW','KG','LA','LB','MO','MY','MV','MN','MM','NP','KP','OM','PK','PS','PH','QA','SA','SG','KR','LK','SY','TW','TJ','TH','TL','TR','TM','AE','UZ','VN','YE'],
  AF: ['DZ','AO','BJ','BW','BF','BI','CM','CV','CF','TD','KM','CG','CD','CI','DJ','EG','GQ','ER','SZ','ET','GA','GM','GH','GN','GW','KE','LS','LR','LY','MG','MW','ML','MR','MU','MA','MZ','NA','NE','NG','RW','ST','SN','SC','SL','SO','ZA','SS','SD','TZ','TG','TN','UG','ZM','ZW','EH'],
  NA: ['AG','BS','BB','BZ','CA','CR','CU','DM','DO','SV','GD','GT','HT','HN','JM','MX','NI','PA','KN','LC','VC','TT','US','PR','BM','GP','MQ','GL'],
  SA: ['AR','BO','BR','CL','CO','EC','FK','GF','GY','PY','PE','SR','UY','VE'],
  OC: ['AS','AU','CK','FJ','PF','GU','KI','MH','FM','NR','NC','NZ','MP','PW','PG','WS','SB','TK','TO','TV','VU','WF'],
};

export function buildTopics() {
  return [
    // ---- 📆 Recommended ----
    // Mixes the weakest cards across ALL of your other topics into a single
    // smart pool. Built from per-card stats, sorted by miss-rate. Empty
    // until you've answered enough to have meaningful stats.
    recommendedTopic(),

    // ---- Country flags ----
    // Flag image → click country on map. Always-loaded from flagcdn.com so
    // we don't have to bundle 130+ images. Includes a Starter pack of
    // recognisable flags + 6 continent tiers.
    flagsTopic('country_flags', 'Country flags', null,
      'Identify the country from its flag.'),
    flagsStarterTopic(),
    ...CONTINENT_TIERS.map(({ key, label }) =>
      flagsTopic(`country_flags_${key.toLowerCase()}`,
        `Country flags — ${label} only`, key,
        `Identify the ${label} country from its flag.`)),

    // ---- Image-based topics — pull from existing tips.json metas ----
    // The biggest visual topics also get continent-scoped tiers so you can
    // chunk learning instead of taking on the whole world at once.
    ...tieredImageTopic('bollards', 'Bollards',
      ['Bollard', 'Bollards'],
      'Concrete posts beside roads — distinctive shapes and colours per country.'),
    ...tieredImageTopic('infrastructure', 'Infrastructure (general)',
      ['Infrastructure'],
      'Generic infrastructure clues — railings, signs, surfaces.'),
    ...tieredImageTopic('landscape', 'Landscape (general)',
      ['Landscape'],
      'Generic terrain and biome clues.'),
    ...tieredImageTopic('vegetation', 'Vegetation',
      ['Vegetation', 'Agriculture'],
      'Plants, agriculture, biome.'),
    ...tieredImageTopic('coverage', 'Coverage / camera',
      ['Coverage Meta', 'Trekker', 'Low Cam', 'Gen 3 Autumn'],
      'Street View capture mode (Trekker, gen-2, gen-3).'),
    // Smaller visual topics — global only (no continent tiers since the
    // pool size is already manageable).
    imageGroupTopic('architecture', 'Architecture', 'Visual',
      ['Architecture', 'General Architecture', 'Unique Architecture', 'Stone Buildings', 'Stilt Houses'],
      'Building styles and materials.'),
    imageGroupTopic('chevrons', 'Chevrons', 'Visual',
      ['Chevrons', 'Chevron'],
      'Curve warning markers.'),
    imageGroupTopic('license_plates', 'License plates', 'Visual',
      ['License Plate', 'License Plates', 'Yellow Plates'],
      'Vehicle plate format and colour.'),
    imageGroupTopic('utility_poles', 'Utility poles', 'Visual',
      ['Pole', 'Poles', 'Holey Pole', 'Pair Poles', 'Ladder Poles', 'Pole Marking', 'Nusa Pole', 'Vic Pole Top'],
      'Telephone / power pole styles.'),
    imageGroupTopic('road_lines_visual', 'Road lines (image)', 'Visual',
      ['Roadlines', 'Road Lines', 'Road Line'],
      'Centre and edge line colour patterns on actual roads.'),
    imageGroupTopic('cars', 'Google car / snorkels', 'Visual',
      ['Car Meta', 'Unique Car', 'Snorkel', 'Pickup Car', 'Pickup Truck', 'Follow Car', 'Landscape + Black Car', 'Car'],
      'Distinctive Google Street View vehicle hardware.'),
    imageGroupTopic('km_markers', 'Kilometre markers', 'Visual',
      ['Kilometre Markers', 'Highway Markers', 'Kilometer Markers'],
      'Roadside distance markers.'),

    // ---- Text-card topics from country_facts.json ----
    factTopic('stop_text', 'Stop sign text', 'Slide deck (factual)',
      'stop_text', 'Click any country whose stop sign reads this.',
      { skip: ['STOP'] }),  // skip the boring "STOP" — too many countries
    factTopic('sign_style', 'Sign style', 'Slide deck (factual)',
      'sign_style', 'Click any country with this signage style.',
      { multi: true }),
    factTopic('plate_format', 'Plate format', 'Slide deck (factual)',
      'plate_format', 'Click any country with this license plate format.',
      { multi: true }),
    factTopic('driving_side', 'Driving side', 'Slide deck (factual)',
      'driving_side', 'Click any country that drives on this side.',
      { multi: true }),
    factTopic('road_lines', 'Road lines (categorical)', 'Slide deck (factual)',
      'road_lines', 'Click any country with this road-line scheme.',
      { multi: true }),
    factTopic('chevron_color', 'Chevron colour scheme', 'Slide deck (factual)',
      'chevron_color', 'Click any European country with this chevron colour.',
      { multi: true, regionEU: true }),
    factTopic('ped_stripes', 'Pedestrian sign stripes', 'Slide deck (factual)',
      'ped_stripes', 'Click any European country whose pedestrian sign has this many stripes.',
      { multi: true, regionEU: true, formatNumber: true }),
    factTopic('speed_limit', 'Highway speed limit', 'Slide deck (factual)',
      'speed_limit_max_kmh', 'Click any country with this max highway speed.',
      { multi: true, formatSpeed: true }),

    // ---- Reference-data text topics (country_reference.json) ----
    // The big four (calling code, TLD, capital, currency) get continent
    // tiers AND a "starter" pack of the most-recognized values.
    ...tieredRefTopic('calling_code', 'Calling code',
      'calling_code', 'Click the country with this telephone country code.',
      { format: x => x }),
    starterRefTopic('calling_code_starter', '⭐ Starter — common calling codes',
      'calling_code', STARTER_CALLING_CODES,
      'The 25 calling codes you\'ll most often see (+1, +44, +33, +49, +81…). Anchor your memory on these before tackling all 134.',
      { format: x => x }),
    ...tieredRefTopic('tld', 'Top-level domain',
      'tld', 'Click the country whose ccTLD this is.',
      { format: x => x }),
    starterRefTopic('tld_starter', '⭐ Starter — common TLDs',
      'tld', STARTER_TLDS,
      'The 30 ccTLDs you\'ll see most often (.uk, .de, .jp, .br, .au…).',
      { format: x => x }),
    ...tieredRefTopic('capital', 'Capital city',
      'capital', 'Click the country whose capital is this.',
      { format: x => x }),
    starterRefTopic('capital_starter', '⭐ Starter — famous capitals',
      'capital', STARTER_CAPITALS,
      'The 30 most internationally-recognized capitals (Paris, London, Tokyo, Beijing…).',
      { format: x => x }),
    refTopic('currency_code', 'Currency code', 'Reference data',
      'currency_code', 'Click any country that uses this currency.',
      { multi: true, format: x => x, subtext: 'ISO 4217' }),
    refTopic('currency_symbol', 'Currency symbol', 'Reference data',
      'currency_symbol', 'Click any country that uses this currency symbol.',
      { multi: true, format: x => x }),
    refTopic('iso3', 'ISO 3-letter code', 'Reference data',
      'iso3', 'Click the country with this 3-letter ISO code.',
      { format: x => x, subtext: 'ISO 3166-1 alpha-3' }),
    refTopic('primary_language', 'Primary language', 'Reference data',
      'primary_language', 'Click any country whose primary language is this.',
      { multi: true, format: x => x }),
    refTopicArray('scripts', 'Writing system', 'Reference data',
      'scripts', 'Click any country that uses this script.',
      { multi: true, skip: ['Latin'] }),  // Latin is too common to be useful
    refTopicArray('official_languages', 'Official languages', 'Reference data',
      'official_languages', 'Click any country where this is an official language.',
      { multi: true }),

    // ---- Extras (vehicle nationality codes, mailbox/police colors, phone) ----
    extraTopic('vehicle_oval', 'Vehicle nationality code', 'Extra metas',
      'vehicle_oval', 'The oval sticker / plate code (e.g. D = Germany, F = France).'),
    extraTopic('mailbox_color', 'Mailbox colour', 'Extra metas',
      'mailbox_color', 'Dominant postbox / mailbox colour. Click any country.',
      { multi: true }),
    extraTopic('police_color', 'Police car livery', 'Extra metas',
      'police_color', 'Dominant police vehicle colour scheme. Click any country.',
      { multi: true }),
    extraTopic('phone_format', 'Phone number format', 'Extra metas',
      'phone_format', 'Common written phone-number format pattern.'),

    // ---- Region "what value is used here" multiple-choice ----
    // The prompt is a region label; the user picks the modal value from
    // 6 MC options. Built from the same fact/reference data as above.
    regionMcTopic('mc_stop_text', 'Region → stop sign text', 'Region MC',
      'stop_text', 'fact', 'What stop sign text is most common in this region?',
      { skipIfMixed: false }),
    regionMcTopic('mc_driving_side', 'Region → driving side', 'Region MC',
      'driving_side', 'fact', 'Which side of the road do most countries here drive on?'),
    regionMcTopic('mc_sign_style', 'Region → sign style', 'Region MC',
      'sign_style', 'fact', 'What style of road signs is most common in this region?'),
    regionMcTopic('mc_road_lines', 'Region → road lines', 'Region MC',
      'road_lines', 'fact', 'What road-line scheme is most common here?'),
    regionMcTopic('mc_plate_format', 'Region → plate format', 'Region MC',
      'plate_format', 'fact', 'What license plate format is most common here?'),
    regionMcTopic('mc_speed_limit', 'Region → highway speed limit', 'Region MC',
      'speed_limit_max_kmh', 'fact', 'What max highway speed is most common here?',
      { formatSpeed: true }),
    regionMcTopic('mc_chevron', 'Region → chevron colour', 'Region MC',
      'chevron_color', 'fact', 'What chevron colour scheme is most common in this European region?',
      { regionEU: true }),
    regionMcTopic('mc_currency_code', 'Region → currency code', 'Region MC',
      'currency_code', 'ref', 'Which currency code is most common in this region?'),
    regionMcTopic('mc_currency_symbol', 'Region → currency symbol', 'Region MC',
      'currency_symbol', 'ref', 'Which currency symbol is most common in this region?'),
    regionMcTopic('mc_calling_code', 'Region → calling code prefix', 'Region MC',
      'calling_code', 'ref', 'What calling code is most common in this region?',
      { extractFirstDigit: false }),
    regionMcTopic('mc_primary_language', 'Region → primary language', 'Region MC',
      'primary_language', 'ref', 'What is the most common primary language in this region?'),

    // ---- Reverse mode (country → meta MC) ----
    reverseModeTopic('reverse_eu', 'Europe — pick the meta', 'EU'),
    reverseModeTopic('reverse_as', 'Asia — pick the meta', 'AS'),
    reverseModeTopic('reverse_af', 'Africa — pick the meta', 'AF'),
    reverseModeTopic('reverse_na', 'N. America — pick the meta', 'NA'),
    reverseModeTopic('reverse_sa', 'S. America — pick the meta', 'SA'),
    reverseModeTopic('reverse_oc', 'Oceania — pick the meta', 'OC'),

    // ---- US area codes — graduated learning path ----
    usAreaCodeStarterTopic(),                              // Tier 1 — 25 famous codes
    // 🎯 Smart pools — built from your local card stats. The "weak" pool
    // surfaces codes you keep getting wrong; the "unseen" pool surfaces
    // codes you've never been quizzed on. Together these target EXACTLY
    // what you haven't memorised yet, instead of cycling through the
    // ones you already know.
    usAreaCodeWeakTopic(),
    usAreaCodeUnseenTopic(),
    ...Object.entries(US_REGIONS).map(([region, states]) =>
      usAreaCodeRegionalTopic(region, states)              // Tier 2 — by region
    ),
    // Tier 3 — sub-region chunks. Smaller multi-state geographic clusters
    // (NYC tristate, New England minors, DC metro, etc.) so each chunk
    // genuinely tests code→state recall but the pool stays small enough
    // to memorise in a sitting.
    ...usAreaCodeChunkTopics(),
    usAreaCodeTopic(),                                     // Tier 4 — all 371

    // ---- Per-country area-code quizzes ----
    // Mirrors the US flow for any country that has a plonkit area-code
    // map in country_area_codes.json (KZ, KR, …). Auto-skipped for any
    // cc whose data hasn't been authored yet.
    ...countryAreaCodeTopics(),

    // ---- Compendium quizzes ----
    // For each plonkit reference image we extracted (state flags, road
    // numbers, area codes, bus-stop styles, etc.), one quiz topic per
    // entry in compendium_quizzes.json. The label is shown as text and
    // the user clicks the correct region on the map.
    ...compendiumQuizTopics(),

    // ---- Personal: confused pairs ----
    // Generated from your GG round history (state.personalData). Each card
    // shows two countries and asks you to identify which is which based
    // on a meta image. Falls back to empty pool if no GG data is loaded.
    confusedPairsTopic(),
  ];
}

// ---------- topic builders ----------

// ---- 📆 Recommended quiz ----
// The big shared smart-pool. Cards are pulled from EVERY other topic in
// the registry, scored by your stored accuracy, and the worst-N are
// returned mixed together. So one session blends weak area codes, weak
// flags, weak bollards, etc. — whatever you've actually struggled with.
//
// We have to look up the topic registry at buildPool time (since topics
// are built BEFORE this one in some recursive sense — this function is
// called from inside buildTopics()). To avoid recursion we read
// state.topics if it's been populated, otherwise return [].
function recommendedTopic() {
  return {
    id: 'recommended_mix',
    label: '📆 Recommended (smart mix of your weakest cards)',
    group: '📆 Recommended',
    description: 'Auto-built from your per-card stats. Pulls the cards you keep getting wrong from across ALL other topics — area codes, flags, bollards, languages, you name it. One blended session.',
    mode: 'mixed',     // each card carries its own mode from the source topic
    buildPool(state) {
      let raw = {};
      try { raw = JSON.parse(localStorage.getItem('plonker:card-stats')) || {}; }
      catch {}
      const allTopics = state.topics || [];
      // Map: cardKey -> { card, accuracy, count, lastSeen }
      const candidates = [];
      const seen = new Set();
      for (const t of allTopics) {
        if (t.id === 'recommended_mix') continue;
        if (t.mode === 'mixed') continue;   // skip self / other meta-topics
        let pool;
        try { pool = t.buildPool(state); } catch { continue; }
        if (!pool || !pool.length) continue;
        for (const c of pool) {
          if (!c?.cardKey || seen.has(c.cardKey)) continue;
          const s = raw[c.cardKey];
          if (!s || s.count === 0) continue;     // skip unseen — recommended is review-only
          const accuracy = s.hits / s.count;
          if (accuracy >= 0.85 && s.count >= 3) continue;  // skip mastered
          seen.add(c.cardKey);
          // Tag the card with the source topic's mode + countryCc so the
          // quiz engine knows how to render and grade it.
          candidates.push({
            ...c,
            mode: t.mode,
            topicId: t.id,
            countryCc: t.countryCc || c.countryCc || null,
            type: t.label,
            title: t.label,
            _accuracy: accuracy,
            _count: s.count,
            _lastSeen: s.lastSeen || 0,
          });
        }
      }
      // Sort: lowest accuracy first, ties broken by oldest lastSeen.
      candidates.sort((a, b) =>
        (a._accuracy - b._accuracy) ||
        (a._lastSeen - b._lastSeen)
      );
      return candidates.slice(0, 40);
    },
  };
}

// ---- Country flags ----
// Flag image → click country. Hand-curated starter set of the most
// recognisable flags, plus a "famous" pack you can begin with.
const STARTER_FLAGS = new Set([
  'US','CA','MX','BR','AR','CL','CO','CU','JM',
  'GB','IE','FR','DE','IT','ES','PT','NL','BE','CH','AT','GR','SE','NO','DK','FI','IS','PL','RU','UA',
  'JP','KR','CN','IN','TH','VN','ID','PH','MY','SG','TR','IL','SA','AE',
  'EG','MA','ZA','KE','NG',
  'AU','NZ',
]);

function flagsTopic(id, label, continentKey, description) {
  return {
    id, label,
    group: continentKey ? 'Country flags (by continent)' : 'Country flags',
    description,
    mode: 'image_country',
    buildPool(state) {
      const allowed = continentKey
        ? new Set(REGION_GROUPS_FOR_TIERS[continentKey])
        : null;
      const cards = [];
      for (const cc of state.countries) {
        if (allowed && !allowed.has(cc)) continue;
        const name = state.tips[cc]?.name
                  || state.reference?.[cc]?.name
                  || cc;
        cards.push({
          // flagcdn.com serves CC-keyed flag PNGs at any width. w320 keeps
          // each file ~10kB so 132 cards load fast.
          img: `https://flagcdn.com/w320/${cc.toLowerCase()}.png`,
          correctCcs: [cc],
          description: `${name} (${cc}).`,
          cardKey: `country_flag:${cc}`,
        });
      }
      return cards;
    },
  };
}

function flagsStarterTopic() {
  return {
    id: 'country_flags_starter',
    label: '⭐ Starter — famous flags',
    group: 'Country flags',
    description: 'The 50 most internationally-recognised flags. Start here before tackling the full set.',
    mode: 'image_country',
    buildPool(state) {
      const cards = [];
      for (const cc of state.countries) {
        if (!STARTER_FLAGS.has(cc)) continue;
        const name = state.tips[cc]?.name
                  || state.reference?.[cc]?.name
                  || cc;
        cards.push({
          img: `https://flagcdn.com/w320/${cc.toLowerCase()}.png`,
          correctCcs: [cc],
          description: `${name} (${cc}).`,
          cardKey: `country_flag:${cc}`,   // unify stats with the main flags pool
        });
      }
      return cards;
    },
  };
}

function imageGroupTopic(id, label, group, types, description) {
  return {
    id, label, group, description,
    mode: 'image_country',
    buildPool(state) {
      const wanted = new Set(types.map(t => t.toLowerCase()));
      const cards = [];
      for (const [cc, c] of Object.entries(state.tips)) {
        if (cc === '_meta') continue;
        const metas = c.metas || [];
        for (let i = 0; i < metas.length; i++) {
          const m = metas[i];
          if (!(m.images || [])[0]) continue;
          if (!wanted.has((m.type || '').toLowerCase())) continue;
          cards.push({
            img: m.images[0],
            correctCcs: [cc],
            description: m.description || '',
            // Use the original meta index so the OCR-detected blacklist
            // (keyed `country:CC:i`) lines up with topic-mode cards.
            cardKey: `country:${cc}:${i}`,
          });
        }
      }
      return cards;
    },
  };
}

function factTopic(id, label, group, factField, description, opts = {}) {
  return {
    id, label, group, description,
    mode: 'text_country',
    buildPool(state) {
      const facts = state.facts || {};
      const ccsByValue = new Map();
      for (const [cc, f] of Object.entries(facts)) {
        if (cc === '_meta') continue;
        const v = f[factField];
        if (v == null || v === '') continue;
        if (opts.skip && opts.skip.includes(v)) continue;
        if (opts.regionEU && !state.regionGroups.EU.includes(cc)) continue;
        if (!ccsByValue.has(v)) ccsByValue.set(v, []);
        ccsByValue.get(v).push(cc);
      }
      const cards = [];
      for (const [value, ccs] of ccsByValue) {
        let display = String(value);
        if (opts.formatSpeed) display = `${value} km/h`;
        if (opts.formatNumber) display = `${value} stripes`;
        // For non-multi topics, only emit cards where exactly one country matches
        if (!opts.multi && ccs.length !== 1) continue;
        cards.push({
          text: display,
          subtext: label,
          correctCcs: ccs,
          description: ccs.length > 1
            ? `Countries: ${ccs.join(', ')}`
            : '',
          cardKey: `${id}:${value}`,
        });
      }
      return cards;
    },
  };
}

function refTopic(id, label, group, refField, description, opts = {}) {
  return {
    id, label, group, description,
    mode: 'text_country',
    buildPool(state) {
      const ref = state.reference || {};
      const ccsByValue = new Map();
      for (const [cc, r] of Object.entries(ref)) {
        if (cc === '_meta') continue;
        const v = r[refField];
        if (v == null || v === '') continue;
        if (opts.skip && opts.skip.includes(v)) continue;
        if (!ccsByValue.has(v)) ccsByValue.set(v, []);
        ccsByValue.get(v).push(cc);
      }
      const cards = [];
      for (const [value, ccs] of ccsByValue) {
        const display = opts.format ? opts.format(value) : value;
        if (!opts.multi && ccs.length !== 1) continue;
        cards.push({
          text: display,
          subtext: opts.subtext || label,
          correctCcs: ccs,
          description: ccs.length > 1 ? `${ccs.length} countries: ${ccs.join(', ')}` : '',
          cardKey: `${id}:${value}`,
        });
      }
      return cards;
    },
  };
}

function refTopicArray(id, label, group, refField, description, opts = {}) {
  return {
    id, label, group, description,
    mode: 'text_country',
    buildPool(state) {
      const ref = state.reference || {};
      const ccsByValue = new Map();
      for (const [cc, r] of Object.entries(ref)) {
        if (cc === '_meta') continue;
        const arr = r[refField] || [];
        for (const v of arr) {
          if (opts.skip && opts.skip.includes(v)) continue;
          if (!ccsByValue.has(v)) ccsByValue.set(v, []);
          ccsByValue.get(v).push(cc);
        }
      }
      const cards = [];
      for (const [value, ccs] of ccsByValue) {
        if (!opts.multi && ccs.length !== 1) continue;
        cards.push({
          text: value,
          subtext: opts.subtext || label,
          correctCcs: [...new Set(ccs)],
          description: ccs.length > 1 ? `${ccs.length} countries: ${[...new Set(ccs)].join(', ')}` : '',
          cardKey: `${id}:${value}`,
        });
      }
      return cards;
    },
  };
}

// ---------- region MC topic ----------
// For each region group, compute the modal (most-common) value of the given
// fact/reference field. Emits one MC card per region where the modal value
// covers >= 50% of countries with data in the region.
const REGION_MC_LABELS = {
  // Continents
  EU: 'Europe', AS: 'Asia', AF: 'Africa', NA: 'North America', SA: 'South America', OC: 'Oceania',
  // Sub-regions (label key matches REGION_GROUPS keys)
  baltic: 'Baltics',
  nordic: 'Nordics',
  scandinavia: 'Scandinavia (NO/SE/DK)',
  balkan: 'Balkans',
  iberia: 'Iberia',
  benelux: 'Benelux',
  dach: 'DACH (German-speaking)',
  visegrad: 'Visegrád (PL/CZ/SK/HU)',
  'central-eu': 'Central Europe',
  'western-eu': 'Western Europe',
  'eastern-eu': 'Eastern Europe',
  'southern-eu': 'Southern Europe',
  'british-isles': 'British Isles',
  mediterranean: 'Mediterranean',
  'former-yugoslavia': 'Former Yugoslavia',
  subcontinent: 'Indian subcontinent',
  'east-asia': 'East Asia',
  'mainland-sea': 'Mainland SE Asia',
  'maritime-sea': 'Maritime SE Asia',
  'se-asia': 'SE Asia',
  stans: 'Central Asia / Stans',
  caucasus: 'Caucasus',
  levant: 'Levant',
  'arabian-peninsula': 'Arabian Peninsula',
  maghreb: 'Maghreb / N Africa',
  'horn-of-africa': 'Horn of Africa',
  'east-africa': 'East Africa',
  'southern-africa': 'Southern Africa',
  'west-africa': 'West Africa',
  'central-africa': 'Central Africa',
  'central-america': 'Central America',
  caribbean: 'Caribbean',
  andean: 'Andean',
  'southern-cone': 'Southern Cone',
  latam: 'Latin America',
  'anglo-america': 'Anglo America (US/CA)',
};

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function regionMcTopic(id, label, group, field, source, description, opts = {}) {
  // We need access to REGION_GROUPS at build time; topics.js doesn't import
  // it but state.regionGroups is set up by app.js's loadAll().
  return {
    id, label, group, description,
    mode: 'mc_text',
    buildPool(state) {
      const REGION_GROUPS = state.regionGroups || {};
      const dataset = source === 'ref' ? (state.reference || {}) : (state.facts || {});
      // Collect all distinct values across all countries (for MC distractors)
      const allValues = new Set();
      for (const [cc, row] of Object.entries(dataset)) {
        if (cc === '_meta') continue;
        const v = row?.[field];
        if (v != null && v !== '') allValues.add(v);
      }

      const formatVal = (v) => {
        if (opts.formatSpeed) return `${v} km/h`;
        return String(v);
      };

      const cards = [];
      for (const [regionKey, regionLabel] of Object.entries(REGION_MC_LABELS)) {
        const ccs = REGION_GROUPS[regionKey] || [];
        if (!ccs.length) continue;
        if (opts.regionEU && !REGION_GROUPS.EU.includes(ccs[0])) continue;

        // Aggregate values for countries in this region
        const counts = {};
        let totalKnown = 0;
        for (const cc of ccs) {
          const v = dataset[cc]?.[field];
          if (v == null || v === '') continue;
          counts[v] = (counts[v] || 0) + 1;
          totalKnown++;
        }
        if (totalKnown < 3) continue;  // skip tiny regions
        const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
        const [topVal, topCount] = sorted[0];
        if (topCount / totalKnown < 0.5 && !opts.skipIfMixed === false) continue;

        // Build MC options: top value + 5 distractors picked from other values
        // first within the dataset, then if not enough, pad with random others.
        const otherVals = [...allValues].filter(v => v !== topVal);
        const distractors = shuffle(otherVals).slice(0, 5);
        const options = shuffle([topVal, ...distractors]);

        cards.push({
          text: regionLabel,
          subtext: description,
          options: options.map(formatVal),
          correctOption: formatVal(topVal),
          highlightCcs: ccs,
          description: `Modal answer in this region: ${formatVal(topVal)} (${topCount} of ${totalKnown} countries with data).`,
          cardKey: `${id}:${regionKey}`,
        });
      }
      return cards;
    },
  };
}

// ---------- Extras (meta_extras.json) ----------
function extraTopic(id, label, group, field, description, opts = {}) {
  return {
    id, label, group, description,
    mode: 'text_country',
    buildPool(state) {
      const extras = state.extras || {};
      const ccsByValue = new Map();
      for (const [cc, e] of Object.entries(extras)) {
        if (cc === '_meta') continue;
        const v = e?.[field];
        if (v == null || v === '') continue;
        if (!ccsByValue.has(v)) ccsByValue.set(v, []);
        ccsByValue.get(v).push(cc);
      }
      const cards = [];
      for (const [value, ccs] of ccsByValue) {
        if (!opts.multi && ccs.length !== 1) continue;
        cards.push({
          text: String(value),
          subtext: label,
          correctCcs: ccs,
          description: ccs.length > 1 ? `${ccs.length} countries: ${ccs.join(', ')}` : '',
          cardKey: `${id}:${value}`,
        });
      }
      return cards;
    },
  };
}

// ---------- Confused pairs (from your GG history) ----------
function confusedPairsTopic() {
  return {
    id: 'confused_pairs',
    label: 'Your confused pairs',
    group: 'Personal (from your data)',
    description: 'Cards from countries you frequently mix up — built from your imported GG rounds.',
    mode: 'image_country',
    buildPool(state) {
      const pairs = state.personalData?.['confused-pairs']?.pairs || {};
      // Build a pool of meta images from any country involved in a >=2x pair.
      const involved = new Set();
      for (const [k, n] of Object.entries(pairs)) {
        if (n < 2) continue;
        const [a, g] = k.split('->');
        involved.add(a); involved.add(g);
      }
      const cards = [];
      for (const cc of involved) {
        const c = state.tips[cc];
        if (!c?.metas?.length) continue;
        for (const m of c.metas) {
          if (!(m.images || [])[0]) continue;
          cards.push({
            img: m.images[0],
            correctCcs: [cc],
            description: m.description || '',
            cardKey: `confused:${cc}:${cards.length}`,
          });
        }
      }
      return cards;
    },
  };
}

// ---------- Reverse mode topics (country → MC of metas) ----------
// For each country, build a card whose prompt is the country flag/name and
// the MC options are short DESCRIPTIVE meta titles (not generic types).
// Distractors are picked from other countries' metas, avoiding any title
// that's too generic ("Bollard", "Region", "Architecture") since those
// exist in many countries and teach nothing.

// Words/phrases that are too generic to test on their own.
const GENERIC_TITLE_WORDS = new Set([
  'bollard', 'bollards', 'region', 'architecture', 'landscape', 'infrastructure',
  'vegetation', 'pole', 'poles', 'coverage', 'meta', 'sign', 'signs', 'plate',
  'plates', 'general', 'misc', 'other', 'car', 'cars', 'trekker', 'vibes',
  'roadlines', 'road lines', 'chevrons', 'curbs', 'agriculture',
]);

function isSpecificTitle(title) {
  if (!title) return false;
  const trimmed = title.trim();
  if (trimmed.length < 10 || trimmed.length > 80) return false;
  const lower = trimmed.toLowerCase();
  // Reject if the entire title is just a generic word
  if (GENERIC_TITLE_WORDS.has(lower)) return false;
  // Need at least 2 words to be specific
  if (trimmed.split(/\s+/).length < 2) return false;
  return true;
}

function reverseModeTopic(id, label, continentKey) {
  return {
    id, label, group: 'Reverse (country → meta)',
    description: 'See a country, pick which descriptive meta belongs to it.',
    mode: 'mc_text',
    buildPool(state) {
      const REGION_GROUPS = state.regionGroups || {};
      const ccs = REGION_GROUPS[continentKey] || [];
      // Collect specific meta titles per country
      const countryMetas = {};
      const allMetas = [];   // {cc, title, type}
      for (const cc of ccs) {
        const c = state.tips[cc];
        if (!c?.metas?.length) continue;
        const metas = [];
        const seenTitles = new Set();
        for (const m of c.metas) {
          if (!(m.images || [])[0]) continue;
          const title = m.title || m.type;
          if (!isSpecificTitle(title)) continue;
          const key = title.toLowerCase().trim();
          if (seenTitles.has(key)) continue;
          seenTitles.add(key);
          metas.push({ title: title.trim(), type: m.type });
        }
        if (!metas.length) continue;
        countryMetas[cc] = metas;
        for (const m of metas) allMetas.push({ cc, ...m });
      }

      // Build a per-title map of which countries use each title — used to
      // exclude titles that are shared across multiple countries (would be
      // ambiguous distractors).
      const titleToCountries = new Map();
      for (const m of allMetas) {
        const k = m.title.toLowerCase();
        if (!titleToCountries.has(k)) titleToCountries.set(k, new Set());
        titleToCountries.get(k).add(m.cc);
      }
      const isUniqueTitle = (title) => titleToCountries.get(title.toLowerCase())?.size === 1;

      const cards = [];
      for (const [cc, metas] of Object.entries(countryMetas)) {
        const c = state.tips[cc];
        // Use up to 3 different metas per country so we get more variety.
        const myUniqueMetas = metas.filter(m => isUniqueTitle(m.title)).slice(0, 3);
        for (const correctMeta of myUniqueMetas) {
          // Distractors: titles from OTHER countries that are also unique to
          // their country, and don't appear in this country's meta list.
          const myTitles = new Set(metas.map(m => m.title.toLowerCase()));
          const candidates = allMetas.filter(m =>
            m.cc !== cc &&
            isUniqueTitle(m.title) &&
            !myTitles.has(m.title.toLowerCase()) &&
            m.title.toLowerCase() !== correctMeta.title.toLowerCase()
          );
          // Shuffle and pick 5 distinct
          const shuffled = candidates.sort(() => Math.random() - 0.5);
          const seen = new Set([correctMeta.title.toLowerCase()]);
          const distractors = [];
          for (const m of shuffled) {
            const k = m.title.toLowerCase();
            if (seen.has(k)) continue;
            seen.add(k);
            distractors.push(m.title);
            if (distractors.length >= 5) break;
          }
          if (distractors.length < 3) continue;
          const options = [correctMeta.title, ...distractors].slice(0, 6);
          cards.push({
            text: `${flagEmoji(cc)} ${c.name}`,
            subtext: 'Which descriptive meta belongs to this country?',
            options,
            correctOption: correctMeta.title,
            highlightCcs: [cc],
            description: `${c.name} is associated with: "${correctMeta.title}".`,
            cardKey: `reverse:${cc}:${correctMeta.title.slice(0, 30)}`,
          });
        }
      }
      return cards;
    },
  };
}

function flagEmoji(cc) {
  if (!cc || cc.length !== 2) return '';
  const A = 0x1F1E6;
  return String.fromCodePoint(...[...cc.toUpperCase()].map(c => A + c.charCodeAt(0) - 65));
}

// Build the feedback description for an area code, including primary city
// and (when available) a memorable mnemonic to help internalise the link.
// The buildPool functions don't have direct access to state.areaCodeNotes,
// so callers can pass it in via opts; otherwise we read from window.__app
// or fall back to the city-only string.
function areaCodeDescription(code, stateName, code2city, notes) {
  // Notes can be passed explicitly OR pulled from the window-attached state
  // (set in app.js boot()). Either way, falling back to {} is fine.
  const noteMap = notes || (typeof window !== 'undefined' && window.__appState?.areaCodeNotes) || {};
  const city = (code2city || {})[code];
  const mnemonic = noteMap[code];
  let base;
  if (city && city !== 'statewide' && !city.includes('overlay')) {
    base = `Area code ${code} → ${stateName} · primary: ${city}.`;
  } else if (city === 'statewide') {
    base = `Area code ${code} → ${stateName} (covers the entire state).`;
  } else if (city && city.includes('overlay')) {
    base = `Area code ${code} → ${stateName} · ${city}.`;
  } else {
    base = `Area code ${code} is assigned to ${stateName}.`;
  }
  if (mnemonic) {
    base += `\n\n💡 ${mnemonic}`;
  }
  return base;
}

function usAreaCodeTopic() {
  return {
    id: 'us_area_codes',
    label: 'US area codes — all 371',
    group: 'US area codes',
    description: 'Click the state on the US map for the given NANP area code. Feedback shows primary city.',
    mode: 'text_subregion',
    countryCc: 'US',
    buildPool(state) {
      const ac = state.areaCodes || {};
      const code2state = ac.code_to_state || {};
      const code2city = ac.code_to_city || {};
      return Object.entries(code2state).map(([code, stateName]) => ({
        text: code,
        subtext: 'US area code',
        correctSubregionNames: [stateName],
        description: areaCodeDescription(code, stateName, code2city, state.areaCodeNotes),
        cardKey: `us_area:${code}`,
      }));
    },
  };
}

// Walk localStorage's per-card stats and roll them up by the underlying
// 3-digit area code. The stats are keyed by full cardKey (e.g.
// `us_area:212`, `us_area_starter:212`, `us_area_chunk_xxx:212`) but they
// all describe the same code → state link, so we collapse them.
function rollupAreaCodeStats() {
  let raw = {};
  try { raw = JSON.parse(localStorage.getItem('plonker:card-stats')) || {}; }
  catch {}
  const byCode = {};   // code -> {hits, misses, count, lastSeen}
  for (const [k, s] of Object.entries(raw)) {
    // Match any us_area*-prefixed cardKey ending in :<3 digits>. The middle
    // part can contain spaces, parens, dashes etc. for chunk-style keys.
    const m = k.match(/^us_area[\s\S]*:(\d{3})$/);
    if (!m) continue;
    const code = m[1];
    const agg = byCode[code] || (byCode[code] = { hits: 0, misses: 0, count: 0, lastSeen: 0 });
    agg.hits += s.hits || 0;
    agg.misses += s.misses || 0;
    agg.count += s.count || 0;
    agg.lastSeen = Math.max(agg.lastSeen, s.lastSeen || 0);
  }
  return byCode;
}

// 🎯 Spaced-repetition pool. Mixes:
//   1. Actively weak codes (<75% accuracy) — your current trouble spots
//   2. "Due for review" codes — high accuracy but you haven't seen them
//      in a while, so the forgetting curve is bringing them back
// Capped at 30 per session and rebuilt every time you click Start.
function usAreaCodeWeakTopic() {
  return {
    id: 'us_area_codes_weak',
    label: '🎯 Weak + due for review (smart pool)',
    group: 'US area codes — smart',
    description: 'Auto-built from your answer history. Mixes codes you keep getting wrong (<75% accuracy) with codes you mastered but haven\'t seen recently — so nothing slips off the forgetting curve. Pool rebuilds every time you click Start.',
    mode: 'text_subregion',
    countryCc: 'US',
    buildPool(state) {
      const ac = state.areaCodes || {};
      const code2state = ac.code_to_state || {};
      const code2city = ac.code_to_city || {};
      const stats = rollupAreaCodeStats();
      const now = Date.now();
      const DAY_MS = 24 * 60 * 60 * 1000;
      // Spacing intervals — once a code reaches each accuracy band, it
      // re-surfaces for review after this many days since the last answer.
      // Lower-accuracy bands return faster; mastered cards return less often.
      const dueIntervalDays = (acc, count) => {
        if (acc < 0.75) return 0;          // always weak — never excluded
        if (acc < 0.90) return 3;          // shaky → 3-day review
        if (acc < 0.98 || count < 5) return 7;   // solid but not yet mastered → 1 wk
        return 14;                         // truly mastered → 2 wk maintenance
      };
      const candidates = [];
      for (const [code, agg] of Object.entries(stats)) {
        if (!code2state[code]) continue;
        if (agg.count === 0) continue;
        const accuracy = agg.hits / agg.count;
        const ageDays = (now - (agg.lastSeen || 0)) / DAY_MS;
        const dueAfter = dueIntervalDays(accuracy, agg.count);
        // "Actively weak" — always include
        const weak = accuracy < 0.75 || (agg.count === 1 && agg.misses > 0);
        // "Due for review" — mastered enough that we set an interval, and it's elapsed
        const due = !weak && ageDays >= dueAfter;
        if (weak || due) {
          candidates.push({
            code,
            agg,
            accuracy,
            ageDays,
            kind: weak ? 'weak' : 'review',
            // priority: actively weak first, then most-overdue review
            priority: weak ? -1 + accuracy : (1 - ageDays / Math.max(1, dueAfter)),
          });
        }
      }
      candidates.sort((a, b) => a.priority - b.priority);
      const top = candidates.slice(0, 30);
      return top.map(({ code, kind }) => {
        const stateName = code2state[code];
        return {
          text: code,
          subtext: kind === 'review' ? 'Review (mastered earlier)' : 'Weak code',
          correctSubregionNames: [stateName],
          description: areaCodeDescription(code, stateName, code2city, state.areaCodeNotes),
          cardKey: `us_area:${code}`,
        };
      });
    },
  };
}

// 🎯 Codes you have NEVER answered. Auto-batches the next 30 unseen codes
// so you can chip away at the unknown territory in small sessions.
function usAreaCodeUnseenTopic() {
  return {
    id: 'us_area_codes_unseen',
    label: '🎯 Unseen codes (next 30 to learn)',
    group: 'US area codes — smart',
    description: 'Auto-built from your answer history. The 30 codes you have never been quizzed on yet — your next batch to learn. Re-builds each session as you cover more codes.',
    mode: 'text_subregion',
    countryCc: 'US',
    buildPool(state) {
      const ac = state.areaCodes || {};
      const code2state = ac.code_to_state || {};
      const code2city = ac.code_to_city || {};
      const stats = rollupAreaCodeStats();
      // Collect codes never quizzed (or quizzed 0 times — same thing)
      const unseen = [];
      for (const code of Object.keys(code2state)) {
        const s = stats[code];
        if (!s || s.count === 0) unseen.push(code);
      }
      // Sort numerically so the dropdown count is stable across reloads
      unseen.sort();
      const batch = unseen.slice(0, 30);
      return batch.map(code => {
        const stateName = code2state[code];
        return {
          text: code,
          subtext: 'Unseen code (next batch)',
          correctSubregionNames: [stateName],
          description: areaCodeDescription(code, stateName, code2city, state.areaCodeNotes),
          cardKey: `us_area:${code}`,
        };
      });
    },
  };
}

// 25 most-recognizable area codes — start here if you have no knowledge.
// Sourced by selecting the original 1947 NPA codes for major cities + the
// most-referenced codes in pop culture (212 NYC, 90210-area 310, 415 SF,
// 305 Miami, 312 Chicago, 808 Hawaii, etc.).
const STARTER_CODES = new Set([
  '212',  // Manhattan
  '213',  // Los Angeles
  '202',  // Washington DC
  '312',  // Chicago
  '305',  // Miami
  '415',  // San Francisco
  '617',  // Boston
  '702',  // Las Vegas
  '808',  // Hawaii
  '907',  // Alaska
  '504',  // New Orleans
  '615',  // Nashville
  '713',  // Houston
  '214',  // Dallas
  '619',  // San Diego
  '404',  // Atlanta
  '503',  // Portland OR
  '206',  // Seattle
  '602',  // Phoenix
  '303',  // Denver
  '215',  // Philadelphia
  '216',  // Cleveland
  '313',  // Detroit
  '816',  // Kansas City
  '512',  // Austin
]);

function usAreaCodeStarterTopic() {
  return {
    id: 'us_area_codes_starter',
    label: '⭐ Starter — 25 famous codes',
    group: 'US area codes',
    description: 'Begin here. The 25 most-recognizable US area codes (NYC, LA, Chicago, Miami, etc.) — anchor your memory on these first.',
    mode: 'text_subregion',
    countryCc: 'US',
    buildPool(state) {
      const ac = state.areaCodes || {};
      const code2state = ac.code_to_state || {};
      const code2city = ac.code_to_city || {};
      const cards = [];
      for (const [code, stateName] of Object.entries(code2state)) {
        if (!STARTER_CODES.has(code)) continue;
        cards.push({
          text: code,
          subtext: 'Famous US area code',
          correctSubregionNames: [stateName],
          description: areaCodeDescription(code, stateName, code2city, state.areaCodeNotes) + ' (One of the 25 most-recognizable codes.)',
          cardKey: `us_area_starter:${code}`,
        });
      }
      return cards;
    },
  };
}

// US census regions — geographic grouping. Each topic restricts the quiz pool
// to area codes from states in that region, so you can master one chunk at a
// time instead of randomly sampling all 50 states.
const US_REGIONS = {
  'Northeast': [
    'Connecticut', 'Maine', 'Massachusetts', 'New Hampshire', 'New Jersey',
    'New York', 'Pennsylvania', 'Rhode Island', 'Vermont',
  ],
  'Midwest': [
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Michigan', 'Minnesota',
    'Missouri', 'Nebraska', 'North Dakota', 'Ohio', 'South Dakota', 'Wisconsin',
  ],
  'South': [
    'Alabama', 'Arkansas', 'Delaware', 'District of Columbia', 'Florida',
    'Georgia', 'Kentucky', 'Louisiana', 'Maryland', 'Mississippi',
    'North Carolina', 'Oklahoma', 'South Carolina', 'Tennessee', 'Texas',
    'Virginia', 'West Virginia',
  ],
  'West': [
    'Alaska', 'Arizona', 'California', 'Colorado', 'Hawaii', 'Idaho',
    'Montana', 'Nevada', 'New Mexico', 'Oregon', 'Utah', 'Washington', 'Wyoming',
  ],
};

function usAreaCodeRegionalTopic(regionName, stateList) {
  const states = new Set(stateList);
  return {
    id: `us_area_${regionName.toLowerCase().replace(/\s+/g, '_')}`,
    label: `${regionName} only (${stateList.length} states)`,
    group: 'US area codes',
    description: `Only area codes from ${regionName} states. Drill one region at a time — much easier than the full 371.`,
    mode: 'text_subregion',
    countryCc: 'US',
    buildPool(state) {
      const ac = state.areaCodes || {};
      const code2state = ac.code_to_state || {};
      const code2city = ac.code_to_city || {};
      const cards = [];
      for (const [code, stateName] of Object.entries(code2state)) {
        if (!states.has(stateName)) continue;
        cards.push({
          text: code,
          subtext: `${regionName} US area code`,
          correctSubregionNames: [stateName],
          description: areaCodeDescription(code, stateName, code2city, state.areaCodeNotes),
          cardKey: `us_area_${regionName}:${code}`,
        });
      }
      return cards;
    },
  };
}

// Sub-region chunks — small multi-state geographic clusters. Each chunk
// has 4–15 codes spanning 2–6 states, so the quiz still tests code→state
// recall (multiple state answers possible) but the pool is small enough to
// memorise in one sitting.
const US_AREA_CHUNKS = {
  // ---- Northeast ----
  'New England minors (single-code states)': {
    states: ['Maine', 'New Hampshire', 'Rhode Island', 'Vermont'],
    note: 'Each of these states has exactly ONE area code. 207=ME, 401=RI, 603=NH, 802=VT — easy anchors.',
  },
  'Tristate area (NYC + suburbs)': {
    states: ['New York', 'New Jersey', 'Connecticut'],
    codes: ['212','332','347','646','680','718','917','929','201','551','732','848','862','908','973','203','475','860','959','516','631','914','845','363','329','934'],
    note: 'NYC core + NJ commuter belt + CT shore. Mostly metro-area codes.',
  },
  'Upstate New York': {
    states: ['New York'],
    codes: ['315','518','585','607','716','680','838'],
    note: 'Buffalo (716), Rochester (585), Syracuse (315/680), Albany (518/838), Binghamton (607).',
  },
  'Pennsylvania (East — Philly + Lehigh)': {
    states: ['Pennsylvania', 'New Jersey', 'Delaware'],
    codes: ['215','267','445','610','484','835','223','272','570','302','856','609','640'],
    note: 'Greater Philadelphia metro spans into NJ + DE.',
  },
  'Pennsylvania (West — Pittsburgh + central)': {
    states: ['Pennsylvania'],
    codes: ['412','724','878','582','814','717'],
    note: 'Pittsburgh metro, Erie, central PA (Harrisburg / Lancaster).',
  },
  'Massachusetts (Boston + outer)': {
    states: ['Massachusetts', 'Rhode Island', 'New Hampshire'],
    codes: ['617','857','339','781','351','978','413','508','774','401','603'],
    note: 'Greater Boston is dense with overlay codes; western MA + RI + NH on the edges.',
  },

  // ---- Mid-Atlantic ----
  'DC metro (DC + MD + VA)': {
    states: ['District of Columbia', 'Maryland', 'Virginia', 'West Virginia'],
    codes: ['202','771','301','240','410','443','667','703','571','540','276','434','804','757','948','304','681'],
    note: 'DC capital + suburbs in MD + VA. The "DMV" cluster.',
  },

  // ---- South ----
  'Florida (Miami + Orlando + Tampa)': {
    states: ['Florida'],
    codes: ['305','786','645','954','754','561','728','727','813','863','941','239','407','321','689','689','352','386','850','904'],
    note: 'Three big metros: South FL (Miami), Central (Orlando/Tampa), North (Jax/Tally).',
  },
  'Carolinas + Georgia': {
    states: ['North Carolina', 'South Carolina', 'Georgia'],
    codes: ['704','980','910','252','336','743','828','919','984','803','839','843','854','864','821','404','470','678','770','762','706','912','229','478'],
    note: 'Charlotte (704), Raleigh (919), Atlanta cluster (404/470/678/770).',
  },
  'Texas (DFW + Houston + Austin/SA)': {
    states: ['Texas'],
    codes: ['214','469','972','945','817','682','713','346','281','832','512','737','210','726','254','325','361','409','430','432','512','830','903','936','940','956','972','979'],
    note: 'DFW: 214/469/972/945. Houston: 713/281/832. Austin: 512/737. San Antonio: 210/726.',
  },
  'Mississippi River South (LA + MS + AR + TN)': {
    states: ['Louisiana', 'Mississippi', 'Arkansas', 'Tennessee'],
    codes: ['504','225','985','318','337','601','662','769','228','501','479','870','327','901','731','615','629','423','865','931'],
    note: 'New Orleans (504), Memphis (901), Little Rock (501), Nashville (615/629).',
  },

  // ---- Midwest ----
  'Great Lakes industrial (OH + MI + IN)': {
    states: ['Ohio', 'Michigan', 'Indiana'],
    codes: ['216','220','234','283','330','380','419','436','440','513','567','614','740','937','248','269','313','517','586','616','679','734','810','906','947','989','219','260','317','463','574','765','812','930'],
    note: 'Cleveland/Columbus/Cincy + Detroit + Indianapolis cluster.',
  },
  'Chicago + Illinois + Wisconsin': {
    states: ['Illinois', 'Wisconsin'],
    codes: ['312','773','872','464','708','331','630','847','224','217','309','447','618','730','779','815','414','262','274','534','608','715','920'],
    note: 'Chicago metro is a stack of overlays (312/773/872/464). WI: 414=Milwaukee.',
  },
  'Plains states (KS + NE + ND + SD + IA + MO + MN)': {
    states: ['Kansas','Nebraska','North Dakota','South Dakota','Iowa','Missouri','Minnesota'],
    codes: ['316','620','785','913','308','402','531','701','605','319','515','563','641','712','839','314','417','573','636','660','816','975','218','320','507','612','651','763','952'],
    note: 'Mostly small/single codes per state — sparse population.',
  },

  // ---- West ----
  'California (Bay Area + LA)': {
    states: ['California'],
    codes: ['415','628','510','341','650','408','669','209','559','213','310','323','424','747','818','747','626','661','747','949','714','657','562','805','820'],
    note: 'Bay Area: 415/628/510/650/408. LA Basin: 213/323/310/424/818/747.',
  },
  'California (Central + North)': {
    states: ['California'],
    codes: ['916','279','530','209','559','661','805','820','831','559','209','541','458'],
    note: 'Sacramento (916), Central Valley (559/209), North Coast (530/707).',
  },
  'Pacific Northwest (WA + OR + ID)': {
    states: ['Washington', 'Oregon', 'Idaho'],
    codes: ['206','253','360','425','509','564','206','503','541','971','458','208','986'],
    note: 'Seattle (206/425), Portland (503/971), Boise (208).',
  },
  'Mountain West (CO + UT + NV + AZ + NM + WY + MT)': {
    states: ['Colorado','Utah','Nevada','Arizona','New Mexico','Wyoming','Montana'],
    codes: ['303','720','970','983','385','435','801','802','725','775','702','480','520','602','623','480','928','505','575','307','406'],
    note: 'Denver (303/720), SLC (385/801), Vegas (702/725), Phoenix (480/602/623/928).',
  },
  'Alaska + Hawaii': {
    states: ['Alaska', 'Hawaii'],
    codes: ['907', '808'],
    note: 'Each state has one code. 907=AK, 808=HI. Easy anchors.',
  },
};

function usAreaCodeChunkTopics() {
  return Object.entries(US_AREA_CHUNKS).map(([chunkName, def]) => ({
    id: `us_area_chunk_${chunkName.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')}`,
    label: chunkName,
    group: 'US area codes — by metro / cluster',
    description: `${def.note} ${def.states.length} states.`,
    mode: 'text_subregion',
    countryCc: 'US',
    buildPool(state) {
      const ac = state.areaCodes || {};
      const code2state = ac.code_to_state || {};
      const code2city = ac.code_to_city || {};
      const wantedStates = new Set(def.states);
      const wantedCodes = def.codes ? new Set(def.codes) : null;
      const cards = [];
      const seen = new Set();
      for (const [code, st] of Object.entries(code2state)) {
        if (!wantedStates.has(st)) continue;
        // If chunk specifies an explicit code list, use that (lets us pick
        // only the metro-area codes from a state with many codes). Otherwise
        // include all codes for the listed states.
        if (wantedCodes && !wantedCodes.has(code)) continue;
        if (seen.has(code)) continue;
        seen.add(code);
        cards.push({
          text: code,
          subtext: chunkName,
          correctSubregionNames: [st],
          description: areaCodeDescription(code, st, code2city, state.areaCodeNotes),
          cardKey: `us_area_chunk_${chunkName}:${code}`,
        });
      }
      return cards;
    },
  }));
}

// ---- Per-country area-code quizzes ----
// Reads `state.countryAreaCodes` (data/country_area_codes.json) and emits
// one topic per country with code-to-region data. Each topic asks the user
// to click the correct admin-1 region for the displayed code.
function countryAreaCodeTopics() {
  // We only know which countries have data at buildPool() time, so we
  // pre-generate topics for any cc that MIGHT have data; the buildPool
  // returns [] if data is missing and the topic shows "(0)".
  const POSSIBLE = ['KZ', 'KR', 'GR', 'HR', 'HU', 'CY', 'IE', 'PT', 'RS',
                    'SK', 'TH', 'TW', 'UA', 'BG', 'BE', 'GB', 'IL', 'LK', 'RU'];
  return POSSIBLE.flatMap(cc => {
    const allTopic = {
      id: `${cc.toLowerCase()}_area_codes`,
      label: `${cc} area codes — all`,
      group: `Area codes — ${cc}`,
      description: `All area codes for ${cc}. Click the correct region on the map.`,
      mode: 'text_subregion',
      countryCc: cc,
      buildPool(state) {
        const data = (state.countryAreaCodes || {})[cc];
        if (!data) return [];
        const code2region = data.code_to_region || {};
        const notes = data.notes || {};
        return Object.entries(code2region).map(([code, regionName]) => ({
          text: code,
          subtext: `${data.name} area code`,
          correctSubregionNames: [regionName],
          description: countryAreaCodeDescription(code, regionName, notes),
          cardKey: `${cc.toLowerCase()}_area:${code}`,
        }));
      },
    };
    // 🎯 Smart pool — same idea as US weak-codes, scoped to this country.
    const weakTopic = {
      id: `${cc.toLowerCase()}_area_codes_weak`,
      label: `${cc} area codes — 🎯 weak + due for review`,
      group: `Area codes — ${cc}`,
      description: `Auto-built from your stats for ${cc}. Codes you keep getting wrong + codes you mastered but haven't seen in a while.`,
      mode: 'text_subregion',
      countryCc: cc,
      buildPool(state) {
        const data = (state.countryAreaCodes || {})[cc];
        if (!data) return [];
        const code2region = data.code_to_region || {};
        const notes = data.notes || {};
        const stats = rollupCountryAreaCodeStats(cc.toLowerCase());
        const now = Date.now();
        const DAY = 24 * 60 * 60 * 1000;
        const candidates = [];
        for (const [code, regionName] of Object.entries(code2region)) {
          const agg = stats[code];
          if (!agg || agg.count === 0) continue;   // unseen — handled by "all" pool
          const accuracy = agg.hits / agg.count;
          const age = (now - (agg.lastSeen || 0)) / DAY;
          const dueAfter =
            accuracy < 0.75 ? 0 :
            accuracy < 0.90 ? 3 :
            (accuracy < 0.98 || agg.count < 5) ? 7 : 14;
          const weak = accuracy < 0.75;
          const due = !weak && age >= dueAfter;
          if (weak || due) {
            candidates.push({
              code,
              regionName,
              priority: weak ? -1 + accuracy : (1 - age / Math.max(1, dueAfter)),
              kind: weak ? 'weak' : 'review',
            });
          }
        }
        candidates.sort((a, b) => a.priority - b.priority);
        return candidates.slice(0, 30).map(({ code, regionName, kind }) => ({
          text: code,
          subtext: kind === 'review' ? 'Review (mastered earlier)' : 'Weak code',
          correctSubregionNames: [regionName],
          description: countryAreaCodeDescription(code, regionName, notes),
          cardKey: `${cc.toLowerCase()}_area:${code}`,
        }));
      },
    };
    return [allTopic, weakTopic];
  });
}

function countryAreaCodeDescription(code, regionName, notes) {
  const note = notes[code];
  let base = `Area code ${code} → ${regionName}.`;
  if (note) base += `\n\n💡 ${note}`;
  return base;
}

// ---- Compendium quizzes ----
// Each compendium in `state.compendiumQuizzes` (data/compendium_quizzes.json)
// becomes a focused per-country topic. Card mode is text_subregion: the
// label is shown as the prompt, the user clicks the correct admin-1 region
// on the map. Subregion-name resolution piggybacks on subregion_polygons
// (which already has aliases for most spellings).
const COMPENDIUM_TYPE_LABELS = {
  area_code:       { group: 'Compendium quiz', noun: 'area code' },
  road_number:     { group: 'Compendium quiz', noun: 'road number' },
  flag:            { group: 'Compendium quiz', noun: 'state flag' },
  license_plate:   { group: 'Compendium quiz', noun: 'license plate' },
  pole_plate:      { group: 'Compendium quiz', noun: 'pole plate' },
  bus_stop_style:  { group: 'Compendium quiz', noun: 'bus stop style' },
  bus_company:     { group: 'Compendium quiz', noun: 'bus company' },
  postcode:        { group: 'Compendium quiz', noun: 'postal code' },
  other:           { group: 'Compendium quiz', noun: 'item' },
};

function compendiumQuizTopics() {
  // We don't know the data at module-load time. Emit one factory per
  // compendium key by reading state at buildPool time.
  // To keep dropdown order stable we hardcode common keys we ship with;
  // unrecognised keys still appear via a generic fallback below.
  // Approach: at buildPool time, iterate state.compendiumQuizzes — but
  // we need to know KEYS at registration time. Solution: emit one topic
  // per known key by reading a static index of expected keys from a
  // synchronously-evaluated import side effect. Since topics.js runs
  // before data loads, we can't do that. Instead, we expose ALL keys
  // dynamically by registering a SINGLE meta-topic that fans out per
  // compendium when buildPool is called — but that's a single dropdown
  // entry, not per-compendium.
  //
  // Practical fix: register a fixed list of known compendium keys (the
  // ones that exist in compendium_quizzes.json today). New keys added
  // later will need a code update — minor maintenance cost.
  const KNOWN_KEYS = [
    'DE_flags', 'MY_flags', 'IT_flags',
    'IL_area_codes', 'BE_phone_codes', 'GR_area_codes', 'IE_phone_codes',
    'SK_area_codes', 'KR_area_codes',
    'SK_road_numbers', 'HU_road_numbers', 'LU_road_numbers',
    'CZ_road_numbers', 'DK_road_numbers',
    'BE_bus_stops', 'NZ_bus_stops', 'RU_bus_stops', 'SE_bus_stops',
    'DK_bus_companies', 'AT_bus_companies',
    'CA_license_plates',
  ];
  return KNOWN_KEYS.map(key => ({
    id: `compendium_${key.toLowerCase()}`,
    label: `(compendium) ${key.replace(/_/g, ' ')}`,
    group: 'Compendium quiz',
    description: 'Click the correct region for the labelled item.',
    mode: 'text_subregion',
    countryCc: null,    // set dynamically in buildPool when data loads
    buildPool(state) {
      const cq = (state.compendiumQuizzes || {})[key];
      if (!cq || !Array.isArray(cq.items)) return [];
      const cc = cq.cc;
      // Patch the topic's countryCc lazily so the map zooms correctly
      this.countryCc = cc;
      this.label = cq.name || `${cc} ${key}`;
      this.description = cq.intro || this.description;
      return cq.items
        .filter(it => it.label && it.region)
        .map((it, i) => ({
          text: it.label,
          subtext: cq.name || key,
          correctSubregionNames: [it.region],
          description: `${it.label} → ${it.region} (${cq.name}).`,
          cardKey: `compendium:${key}:${i}`,
        }));
    },
  }));
}

function rollupCountryAreaCodeStats(prefix) {
  let raw = {};
  try { raw = JSON.parse(localStorage.getItem('plonker:card-stats')) || {}; }
  catch {}
  const byCode = {};
  const rx = new RegExp(`^${prefix}_area[\\s\\S]*:(\\d{2,3})$`);
  for (const [k, s] of Object.entries(raw)) {
    const m = k.match(rx);
    if (!m) continue;
    const code = m[1];
    const agg = byCode[code] || (byCode[code] = { hits: 0, misses: 0, count: 0, lastSeen: 0 });
    agg.hits += s.hits || 0;
    agg.misses += s.misses || 0;
    agg.count += s.count || 0;
    agg.lastSeen = Math.max(agg.lastSeen, s.lastSeen || 0);
  }
  return byCode;
}
