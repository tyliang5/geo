// Plonker localhost app — unified Home / Quiz / Dashboard.
// Pulls round history directly from Supabase (publishable key, RLS-gated).
// Click-on-map quiz uses Leaflet + Natural Earth countries.geojson.

// Cache-bust topics.js so dev edits show without a hard refresh.
import { buildTopics } from './topics.js?v=14';

const SUPABASE_URL = 'https://qhudavmfhbumknqddgig.supabase.co';
const SUPABASE_KEY = 'sb_publishable_aGh_bbXqckmx-0DgaEySWg_9yyc_994';
const SUPA_HEADERS = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
};

const $ = (id) => document.getElementById(id);
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const flagEmoji = (cc) => {
  if (!cc || cc.length !== 2) return '';
  const A = 0x1F1E6;
  return String.fromCodePoint(...[...cc.toUpperCase()].map(c => A + c.charCodeAt(0) - 65));
};

// ---------- phone-keypad widget ----------
// Renders the standard ITU 3×4 phone keypad next to the prompt when the
// prompt is a numeric area / calling code. Each digit of the code is
// highlighted on the keypad and numbered in the order it appears in the
// code, so the user can see the spatial pattern (e.g. 212 → top column
// twice via 2-1-2) and build T9-letter mnemonics (212 = ABC × 1 × ABC).
const KEYPAD_LAYOUT = [
  { num: '1', letters: '' },
  { num: '2', letters: 'ABC' },
  { num: '3', letters: 'DEF' },
  { num: '4', letters: 'GHI' },
  { num: '5', letters: 'JKL' },
  { num: '6', letters: 'MNO' },
  { num: '7', letters: 'PQRS' },
  { num: '8', letters: 'TUV' },
  { num: '9', letters: 'WXYZ' },
  { num: '*', letters: '' },
  { num: '0', letters: '' },
  { num: '#', letters: '' },
];
function renderKeypad(promptText) {
  const el = document.getElementById('quiz-keypad');
  if (!el) return;
  // Strip leading + and any non-digits to get just the digits the user
  // would dial. If nothing's left or it's >4 digits, hide the keypad.
  const digits = String(promptText).replace(/\D/g, '');
  if (!digits || digits.length < 2 || digits.length > 4) {
    el.hidden = true;
    el.innerHTML = '';
    return;
  }
  // First-occurrence index per digit so we know what to show in the
  // order-bubble (1 for the first unique digit, 2 for the second, etc.).
  // For repeated digits (e.g. 808's two 8s) the bubble shows the LAST
  // position in the code so the user sees the latest "press" — but we
  // also keep the highlight on the key for both presses.
  const digitOrder = {};
  digits.split('').forEach((d, i) => { digitOrder[d] = (i + 1); });
  el.hidden = false;
  el.innerHTML = KEYPAD_LAYOUT.map(({ num, letters }) => {
    const order = digitOrder[num];
    const active = order != null;
    return `<div class="qkeypad-key${active ? ' active' : ''}">
      ${active ? `<div class="qkeypad-order">${digits.indexOf(num) + 1}</div>` : ''}
      <div class="qkeypad-num">${num}</div>
      <div class="qkeypad-letters">${letters}</div>
    </div>`;
  }).join('');
}

// ---------- inset detection (client-side) ----------
// learnablemeta routinely embeds a small country-shape inset somewhere on
// each meta image — gray country fill, light background, often with red
// region highlights. In sub-region quizzes that inset gives the answer
// away. We detect the inset's bbox by sampling pixels into a low-res
// canvas, finding the largest contiguous "map-ish" region (low color
// saturation, medium-bright background, ≥4% of image), and then sizing
// the mask to cover it.
//
// Returns null when no inset is found (so the mask isn't shown at all).
function detectInsetBox(imgEl) {
  try {
    const TW = 100;   // target width — kept tiny for speed
    const W = imgEl.naturalWidth, H = imgEl.naturalHeight;
    if (!W || !H) return null;
    const w = TW;
    const h = Math.max(20, Math.round(H * (TW / W)));
    const cv = document.createElement('canvas');
    cv.width = w; cv.height = h;
    const ctx = cv.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(imgEl, 0, 0, w, h);
    let pixels;
    try { pixels = ctx.getImageData(0, 0, w, h).data; }
    catch { return null; }   // tainted canvas (cross-origin) — give up gracefully
    // Build "map-ish" mask: low saturation (<=22) AND mean brightness >=200
    const mask = new Uint8Array(w * h);
    for (let i = 0, p = 0; p < pixels.length; p += 4, i++) {
      const r = pixels[p], g = pixels[p+1], b = pixels[p+2];
      const mn = Math.min(r, g, b);
      const mx = Math.max(r, g, b);
      const mean = (r + g + b) / 3;
      mask[i] = (mx - mn <= 22 && mean >= 200) ? 1 : 0;
    }
    // Quick sanity: need at least 4% map-ish pixels overall
    let total = 0;
    for (let i = 0; i < mask.length; i++) total += mask[i];
    if (total < w * h * 0.04) return null;
    // Morphological closing (3x3 dilate, then 3x3 erode) so the country
    // fill's gaps inside the inset get bridged.
    const dilate = (m) => {
      const out = new Uint8Array(m.length);
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          let v = 0;
          for (let dy = -1; dy <= 1 && !v; dy++) {
            for (let dx = -1; dx <= 1 && !v; dx++) {
              const yy = y + dy, xx = x + dx;
              if (yy < 0 || yy >= h || xx < 0 || xx >= w) continue;
              if (m[yy * w + xx]) v = 1;
            }
          }
          out[y * w + x] = v;
        }
      }
      return out;
    };
    const erode = (m) => {
      const out = new Uint8Array(m.length);
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          let v = 1;
          for (let dy = -1; dy <= 1 && v; dy++) {
            for (let dx = -1; dx <= 1 && v; dx++) {
              const yy = y + dy, xx = x + dx;
              if (yy < 0 || yy >= h || xx < 0 || xx >= w) { v = 0; continue; }
              if (!m[yy * w + xx]) v = 0;
            }
          }
          out[y * w + x] = v;
        }
      }
      return out;
    };
    let m = mask;
    m = dilate(m); m = dilate(m);
    m = erode(m);  m = erode(m);
    // Connected components — pick the largest. We do a flood-fill BFS.
    const seen = new Uint8Array(m.length);
    let bestSize = 0, bestBox = null;
    const queue = new Int32Array(m.length);
    for (let i = 0; i < m.length; i++) {
      if (!m[i] || seen[i]) continue;
      let qHead = 0, qTail = 0;
      queue[qTail++] = i;
      seen[i] = 1;
      let minX = w, maxX = -1, minY = h, maxY = -1, size = 0;
      while (qHead < qTail) {
        const idx = queue[qHead++];
        const x = idx % w, y = (idx / w) | 0;
        size++;
        if (x < minX) minX = x;  if (x > maxX) maxX = x;
        if (y < minY) minY = y;  if (y > maxY) maxY = y;
        for (const [dy, dx] of [[-1,0],[1,0],[0,-1],[0,1]]) {
          const yy = y + dy, xx = x + dx;
          if (yy < 0 || yy >= h || xx < 0 || xx >= w) continue;
          const ni = yy * w + xx;
          if (!m[ni] || seen[ni]) continue;
          seen[ni] = 1;
          queue[qTail++] = ni;
        }
      }
      if (size > bestSize) {
        bestSize = size;
        bestBox = { minX, maxX, minY, maxY, size };
      }
    }
    if (!bestBox || bestSize < w * h * 0.04) return null;
    const bw = bestBox.maxX - bestBox.minX + 1;
    const bh = bestBox.maxY - bestBox.minY + 1;
    const areaFrac = (bw * bh) / (w * h);
    if (areaFrac > 0.95) return null;
    // Rectangularity: insets fill their bbox at >0.55, sky/cloud blobs less.
    const fill = bestSize / (bw * bh);
    if (fill < 0.45) return null;
    // Padding: 1.5% of dims so the mask comfortably overlaps the boundary.
    const padX = w * 0.015, padY = h * 0.015;
    let x0 = Math.max(0, bestBox.minX - padX);
    let y0 = Math.max(0, bestBox.minY - padY);
    let x1 = Math.min(w, bestBox.maxX + padX + 1);
    let y1 = Math.min(h, bestBox.maxY + padY + 1);
    return {
      x: x0 / w, y: y0 / h,
      w: (x1 - x0) / w, h: (y1 - y0) / h,
    };
  } catch (e) {
    console.warn('[plonker] inset detection failed:', e);
    return null;
  }
}

// Apply a detected mask box (or hide the mask entirely if no inset detected).
function applyMaskBox(maskEl, box) {
  if (!maskEl) return;
  if (!box) {
    // No inset found in this image — hide the mask (no reason to occlude
    // photo content if there's nothing to hide).
    maskEl.classList.add('no-inset');
    return;
  }
  maskEl.classList.remove('no-inset');
  // Mask is positioned absolute inside .qimg-wrap, which contains .qimg
  // sized to fill the wrap (object-fit: contain). The image is letterboxed
  // so we have to position relative to the rendered image's content box,
  // not the wrap. Leaflet/CSS handles this with percentages anchored to
  // the wrap, which is fine because qimg uses width:100% and
  // object-fit: contain only adds bars on the SHORT axis. We approximate
  // by setting the mask in fractions of the wrap and letting any minor
  // letterbox bias slide — the mask is padded enough to cover the slop.
  maskEl.style.left   = (box.x * 100).toFixed(2) + '%';
  maskEl.style.top    = (box.y * 100).toFixed(2) + '%';
  maskEl.style.width  = (box.w * 100).toFixed(2) + '%';
  maskEl.style.height = (box.h * 100).toFixed(2) + '%';
  maskEl.style.right  = 'auto';
  maskEl.style.bottom = 'auto';
  maskEl.style.maxWidth = 'none';
  maskEl.style.maxHeight = 'none';
}

// ---------- region groupings ----------
const REGION_GROUPS = {
  // Continents
  EU: ['AL','AD','AT','BY','BE','BA','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IS','IE','IM','IT','JE','XK','LV','LI','LT','LU','MT','MD','MC','ME','NL','MK','NO','PL','PT','RO','SM','RS','SK','SI','ES','SE','CH','UA','GB','VA','GG','FO','SJ','GI'],
  AS: ['AF','AM','AZ','BH','BD','BT','BN','KH','CN','GE','HK','IN','ID','IR','IQ','IL','JP','JO','KZ','KW','KG','LA','LB','MO','MY','MV','MN','MM','NP','KP','OM','PK','PS','PH','QA','SA','SG','KR','LK','SY','TW','TJ','TH','TL','TR','TM','AE','UZ','VN','YE'],
  AF: ['DZ','AO','BJ','BW','BF','BI','CM','CV','CF','TD','KM','CG','CD','CI','DJ','EG','GQ','ER','SZ','ET','GA','GM','GH','GN','GW','KE','LS','LR','LY','MG','MW','ML','MR','MU','MA','MZ','NA','NE','NG','RW','ST','SN','SC','SL','SO','ZA','SS','SD','TZ','TG','TN','UG','ZM','ZW','EH'],
  NA: ['AG','BS','BB','BZ','CA','CR','CU','DM','DO','SV','GD','GT','HT','HN','JM','MX','NI','PA','KN','LC','VC','TT','US','PR','BM','GP','MQ','GL'],
  SA: ['AR','BO','BR','CL','CO','EC','FK','GF','GY','PY','PE','SR','UY','VE'],
  OC: ['AS','AU','CK','FJ','PF','GU','KI','MH','FM','NR','NC','NZ','MP','PW','PG','WS','SB','TK','TO','TV','VU','WF'],

  // Europe sub-regions
  baltic:        ['LV','LT','EE'],
  nordic:        ['SE','NO','DK','FI','IS','SJ','FO','GL'],
  scandinavia:   ['SE','NO','DK'],
  balkan:        ['AL','BA','BG','HR','XK','MK','ME','RO','RS','SI'],
  iberia:        ['ES','PT','AD','GI'],
  benelux:       ['NL','BE','LU'],
  dach:          ['DE','AT','CH','LI'],
  visegrad:      ['PL','CZ','SK','HU'],
  'central-eu':  ['DE','AT','CH','LI','CZ','SK','HU','PL','SI'],
  'western-eu':  ['FR','DE','NL','BE','LU','CH','AT','MC'],
  'eastern-eu':  ['PL','CZ','SK','HU','RO','BG','BY','UA','MD','RU'],
  'southern-eu': ['ES','PT','IT','GR','MT','CY','SM','VA','MC','AD'],
  'british-isles': ['GB','IE','IM','JE','GG'],
  mediterranean:   ['ES','FR','IT','MT','GR','CY','TR','MC','SM','VA','MA','DZ','TN','LY','EG','IL','LB','SY'],
  'former-yugoslavia': ['HR','SI','BA','RS','ME','XK','MK'],

  // Asia sub-regions
  'subcontinent':   ['IN','PK','BD','LK','NP','BT','MV'],
  'east-asia':      ['CN','JP','KR','KP','TW','MO','HK','MN'],
  'mainland-sea':   ['TH','VN','KH','LA','MM','MY'],
  'maritime-sea':   ['ID','MY','SG','PH','BN','TL'],
  'se-asia':        ['BN','KH','ID','LA','MY','MM','PH','SG','TH','TL','VN'],
  stans:            ['KZ','UZ','TM','KG','TJ','AF'],
  caucasus:         ['GE','AM','AZ'],
  levant:           ['TR','SY','LB','IL','JO','PS','IQ'],
  'arabian-peninsula': ['SA','AE','OM','YE','KW','QA','BH'],

  // Africa sub-regions
  maghreb:           ['MA','DZ','TN','LY','EG','EH'],
  'horn-of-africa':  ['ET','ER','DJ','SO','SS'],
  'east-africa':     ['KE','UG','TZ','RW','BI'],
  'southern-africa': ['ZA','NA','BW','ZW','ZM','MW','MZ','LS','SZ','MG'],
  'west-africa':     ['NG','GH','BJ','TG','CI','BF','ML','SN','GM','GN','GW','LR','SL','MR','NE','CV'],
  'central-africa':  ['CM','CF','TD','CG','CD','GA','GQ','AO','ST'],

  // Americas sub-regions
  'central-america': ['BZ','CR','SV','GT','HN','NI','PA'],
  caribbean:         ['JM','BS','BB','CU','DO','HT','TT','KN','AG','DM','GD','LC','VC','PR'],
  andean:            ['CO','EC','PE','BO','CL','VE'],
  'southern-cone':   ['AR','CL','UY','PY','BR'],
  latam:             ['AR','BO','BR','CL','CO','CR','CU','DO','EC','SV','GT','HN','MX','NI','PA','PY','PE','PR','UY','VE'],
  'anglo-america':   ['US','CA'],

  // Pacific
  'pacific-islands': ['FJ','NZ','PG','SB','VU','WS','TO','TV','KI','NR','FM','MH','PW','MP','GU','AS','PF','NC','CK','WF','TK'],
  oceania:           ['AU','NZ','PG','FJ','SB','VU','WS','TO','TV','KI','NR','FM','MH','PW','MP','GU','AS','PF','NC','CK','WF','TK'],

  // Confusables (high-value GG study targets)
  'confused-eu-east': ['BY','RU','UA'],
  'confused-cz-sk':   ['CZ','SK'],
  'confused-ar-uy':   ['AR','UY'],
  'confused-at-ch':   ['AT','CH'],
  'confused-nl-be':   ['NL','BE'],
  'confused-es-pt':   ['ES','PT'],
  'confused-no-se':   ['NO','SE','DK','FI'],
  'confused-rs-ba-me': ['RS','BA','ME','XK'],
  'confused-hr-si':   ['HR','SI'],
  'confused-jp-kr-tw': ['JP','KR','TW'],
  'confused-th-vn':   ['TH','VN','KH','LA','MM'],
  'confused-au-nz':   ['AU','NZ'],
  'confused-ca-us':   ['CA','US'],
  'confused-bo-pe':   ['BO','PE','EC'],
};

// Friendly labels for the dropdown — also used to group them by category
const REGION_LABELS = [
  { group: 'Europe', items: [
    ['baltic', 'Baltics'],
    ['nordic', 'Nordics'],
    ['scandinavia', 'Scandinavia (proper)'],
    ['british-isles', 'British Isles'],
    ['benelux', 'Benelux'],
    ['dach', 'DACH (German-speaking)'],
    ['visegrad', 'Visegrád (PL/CZ/SK/HU)'],
    ['iberia', 'Iberia'],
    ['balkan', 'Balkans'],
    ['former-yugoslavia', 'Former Yugoslavia'],
    ['central-eu', 'Central Europe'],
    ['western-eu', 'Western Europe'],
    ['eastern-eu', 'Eastern Europe'],
    ['southern-eu', 'Southern Europe'],
    ['mediterranean', 'Mediterranean'],
  ]},
  { group: 'Asia', items: [
    ['subcontinent', 'Indian subcontinent'],
    ['east-asia', 'East Asia'],
    ['mainland-sea', 'Mainland SE Asia'],
    ['maritime-sea', 'Maritime SE Asia'],
    ['se-asia', 'SE Asia (all)'],
    ['stans', 'Central Asia / Stans'],
    ['caucasus', 'Caucasus'],
    ['levant', 'Levant'],
    ['arabian-peninsula', 'Arabian Peninsula'],
  ]},
  { group: 'Africa', items: [
    ['maghreb', 'Maghreb / N Africa'],
    ['horn-of-africa', 'Horn of Africa'],
    ['east-africa', 'East Africa'],
    ['southern-africa', 'Southern Africa'],
    ['west-africa', 'West Africa'],
    ['central-africa', 'Central Africa'],
  ]},
  { group: 'Americas', items: [
    ['anglo-america', 'Anglo America (US/CA)'],
    ['central-america', 'Central America'],
    ['caribbean', 'Caribbean'],
    ['andean', 'Andean'],
    ['southern-cone', 'Southern Cone'],
    ['latam', 'Latin America (all)'],
  ]},
  { group: 'Pacific', items: [
    ['oceania', 'Oceania'],
    ['pacific-islands', 'Pacific Islands'],
  ]},
  { group: 'Easy-confused pairs', items: [
    ['confused-eu-east', 'BY / RU / UA'],
    ['confused-cz-sk', 'CZ / SK'],
    ['confused-ar-uy', 'AR / UY'],
    ['confused-at-ch', 'AT / CH'],
    ['confused-nl-be', 'NL / BE'],
    ['confused-es-pt', 'ES / PT'],
    ['confused-no-se', 'Nordics (NO/SE/DK/FI)'],
    ['confused-rs-ba-me', 'RS / BA / ME / XK'],
    ['confused-hr-si', 'HR / SI'],
    ['confused-jp-kr-tw', 'JP / KR / TW'],
    ['confused-th-vn', 'Mainland SE Asia'],
    ['confused-au-nz', 'AU / NZ'],
    ['confused-ca-us', 'CA / US'],
    ['confused-bo-pe', 'BO / PE / EC'],
  ]},
];

// ---------- shared state ----------
const state = {
  tips: null,        // tips.json
  countries: null,   // covered country list (from country-slugs equivalent)
  geojson: null,     // Natural Earth polygons
  rounds: [],        // Supabase rounds
  focus: { type: 'global', value: null },
};

// ---------- localStorage helpers ----------
const QUIZ_STATS_KEY = 'plonker:quiz-stats';
const TOPIC_STATS_KEY = 'plonker:topic-stats';
const LEITNER_KEY_PREFIX = 'plonker:leitner:';

function loadTopicStats() {
  try { return JSON.parse(localStorage.getItem(TOPIC_STATS_KEY)) || {}; }
  catch { return {}; }
}
function recordTopicAnswer(topicId, isCorrect) {
  if (!topicId) return;
  const stats = loadTopicStats();
  const s = stats[topicId] || { hits: 0, misses: 0, count: 0, lastSeen: 0 };
  s.count++;
  if (isCorrect) s.hits++; else s.misses++;
  s.lastSeen = Date.now();
  stats[topicId] = s;
  localStorage.setItem(TOPIC_STATS_KEY, JSON.stringify(stats));
  schedulePushProgress?.();
}

// Per-card accuracy: keyed by stable cardKey so the same card across
// sessions accumulates stats. Used by the country fact-sheet to highlight
// which specific metas you struggle with.
const CARD_STATS_KEY = 'plonker:card-stats';
function loadCardStats() {
  try { return JSON.parse(localStorage.getItem(CARD_STATS_KEY)) || {}; }
  catch { return {}; }
}
function recordCardAnswer(cardKey, cc, metaType, isCorrect) {
  if (!cardKey) return;
  const stats = loadCardStats();
  const s = stats[cardKey] || { hits: 0, misses: 0, count: 0, cc, metaType, lastSeen: 0 };
  s.count++;
  if (isCorrect) s.hits++; else s.misses++;
  s.cc = cc || s.cc;
  s.metaType = metaType || s.metaType;
  s.lastSeen = Date.now();
  stats[cardKey] = s;
  localStorage.setItem(CARD_STATS_KEY, JSON.stringify(stats));
  schedulePushProgress?.();
}

function loadQuizStats() {
  try { return JSON.parse(localStorage.getItem(QUIZ_STATS_KEY)) || {}; }
  catch { return {}; }
}
function recordQuizAnswer(cc, isCorrect, score) {
  const stats = loadQuizStats();
  const s = stats[cc] || { hits: 0, misses: 0, count: 0, totalScore: 0, lastSeen: 0 };
  s.count++;
  if (isCorrect) s.hits++; else s.misses++;
  if (typeof score === 'number') s.totalScore += score;
  s.lastSeen = Date.now();
  stats[cc] = s;
  localStorage.setItem(QUIZ_STATS_KEY, JSON.stringify(stats));
  schedulePushProgress?.();
}

// Leitner box (1-5). Lower = practice more. Reset to 1 on miss; +1 on hit (cap 5).
function leitnerKey(cc, idx) { return `${LEITNER_KEY_PREFIX}${cc}:${idx}`; }
function getLeitnerBox(cc, idx) {
  try {
    const s = JSON.parse(localStorage.getItem(leitnerKey(cc, idx)));
    return s?.box ?? 1;
  } catch { return 1; }
}
function setLeitnerBox(cc, idx, box) {
  localStorage.setItem(leitnerKey(cc, idx), JSON.stringify({ box, lastSeen: Date.now() }));
  schedulePushProgress?.();
}

// ---------- data loading ----------
// no-cache so editing tips.json / countries.geojson during dev shows up
// without a hard refresh.
const loadJson = (path) => fetch(path, { cache: 'no-cache' }).then(r => r.json());

async function loadAll() {
  const [tips, geojson, admin1, subregions, facts, reference, areaCodes, areaCodeNotes, countryAreaCodes, compendiumQuizzes, extras, ocrBlacklist, plonkitCovered, geoAliases] = await Promise.all([
    loadJson('data/tips.json'),
    loadJson('data/countries.geojson'),
    loadJson('data/admin1.geojson').catch(() => null),
    loadJson('data/subregion_polygons.json').catch(() => null),
    loadJson('data/country_facts.json').catch(() => null),
    loadJson('data/country_reference.json').catch(() => null),
    loadJson('data/us_area_codes.json').catch(() => null),
    loadJson('data/us_area_code_notes.json').catch(() => ({})),
    loadJson('data/country_area_codes.json').catch(() => ({})),
    loadJson('data/compendium_quizzes.json').catch(() => ({})),
    loadJson('data/meta_extras.json').catch(() => null),
    loadJson('data/giveaway_blacklist.json').catch(() => ({})),
    loadJson('data/plonkit_covered.json').catch(() => null),
    loadJson('data/geographic_aliases.json').catch(() => ({})),
  ]);
  state.tips = tips;
  state.geojson = geojson;
  state.admin1 = admin1;
  state.subregions = subregions;
  state.facts = facts;
  state.reference = reference;
  state.areaCodes = areaCodes;
  state.areaCodeNotes = areaCodeNotes || {};
  state.countryAreaCodes = countryAreaCodes || {};
  state.compendiumQuizzes = compendiumQuizzes || {};
  state.extras = extras;
  state.ocrBlacklist = ocrBlacklist || {};   // pre-built {cardKey: {reason, ...}}
  state.geoAliases = geoAliases || {};       // {cc: {phrase: [region names]}}
  state.regionGroups = REGION_GROUPS;
  // Quiz-eligible countries are those with a plonkit guide — i.e. they have
  // real Google Street View coverage. Countries we know facts about but that
  // have no SV (Saudi Arabia, Morocco, North Korea, Aruba, …) are excluded
  // so we never quiz on a country the player can't actually visit in GG.
  // Falls back to the union of tips/facts/reference if the covered list is
  // missing (defensive — should always be present in production).
  const plonkitSet = plonkitCovered ? new Set(plonkitCovered) : null;
  state.countries = new Set();
  const addAll = (obj) => {
    for (const cc of Object.keys(obj || {})) {
      if (cc === '_meta') continue;
      if (plonkitSet && !plonkitSet.has(cc)) continue;
      state.countries.add(cc);
    }
  };
  addAll(tips);
  addAll(facts);
  addAll(reference);
  // Index admin-1 features by their fid for fast lookup
  state.admin1ByFid = {};
  if (admin1?.features) {
    for (const f of admin1.features) {
      const p = f.properties;
      const fid = p.iso_3166_2 || p.code_local || `${p.iso_a2}-${(p.name || 'X').slice(0,8)}`;
      state.admin1ByFid[fid] = f;
    }
  }
}

async function loadRounds() {
  // Supabase / PostgREST caps each response at 1000 rows by default. Page
  // through with the Range header to pull the full history.
  const all = [];
  const PAGE = 1000;
  try {
    for (let from = 0; from < 50000; from += PAGE) {
      const to = from + PAGE - 1;
      const r = await fetch(
        `${SUPABASE_URL}/rest/v1/plonker_round?select=*&order=played_at.desc`,
        { headers: { ...SUPA_HEADERS, Range: `${from}-${to}` } }
      );
      if (!r.ok) break;
      const rows = await r.json();
      if (!rows.length) break;
      all.push(...rows);
      if (rows.length < PAGE) break;
    }
  } catch (e) {
    console.warn('supabase fetch failed', e);
  }
  return all;
}

// ============================================================
// Cross-device progress sync (Supabase, single shared 'self' row).
// localStorage is the primary store; cloud is a write-through merge target.
// ============================================================
const PROGRESS_ROW_ID = 'self';

const PROGRESS_LS_KEYS = {
  card_stats:  'plonker:card-stats',
  blacklist:   'plonker:card-blacklist',
  topic_stats: 'plonker:topic-stats',
  quiz_stats:  'plonker:quiz-stats',
  // 'leitner' is special — many keys with the prefix 'plonker:leitner:'
};

// Read all progress out of localStorage into a single shape that maps to
// the plonker_progress table columns.
function readLocalProgress() {
  const json = (k, fb) => { try { return JSON.parse(localStorage.getItem(k)) ?? fb; } catch { return fb; } };
  const leitner = {};
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (!k?.startsWith('plonker:leitner:')) continue;
    leitner[k.slice('plonker:leitner:'.length)] = json(k, null);
  }
  return {
    card_stats:  json(PROGRESS_LS_KEYS.card_stats,  {}),
    blacklist:   json(PROGRESS_LS_KEYS.blacklist,   []),
    topic_stats: json(PROGRESS_LS_KEYS.topic_stats, {}),
    quiz_stats:  json(PROGRESS_LS_KEYS.quiz_stats,  {}),
    leitner,
  };
}

// Write a merged progress object back into localStorage, including the
// per-key plonker:leitner:* entries.
function writeLocalProgress(p) {
  if (!p) return;
  if (p.card_stats)  localStorage.setItem(PROGRESS_LS_KEYS.card_stats,  JSON.stringify(p.card_stats));
  if (p.blacklist)   localStorage.setItem(PROGRESS_LS_KEYS.blacklist,   JSON.stringify(p.blacklist));
  if (p.topic_stats) localStorage.setItem(PROGRESS_LS_KEYS.topic_stats, JSON.stringify(p.topic_stats));
  if (p.quiz_stats)  localStorage.setItem(PROGRESS_LS_KEYS.quiz_stats,  JSON.stringify(p.quiz_stats));
  if (p.leitner) {
    for (const [k, v] of Object.entries(p.leitner)) {
      if (v == null) continue;
      localStorage.setItem(`plonker:leitner:${k}`, JSON.stringify(v));
    }
  }
}

// Merge cloud + local. Per-card-key fields (card_stats, leitner) take the
// entry with the newer lastSeen. topic_stats/quiz_stats sum their counts
// (additive, since both devices may have practised in parallel). blacklist
// is a union.
function mergeProgress(cloud, local) {
  const out = {};
  // card_stats: newer lastSeen wins per cardKey
  out.card_stats = { ...(cloud.card_stats || {}) };
  for (const [k, v] of Object.entries(local.card_stats || {})) {
    const c = out.card_stats[k];
    if (!c || (v.lastSeen || 0) >= (c.lastSeen || 0)) out.card_stats[k] = v;
  }
  // leitner: same rule
  out.leitner = { ...(cloud.leitner || {}) };
  for (const [k, v] of Object.entries(local.leitner || {})) {
    const c = out.leitner[k];
    if (!c || (v.lastSeen || 0) >= (c.lastSeen || 0)) out.leitner[k] = v;
  }
  // blacklist: set union
  out.blacklist = [...new Set([
    ...(cloud.blacklist || []),
    ...(local.blacklist || []),
  ])];
  // topic_stats / quiz_stats: per key, take the row with higher count
  const mergeStatsMap = (a, b) => {
    const r = { ...(a || {}) };
    for (const [k, v] of Object.entries(b || {})) {
      const c = r[k];
      if (!c || (v.count || 0) > (c.count || 0)) r[k] = v;
    }
    return r;
  };
  out.topic_stats = mergeStatsMap(cloud.topic_stats, local.topic_stats);
  out.quiz_stats  = mergeStatsMap(cloud.quiz_stats,  local.quiz_stats);
  return out;
}

async function loadCloudProgress() {
  try {
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/plonker_progress?id=eq.${PROGRESS_ROW_ID}&select=*`,
      { headers: SUPA_HEADERS }
    );
    if (!r.ok) return null;
    const rows = await r.json();
    return rows[0] || null;
  } catch (e) {
    console.warn('cloud progress fetch failed:', e);
    return null;
  }
}

async function pushCloudProgress(progress) {
  try {
    // PATCH the singleton row. The server will set updated_at via trigger.
    const r = await fetch(
      `${SUPABASE_URL}/rest/v1/plonker_progress?id=eq.${PROGRESS_ROW_ID}`,
      {
        method: 'PATCH',
        headers: { ...SUPA_HEADERS, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
        body: JSON.stringify({
          card_stats:  progress.card_stats,
          leitner:     progress.leitner,
          blacklist:   progress.blacklist,
          topic_stats: progress.topic_stats,
          quiz_stats:  progress.quiz_stats,
        }),
      }
    );
    return r.ok;
  } catch (e) {
    console.warn('cloud progress push failed:', e);
    return false;
  }
}

// Debounced cloud push so we don't hit the API on every single answer.
let _pushTimer = null;
function schedulePushProgress() {
  clearTimeout(_pushTimer);
  _pushTimer = setTimeout(() => {
    const local = readLocalProgress();
    pushCloudProgress(local);
  }, 1500);
}

// On boot: pull cloud, merge, write back. After this, localStorage and the
// cloud row are aligned, and the rest of the app reads localStorage as
// usual. Failures are logged and the app falls back to pure local mode.
async function initProgressSync() {
  const cloud = await loadCloudProgress();
  if (!cloud) return;
  const local = readLocalProgress();
  const merged = mergeProgress(cloud, local);
  writeLocalProgress(merged);
  // Push the merged state so the cloud reflects anything local that wasn't
  // there yet.
  pushCloudProgress(merged);
}

// ---------- focus resolution ----------
// Returns the Set of ISO2 codes "in scope" for the current focus.
function focusCountries() {
  const { type, value } = state.focus;
  if (type === 'global') return state.countries;
  if (type === 'continent') {
    const group = REGION_GROUPS[value] || [];
    return new Set(group.filter(cc => state.countries.has(cc)));
  }
  if (type === 'region') {
    const group = REGION_GROUPS[value] || [];
    return new Set(group.filter(cc => state.countries.has(cc)));
  }
  if (type === 'country') return new Set([value]);
  if (type === 'topic') {
    const t = state.topics?.find(x => x.id === value);
    if (!t || t.mode === 'text_subregion') return state.countries;
    return state.countries;
  }
  if (type === 'personal') {
    // Personal lists: weak-spots / confused-pairs / recent-misses. Build
    // from the GG round history loaded into state.personalData.
    const set = new Set();
    const list = (state.personalData?.[value]?.countries) || [];
    for (const cc of list) if (state.countries.has(cc)) set.add(cc);
    return set.size ? set : state.countries;
  }
  return state.countries;
}

// Build personal study lists from imported GG rounds. Cached so we don't
// re-aggregate on every dropdown change.
async function ensurePersonalData() {
  if (state.personalData) return state.personalData;
  const rounds = state.rounds && state.rounds.length ? state.rounds : await loadRounds();
  state.rounds = rounds;
  // Aggregate per-country avg score + miss count
  const agg = {};
  const confusedPairs = {};   // `${actual}->${guessed}` -> count
  const recentMisses = [];
  for (const r of rounds) {
    const cc = r.actual_country_iso2;
    if (!cc) continue;
    const a = agg[cc] || (agg[cc] = { count: 0, total: 0, miss: 0 });
    a.count++;
    if (typeof r.round_score === 'number') a.total += r.round_score;
    if (r.guess_country_iso2 && r.guess_country_iso2 !== cc) {
      a.miss++;
      const k = `${cc}->${r.guess_country_iso2}`;
      confusedPairs[k] = (confusedPairs[k] || 0) + 1;
      if (recentMisses.length < 200) recentMisses.push(cc);
    }
  }
  for (const a of Object.values(agg)) a.avg = a.count ? a.total / a.count : 0;
  // Weak spots: bottom 30 by avg score, requiring at least 2 rounds
  const weak = Object.entries(agg)
    .filter(([, v]) => v.count >= 2)
    .sort((a, b) => a[1].avg - b[1].avg)
    .slice(0, 30)
    .map(([cc]) => cc);
  // Confused pairs: extract each country in any pair >= 2 occurrences
  const confusedSet = new Set();
  for (const [pair, n] of Object.entries(confusedPairs)) {
    if (n >= 2) {
      const [a, g] = pair.split('->');
      confusedSet.add(a); confusedSet.add(g);
    }
  }
  state.personalData = {
    'weak-spots':     { countries: weak, label: `${weak.length} weakest`, hint: `bottom ${weak.length} by avg score (≥2 rounds each)` },
    'confused-pairs': { countries: [...confusedSet], pairs: confusedPairs, label: `${confusedSet.size} countries`, hint: `${Object.keys(confusedPairs).filter(k => confusedPairs[k] >= 2).length} confused pairs` },
    'recent-misses':  { countries: [...new Set(recentMisses.slice(0, 50))], label: `${new Set(recentMisses.slice(0, 50)).size} unique`, hint: 'countries from your most recent missed rounds' },
  };
  return state.personalData;
}

// ---------- tab switching ----------
function showTab(name) {
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  $('view-home').hidden = name !== 'home';
  $('view-quiz').hidden = name !== 'quiz';
  $('view-dash').hidden = name !== 'dash';
  if (name === 'dash') refreshDashboard();
  if (name === 'quiz') ensureQuizMap();
}

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    if (btn.disabled) return;
    showTab(btn.dataset.tab);
  });
});

// ============================================================
// HOME PAGE
// ============================================================
function populateCountrySelect() {
  const sel = $('country-select');
  const sorted = [...state.countries].sort((a, b) =>
    (state.tips[a]?.name || a).localeCompare(state.tips[b]?.name || b)
  );
  sel.innerHTML = sorted.map(cc =>
    `<option value="${cc}">${flagEmoji(cc)} ${escapeHtml(state.tips[cc]?.name || cc)}</option>`
  ).join('');
}

function populateTopicSelect() {
  const sel = $('topic-select');
  // Group by topic.group
  const groups = {};
  for (const t of state.topics) {
    (groups[t.group] = groups[t.group] || []).push(t);
  }
  // Annotate label with pool size for the user
  sel.innerHTML = Object.entries(groups).map(([g, items]) => `
    <optgroup label="${escapeHtml(g)}">
      ${items.map(t => {
        const pool = t.buildPool(state);
        const n = pool.length;
        return `<option value="${t.id}" ${n === 0 ? 'disabled' : ''}>${escapeHtml(t.label)} (${n})</option>`;
      }).join('')}
    </optgroup>
  `).join('');
}

function selectFocusCard(card) {
  document.querySelectorAll('.focus-card').forEach(c => c.classList.toggle('selected', c === card));
  const type = card.dataset.focusType;
  let value = null;
  if (type === 'continent') value = $('continent-select').value;
  if (type === 'region') value = $('region-select').value;
  if (type === 'country') value = $('country-select').value;
  if (type === 'topic') value = $('topic-select').value;
  if (type === 'personal') {
    value = $('personal-select').value;
    // Lazy-build personal data on first selection
    ensurePersonalData().then(() => updateFocusMeta());
  }
  state.focus = { type, value };
  updateFocusMeta();
  renderRegionTips();
}

function updateFocusMeta() {
  const cc = focusCountries();
  $('meta-global').textContent = `${state.countries.size} countries`;
  $('meta-continent').textContent = state.focus.type === 'continent' ? `${cc.size} covered` : `${countCovered(REGION_GROUPS[$('continent-select').value])} covered`;
  $('meta-region').textContent = state.focus.type === 'region' ? `${cc.size} countries` : `${(REGION_GROUPS[$('region-select').value] || []).length} countries`;
  $('meta-country').textContent = state.focus.type === 'country'
    ? `${(state.tips[state.focus.value]?.metas || []).length} metas`
    : 'pick one';
  // Topic focus: show how many cards are in the selected topic's pool
  const topicId = state.focus.type === 'topic' ? state.focus.value : $('topic-select').value;
  const t = state.topics.find(x => x.id === topicId);
  if (t) {
    const n = t.buildPool(state).length;
    $('meta-topic').textContent = `${n} cards`;
  } else {
    $('meta-topic').textContent = 'pick one';
  }
  // Personal focus: show generated label
  const personalId = state.focus.type === 'personal' ? state.focus.value : $('personal-select')?.value;
  const personal = state.personalData?.[personalId];
  $('meta-personal').textContent = personal
    ? `${personal.label} · ${personal.hint}`
    : 'computed from GG history';
  $('start-btn').disabled = false;
}

function countCovered(group) {
  return (group || []).filter(cc => state.countries.has(cc)).length;
}

function renderRegionTips() {
  const wrap = $('region-tips');
  const { type, value } = state.focus;
  if (type === 'global' || type === 'continent') {
    wrap.innerHTML = '';
    return;
  }

  if (type === 'country') {
    const c = state.tips[value];
    if (!c) { wrap.innerHTML = ''; return; }
    const cards = (c.metas || []).slice(0, 8).map(m => `
      <div class="tip-card">
        ${m.images?.[0] ? `<img src="${escapeHtml(m.images[0])}" alt="">` : ''}
        <div class="tcontent">
          <div class="ttype">${escapeHtml(m.type || '')}</div>
          <div class="ttitle">${escapeHtml(m.title || '')}</div>
          <div class="tdesc">${escapeHtml(m.description || '')}</div>
        </div>
      </div>
    `).join('');
    wrap.innerHTML = `<h3>${flagEmoji(value)} ${escapeHtml(c.name)} &mdash; metas to study</h3><div class="tip-list">${cards || '<div style="color:var(--muted)">No bundled metas for this country.</div>'}</div>`;
    wireThumbnailLenses(wrap);
    return;
  }

  // region — show a few representative metas pulled from each country in scope
  const group = REGION_GROUPS[value] || [];
  const tips = [];
  for (const cc of group) {
    if (!state.countries.has(cc)) continue;
    const c = state.tips[cc];
    if (!c?.metas?.length) continue;
    const m = c.metas[0];
    tips.push({ cc, name: c.name, m });
    if (tips.length >= 8) break;
  }
  wrap.innerHTML = tips.length
    ? `<h3>Sample metas in this region</h3><div class="tip-list">${tips.map(t => `
        <div class="tip-card">
          ${t.m.images?.[0] ? `<img src="${escapeHtml(t.m.images[0])}" alt="">` : ''}
          <div class="tcontent">
            <div class="ttype">${flagEmoji(t.cc)} ${escapeHtml(t.name)}</div>
            <div class="ttitle">${escapeHtml(t.m.title || t.m.type || '')}</div>
            <div class="tdesc">${escapeHtml(t.m.description || '')}</div>
          </div>
        </div>`).join('')}</div>`
    : '';
  // Wire hover-magnify on the freshly-rendered thumbnails
  wireThumbnailLenses(wrap);
}

// Hover-magnify behavior for thumbnail images (home-page tip cards and
// fact-sheet meta cards). Hovering an <img> shows a circular lens floating
// near the cursor that displays a 3× zoom of the patch under the cursor —
// same UX as the quiz image lens but appended to the parent card so it
// can sit OUTSIDE the small thumbnail bounds.
function wireThumbnailLenses(scope) {
  const LENS = 220, SCALE = 3;
  scope.querySelectorAll('.tip-card img, .fs-meta-card img').forEach(img => {
    if (img.dataset.lensWired === '1') return;
    img.dataset.lensWired = '1';
    const card = img.closest('.tip-card, .fs-meta-card');
    if (!card) return;
    let lens = null;
    img.addEventListener('mouseenter', () => {
      if (lens || !img.naturalWidth) return;
      lens = document.createElement('div');
      lens.className = 'tip-lens';
      lens.style.backgroundImage = `url("${img.src.replace(/"/g, '\\"')}")`;
      card.appendChild(lens);
    });
    img.addEventListener('mousemove', (e) => {
      if (!lens) return;
      const ir = img.getBoundingClientRect();
      const cr = card.getBoundingClientRect();
      // Patch coords inside the displayed thumbnail (with object-fit: cover —
      // the image pixel-aspect == display-aspect, so direct mapping works).
      const fx = (e.clientX - ir.left) / ir.width;
      const fy = (e.clientY - ir.top)  / ir.height;
      const bgW = img.naturalWidth  * SCALE * (ir.width  / img.naturalWidth);
      const bgH = img.naturalHeight * SCALE * (ir.height / img.naturalHeight);
      lens.style.backgroundSize = `${bgW}px ${bgH}px`;
      lens.style.backgroundPosition =
        `${-(fx * bgW - LENS / 2)}px ${-(fy * bgH - LENS / 2)}px`;
      // Position lens centered on cursor, relative to the card box.
      lens.style.left = (e.clientX - cr.left - LENS / 2) + 'px';
      lens.style.top  = (e.clientY - cr.top  - LENS / 2) + 'px';
    });
    img.addEventListener('mouseleave', () => {
      if (lens) { lens.remove(); lens = null; }
    });
    // Touch handlers for mobile — drag finger to magnify.
    const ttouch = (e) => {
      if (!e.touches?.[0]) return;
      if (!lens) {
        if (!img.naturalWidth) return;
        lens = document.createElement('div');
        lens.className = 'tip-lens';
        lens.style.backgroundImage = `url("${img.src.replace(/"/g, '\\"')}")`;
        card.appendChild(lens);
      }
      e.preventDefault();
      const t = e.touches[0];
      const ir = img.getBoundingClientRect();
      const cr = card.getBoundingClientRect();
      const fx = (t.clientX - ir.left) / ir.width;
      const fy = (t.clientY - ir.top)  / ir.height;
      const bgW = img.naturalWidth  * SCALE * (ir.width  / img.naturalWidth);
      const bgH = img.naturalHeight * SCALE * (ir.height / img.naturalHeight);
      lens.style.backgroundSize = `${bgW}px ${bgH}px`;
      lens.style.backgroundPosition =
        `${-(fx * bgW - LENS / 2)}px ${-(fy * bgH - LENS / 2)}px`;
      lens.style.left = (t.clientX - cr.left - LENS / 2) + 'px';
      lens.style.top  = (t.clientY - cr.top  - LENS / 2) + 'px';
    };
    const tend = () => { if (lens) { lens.remove(); lens = null; } };
    img.addEventListener('touchstart', ttouch, { passive: false });
    img.addEventListener('touchmove', ttouch, { passive: false });
    img.addEventListener('touchend', tend);
    img.addEventListener('touchcancel', tend);
  });
}

// ============================================================
// QUIZ — click-on-map mode
// ============================================================
const quiz = {
  map: null,
  geoLayer: null,
  pool: [],
  card: null,
  streak: 0,
  bestStreak: 0,
  correct: 0,
  total: 0,
  scoring: 'binary',
  awaitingClick: false,
  // Review queue for wrong answers: each entry is { card, reviewAt: scheduled
  // total at which it becomes due (random delay) }. Once due, has a high
  // chance of being picked over a fresh card.
  reviewQueue: [],
};

// Variable, non-fixed re-show window for a wrong answer.
// Pick a delay uniformly in [3, 8] cards from now, then a high-but-not-100%
// probability of choosing a due review on each subsequent pick.
const REVIEW_DELAY_MIN = 3;
const REVIEW_DELAY_MAX = 8;
const REVIEW_PICK_CHANCE = 0.65;

function ensureQuizMap() {
  if (quiz.map) {
    quiz.map.remove();
    quiz.map = null;
    quiz.geoLayer = null;
    quiz.subLayer = null;
  }
  quiz.map = L.map('quiz-map', {
    minZoom: 2,
    maxZoom: 8,
    worldCopyJump: false,
    zoomControl: true,
    attributionControl: false,
    // Use Canvas instead of SVG renderer — sidesteps the M0 0 SVG-projection bug.
    preferCanvas: true,
  });
}

function buildCountryLayer() {
  if (quiz.geoLayer) {
    quiz.map.removeLayer(quiz.geoLayer);
    quiz.geoLayer = null;
  }
  if (quiz.subLayer) {
    quiz.map.removeLayer(quiz.subLayer);
    quiz.subLayer = null;
  }
  quiz.geoLayer = L.geoJSON(state.geojson, {
    style: countryStyle,
    onEachFeature: (feat, layer) => {
      layer.on('click', () => onCountryClick(feat));
      const cc = feat.properties.ISO_A2_EH || feat.properties.ISO_A2;
      if (cc && cc !== '-99') {
        layer.bindTooltip(state.tips[cc]?.name || feat.properties.NAME || cc, { sticky: true, direction: 'top' });
      }
    },
  }).addTo(quiz.map);
}

function countryStyle(feat) {
  const cc = feat.properties.ISO_A2_EH || feat.properties.ISO_A2;
  return focusCountries().has(cc) ? STYLE_ELIGIBLE : STYLE_DISABLED;
}

// World map with a specific set of countries highlighted (for region MC mode).
// Styling is baked in at layer creation so we don't depend on canvas redraw
// after a separate setStyle pass.
function buildHighlightLayer(highlightCcs) {
  if (quiz.geoLayer) {
    quiz.map.removeLayer(quiz.geoLayer);
    quiz.geoLayer = null;
  }
  if (quiz.subLayer) {
    quiz.map.removeLayer(quiz.subLayer);
    quiz.subLayer = null;
  }
  quiz.geoLayer = L.geoJSON(state.geojson, {
    interactive: false,
    style: (feat) => {
      const cc = feat.properties.ISO_A2_EH || feat.properties.ISO_A2;
      return highlightCcs.has(cc) ? STYLE_HIGHLIGHT : STYLE_DISABLED;
    },
  }).addTo(quiz.map);
}

// Color presets for canvas rendering (CSS classes don't apply to canvas).
// Eligible: bright slate, clearly clickable.
// Disabled: still visible as land (mid-slate) so the user can navigate; only
//           the ocean is the very-dark background colour (#0a1421).
const STYLE_ELIGIBLE = { color: '#64748b', weight: 1.0, fillColor: '#3f4e63', fillOpacity: 1 };
const STYLE_DISABLED = { color: '#3a4658', weight: 0.7, fillColor: '#22303f', fillOpacity: 1 };
const STYLE_CORRECT  = { color: '#34d399', weight: 2, fillColor: '#10b981', fillOpacity: 1 };
const STYLE_WRONG    = { color: '#f87171', weight: 2, fillColor: '#ef4444', fillOpacity: 1 };
// Highlighted (used for region MC: shows the region in scope without making it clickable)
const STYLE_HIGHLIGHT = { color: '#fcd34d', weight: 1.6, fillColor: '#f59e0b', fillOpacity: 0.95 };
const HEAT_STYLES = [
  { color: '#475569', weight: 0.5, fillColor: '#ef4444', fillOpacity: 1 },
  { color: '#475569', weight: 0.5, fillColor: '#f59e0b', fillOpacity: 1 },
  { color: '#475569', weight: 0.5, fillColor: '#facc15', fillOpacity: 1 },
  { color: '#475569', weight: 0.5, fillColor: '#84cc16', fillOpacity: 1 },
  { color: '#475569', weight: 0.5, fillColor: '#10b981', fillOpacity: 1 },
];

// Outlying territories that we exclude from the *framing* bbox (kept clickable).
// Maps cc -> Set of admin-1 names to exclude when computing fit bounds.
const MAINLAND_EXCLUDE = {
  US: new Set(['Alaska', 'Hawaii']),
  FR: new Set(['Mayotte', 'Guadeloupe', 'Martinique', 'French Guiana', 'Réunion']),
  ES: new Set(['Canarias']),
  PT: new Set(['Azores', 'Madeira']),
  NL: new Set(['Aruba', 'Curaçao', 'Sint Maarten', 'Bonaire']),
  RU: new Set(['Chukotka Autonomous Okrug']),
};

function filterMainlandFeatures(cc, features) {
  const exclude = MAINLAND_EXCLUDE[cc];
  if (!exclude) return features;
  return features.filter(f => !exclude.has(f.properties.name));
}

function buildSubregionLayer(cc) {
  if (quiz.geoLayer) {
    quiz.map.removeLayer(quiz.geoLayer);
    quiz.geoLayer = null;
  }
  if (quiz.subLayer) {
    quiz.map.removeLayer(quiz.subLayer);
  }
  const features = state.admin1.features.filter(f => f.properties.iso_a2 === cc);
  quiz.subLayer = L.geoJSON({ type: 'FeatureCollection', features }, {
    style: () => STYLE_ELIGIBLE,
    onEachFeature: (feat, layer) => {
      layer.on('click', () => onSubregionClick(feat));
      const name = feat.properties.name;
      const fid = feat.properties.iso_3166_2 || feat.properties.code_local;
      layer.bindTooltip(name || fid, { sticky: true, direction: 'top' });
    },
  }).addTo(quiz.map);
  // Force a Leaflet canvas redraw — adding a layer right after fitBounds
  // doesn't always trigger one. A 1-pixel pan-and-restore does.
  quiz.map.panBy([1, 0], { animate: false });
  quiz.map.panBy([-1, 0], { animate: false });
}

// Style helper: with the canvas renderer we set fill/stroke options directly
// rather than via CSS classes. Map a "kind" string to a preset.
function setLayerKind(layer, kind) {
  const styles = {
    eligible: STYLE_ELIGIBLE,
    disabled: STYLE_DISABLED,
    correct: STYLE_CORRECT,
    wrong: STYLE_WRONG,
    highlight: STYLE_HIGHLIGHT,
    'heat-0': HEAT_STYLES[0],
    'heat-1': HEAT_STYLES[1],
    'heat-2': HEAT_STYLES[2],
    'heat-3': HEAT_STYLES[3],
    'heat-4': HEAT_STYLES[4],
  };
  const s = styles[kind] || STYLE_DISABLED;
  layer.setStyle(s);
}

// Filter regional metas out of the country-ID pool. These give the answer
// away because the meta describes a sub-region (and learnablemeta often
// embeds a regional reference map into the image itself).
const REGIONAL_PATTERN = /\b(north|south|east|west)(ern|wards?)?\b\s+(of|part|side|region|coast|portion|half)\b|\bsee (this|the) map\b|\bin (this|these) regions?\b|\b(most(ly)?|commonly|usually|specifically|only|mainly|primarily|predominantly|chiefly|exclusively) (found|seen|located|present|observed) in\b|\b(specific|distinct|exclusive|native|endemic|particular|unique) to\b|\b(around|near) [A-Z][a-zA-Z]+\b|\b(Northern|Southern|Eastern|Western) [A-Z][a-z]+\b|\bin the (north|south|east|west)\b/;

function isRegionalMeta(m) {
  const text = `${m.title || ''} ${m.description || ''} ${m.type || ''}`;
  return REGIONAL_PATTERN.test(text);
}

// Per-card blacklist. Two layers:
//   1. PREBUILT (state.ocrBlacklist) — OCR-detected images with country
//      names baked in (the "ESTONIA" watermark case). Ships with the app
//      via data/giveaway_blacklist.json.
//   2. USER (localStorage) — manually flagged via "Hide forever" button.
// loadCardBlacklist() returns the union. Either alone removes a card.
const BLACKLIST_KEY = 'plonker:card-blacklist';

// Reasons that are CONTEXT-dependent: not absolute giveaways, just narrow
// metas that aren't useful in broad quizzes. We keep them when the user is
// already focused on the relevant country (they explicitly chose to study
// that country in depth).
const CONTEXT_DEPENDENT_REASONS = new Set(['narrow_locale']);

function loadCardBlacklist(context = null) {
  // context: { focus: 'country' | 'topic' | …, cc: 'US' | … }
  // When focus === 'country' AND the blacklisted card belongs to that
  // same country AND the reason is context-dependent (currently only
  // 'narrow_locale'), the card is allowed back into the pool.
  const set = new Set();
  for (const [k, v] of Object.entries(state.ocrBlacklist || {})) {
    const reason = v?.reason || '';
    if (
      context && context.focus === 'country' && context.cc === v?.cc &&
      [...CONTEXT_DEPENDENT_REASONS].some(r => reason.includes(r))
    ) {
      // Context match — let this card through. Only skip if it ALSO carries
      // a non-context-dependent reason (e.g. country_name_in_image). We
      // detect that by checking whether stripping the context-dependent
      // tokens leaves anything substantive.
      const stripped = reason.split('/').map(s => s.trim())
        .filter(s => ![...CONTEXT_DEPENDENT_REASONS].some(r => s.startsWith(r)));
      if (stripped.length === 0) continue;   // ONLY narrow_locale → allow
    }
    set.add(k);
  }
  try {
    const user = JSON.parse(localStorage.getItem(BLACKLIST_KEY)) || [];
    for (const k of user) set.add(k);   // user blacklist always applies
  } catch {}
  return set;
}
function blacklistCard(cardKey) {
  if (!cardKey) return;
  const set = loadCardBlacklist();
  set.add(cardKey);
  localStorage.setItem(BLACKLIST_KEY, JSON.stringify([...set]));
  schedulePushProgress?.();
}
function unblacklistCard(cardKey) {
  const set = loadCardBlacklist();
  set.delete(cardKey);
  localStorage.setItem(BLACKLIST_KEY, JSON.stringify([...set]));
  schedulePushProgress?.();
}

function buildQuizPool() {
  const inScope = focusCountries();
  const isCountryFocus = state.focus.type === 'country';
  const isTopicFocus = state.focus.type === 'topic';
  const focusCc = state.focus.value;
  const pool = [];
  let skippedRegional = 0;

  // Topic-focus pool: each topic has its own buildPool, returning shaped cards
  if (isTopicFocus) {
    const topic = state.topics.find(t => t.id === state.focus.value);
    if (!topic) return pool;
    const blacklist = loadCardBlacklist();
    const rawCards = topic.buildPool(state);
    const cards = rawCards.filter(c => !c.cardKey || !blacklist.has(c.cardKey));
    if (rawCards.length !== cards.length) {
      console.log(`[plonker] Filtered ${rawCards.length - cards.length} blacklisted cards from topic pool`);
    }
    return cards.map((c, i) => ({
      mode: topic.mode,        // image_country | text_country | text_subregion | mc_text
      topicId: topic.id,
      countryCc: topic.countryCc || null,
      img: c.img,
      text: c.text,
      subtext: c.subtext,
      correctCcs: c.correctCcs,
      correctSubregionNames: c.correctSubregionNames,
      // mc_text-specific:
      options: c.options,
      correctOption: c.correctOption,
      highlightCcs: c.highlightCcs,
      description: c.description || '',
      cardKey: c.cardKey,
      idx: i,
      cc: (c.correctCcs && c.correctCcs[0]) || (c.highlightCcs && c.highlightCcs[0]) || topic.countryCc || null,
      type: topic.label,
      title: topic.label,
    }));
  }

  // Sub-region pool when focus = country (and we have admin-1 mapping for it)
  if (isCountryFocus && state.subregions?.[focusCc]) {
    const c = state.tips[focusCc];
    const regionMap = state.subregions[focusCc];
    // Pre-build a list of region names (longest-first so "New South Wales"
    // matches before "South Wales" would).
    const allRegionNames = Object.keys(regionMap)
      .sort((a, b) => b.length - a.length);
    const escapeRx = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    // Phrases preceding a region name that indicate COMPARISON rather than
    // location. If the immediately preceding text matches any of these, we
    // skip the region — it's a "looks like X" / "compared to X" reference,
    // not "this meta is in X".
    //
    // Notes on "like":
    //   - "looks/feels/seems like X" → comparison (skip)
    //   - "Like X, the Y also..."   → comparison at clause start (skip)
    //   - "states like X"           → exemplary "such as", LOCATION (keep)
    //
    // We therefore split on those three cases instead of treating bare
    // "like" as a comparison.
    const COMPARISON_BEFORE = new RegExp(
      '(?:' +
        // Plain comparison phrases
        '\\b(?:reminiscent of|similar(?:ly)? to|unlike|compared (?:to|with)|than|instead of|vs\\.?|versus|akin to|resembles?|resembling|reminds (?:you )?of|but not|except|whereas|rather than|missing from|absent from|not (?:found |seen |present )?in)\\s+(?:the\\s+)?(?:that of\\s+)?' +
        '|' +
        // Verb-prefixed "like"
        '\\b(?:looks?|looking|seems?|seemed|feels?|felt|appears?|appeared|kinda|sorta)\\s+like\\s+(?:the\\s+)?' +
        '|' +
        // Clause-starting "Like X, ..."
        '(?:^|[.!?]\\s+)Like\\s+(?:the\\s+)?' +
      ')$',
      'i'
    );
    let cardIdx = 0;
    // Sub-region quiz is launched FROM the country focus, so pass that
    // context — narrow-locale cards for this country are kept in the pool
    // (the player explicitly picked this country to study in depth).
    const subBlacklist = loadCardBlacklist({ focus: 'country', cc: focusCc });
    let skippedSubBlacklist = 0;
    for (const [regionName, polygonIds] of Object.entries(regionMap)) {
      const entries = (c?.regions || {})[regionName] || [];
      for (let j = 0; j < entries.length; j++) {
        const e = entries[j];
        if (!e.images?.[0]) continue;
        // Per-card blacklist check — uses the same key format as the
        // generators in scraper/detect_compendiums.py and detect_giveaway_images.py.
        const cardKey = `country:${focusCc}:region:${regionName}:${j}`;
        if (subBlacklist.has(cardKey)) { skippedSubBlacklist++; continue; }
        const baseIds = Array.isArray(polygonIds) ? polygonIds : [polygonIds];
        const correctIds = new Set(baseIds);
        const correctNames = new Set([regionName]);
        // Scan description for mentions of OTHER admin-1 region names of the
        // same country. Only add them if mentioned in a LOCATION context —
        // skip "reminiscent of X" / "similar to X" / "unlike X" etc., which
        // are comparative references, not locations.
        const text = `${e.title || ''} ${e.text || e.description || ''}`;
        for (const otherName of allRegionNames) {
          if (otherName === regionName) continue;
          const rx = new RegExp(`\\b${escapeRx(otherName)}\\b`, 'i');
          const m = rx.exec(text);
          if (!m) continue;
          // Inspect ~40 characters preceding the match for a comparison
          // phrase. If found, this mention is NOT a location indicator.
          const before = text.slice(Math.max(0, m.index - 40), m.index);
          if (COMPARISON_BEFORE.test(before)) continue;
          const otherIds = regionMap[otherName];
          const arr = Array.isArray(otherIds) ? otherIds : [otherIds];
          for (const id of arr) correctIds.add(id);
          correctNames.add(otherName);
        }
        // Geographic phrase expansion: descriptions often use multi-region
        // descriptors like "east of the Urals" / "northern Caucasus" /
        // "the prairies" that don't map to any single admin-1 name. Each
        // phrase in geographic_aliases.json expands to a SET of regions
        // that all count as correct answers.
        const aliases = state.geoAliases?.[focusCc] || {};
        const lowered = text.toLowerCase();
        for (const [phrase, regionList] of Object.entries(aliases)) {
          if (phrase.startsWith('_')) continue;   // skip _meta keys
          // Use a word-boundary regex so "east of the urals" doesn't match
          // "southeast of the urals" partially.
          const phraseRx = new RegExp(`\\b${escapeRx(phrase)}\\b`, 'i');
          const m = phraseRx.exec(lowered);
          if (!m) continue;
          // Same comparison-phrase guard as for region names above.
          const before = lowered.slice(Math.max(0, m.index - 40), m.index);
          if (COMPARISON_BEFORE.test(before)) continue;
          for (const regionName2 of regionList) {
            const ids = regionMap[regionName2];
            if (!ids) continue;
            const arr = Array.isArray(ids) ? ids : [ids];
            for (const id of arr) correctIds.add(id);
            correctNames.add(regionName2);
          }
        }
        pool.push({
          mode: 'subregion',
          cc: focusCc,
          name: c?.name || focusCc,
          regionName: [...correctNames].join(' / '),
          polygonIds: [...correctIds],
          type: e.type || 'Region',
          title: e.title || regionName,
          img: e.images[0],
          description: e.text || e.description || '',
          comparison: e.comparison || '',
          cardKey,
          idx: cardIdx++,
        });
      }
    }
    // ALSO include country-level metas[] cards as "click anywhere in <country>"
    // cards. These are whole-country metas (Catalina car, Golden Gate car,
    // and other narrow-locale cards) that are valid in a country-focused
    // study session — the player explicitly chose this country.
    const allPolyIds = new Set();
    for (const v of Object.values(regionMap)) {
      const arr = Array.isArray(v) ? v : [v];
      for (const id of arr) allPolyIds.add(id);
    }
    const allPolyArr = [...allPolyIds];
    for (let i = 0; i < (c?.metas || []).length; i++) {
      const m = c.metas[i];
      if (!m.images?.[0]) continue;
      const cardKey = `country:${focusCc}:${i}`;
      if (subBlacklist.has(cardKey)) { skippedSubBlacklist++; continue; }
      pool.push({
        mode: 'subregion',
        cc: focusCc,
        name: c?.name || focusCc,
        regionName: c?.name || focusCc,    // "click anywhere in USA"
        polygonIds: allPolyArr,
        type: m.type || 'Meta',
        title: m.title || '',
        img: m.images[0],
        description: m.description || '',
        comparison: m.comparison || '',
        cardKey,
        idx: cardIdx++,
      });
    }
    // If country has no quizzable sub-regions, fall through to country mode
    if (pool.length) {
      console.log(`[plonker] Sub-region pool for ${focusCc}: ${pool.length} cards across ${Object.keys(regionMap).length} regions${skippedSubBlacklist ? ` (skipped ${skippedSubBlacklist} blacklisted)` : ''}`);
      return pool;
    }
  }

  // Country-level pool (default). When focus = country, narrow-locale cards
  // for that country are kept in the pool; when focus = global / continent /
  // region, only broad metas appear.
  const ctx = isCountryFocus ? { focus: 'country', cc: focusCc } : null;
  const blacklist = loadCardBlacklist(ctx);
  let skippedBlacklist = 0;
  for (const cc of inScope) {
    const c = state.tips[cc];
    if (!c?.metas?.length) continue;
    c.metas.forEach((m, i) => {
      if (!m.images?.[0]) return;
      if (isRegionalMeta(m)) { skippedRegional++; return; }
      const cardKey = `country:${cc}:${i}`;
      if (blacklist.has(cardKey)) { skippedBlacklist++; return; }
      pool.push({
        mode: 'country',
        cc, name: c.name, type: m.type, title: m.title,
        img: m.images[0], description: m.description,
        comparison: m.comparison, idx: i,
        cardKey,
      });
    });
  }
  if (skippedRegional || skippedBlacklist) {
    console.log(`[plonker] Filtered ${skippedRegional} regional + ${skippedBlacklist} blacklisted from quiz pool`);
  }
  return pool;
}

function startQuiz() {
  quiz.scoring = $('scoring-select').value;
  quiz.streak = 0;
  quiz.bestStreak = 0;
  quiz.correct = 0;
  quiz.total = 0;
  quiz.reviewQueue = [];
  quiz.pool = buildQuizPool();
  if (!quiz.pool.length) {
    alert('No metas in this focus. Pick a different one.');
    return;
  }

  document.querySelector('.tab[data-tab="quiz"]').disabled = false;
  showTab('quiz');
  // Two-step delay: first ensure the tab is painted and the container has
  // real dimensions, THEN initialize Leaflet. requestAnimationFrame alone
  // races the layout — Leaflet's SVG renderer reads getBoundingClientRect
  // synchronously and gets 0×0 if the layout pass hasn't run yet.
  setTimeout(() => {
    ensureQuizMap();
    const firstMode = quiz.pool[0]?.mode;
    const isSub = firstMode === 'subregion' || firstMode === 'text_subregion';
    const isMc  = firstMode === 'mc_text';
    if (isMc) {
      // Region MC: world map shown for context with the region highlighted.
      // Style highlight directly on layer creation (canvas redraw post-add
      // is unreliable).
      const highlightCcs = new Set(quiz.pool[0].highlightCcs || []);
      buildHighlightLayer(highlightCcs);
      // Fit bounds to highlighted region (with some padding) so the user
      // can see what region is being asked about.
      if (highlightCcs.size && quiz.geoLayer) {
        const layers = [];
        quiz.geoLayer.eachLayer(layer => {
          const cc = layer.feature.properties.ISO_A2_EH || layer.feature.properties.ISO_A2;
          if (highlightCcs.has(cc)) layers.push(layer);
        });
        if (layers.length) {
          quiz.map.fitBounds(L.featureGroup(layers).getBounds().pad(0.5), { animate: false });
        } else {
          quiz.map.setView([20, 0], 2);
        }
      } else {
        quiz.map.setView([20, 0], 2);
      }
    } else if (isSub) {
      // For sub-region mode: fitBounds FIRST so the renderer's pixel origin
      // is correct before any layer is added (mirroring how country mode
      // does setView before adding its layer).
      const cc = quiz.pool[0].cc || quiz.pool[0].countryCc;
      const features = state.admin1.features.filter(f => f.properties.iso_a2 === cc);
      const main = filterMainlandFeatures(cc, features);
      const bounds = L.geoJSON({ type: 'FeatureCollection', features: main }).getBounds();
      if (bounds.isValid()) {
        quiz.map.fitBounds(bounds.pad(0.1), { animate: false });
      } else {
        quiz.map.setView([20, 0], 2);
      }
      buildSubregionLayer(cc);
    } else {
      quiz.map.setView([20, 0], 2);
      buildCountryLayer();
      refitMapToFocus();
      refreshGeoStyles();
    }
    // Force SVG renderer to recompute paths after layer + view are set.
    setTimeout(() => quiz.map.invalidateSize(), 0);
    presentNextCard();
  }, 50);
}

function refitMapToFocus() {
  const inScope = focusCountries();
  const layers = [];
  quiz.geoLayer.eachLayer((layer) => {
    const f = layer.feature;
    const cc = f.properties.ISO_A2_EH || f.properties.ISO_A2;
    if (inScope.has(cc)) layers.push(layer);
  });
  if (!layers.length) {
    quiz.map.setView([20, 0], 2);
    return;
  }
  const group = L.featureGroup(layers);
  quiz.map.fitBounds(group.getBounds().pad(0.15), { animate: false });
}

function refreshGeoStyles() {
  quiz.geoLayer.eachLayer((layer) => {
    const cc = layer.feature.properties.ISO_A2_EH || layer.feature.properties.ISO_A2;
    const eligible = focusCountries().has(cc);
    setLayerKind(layer, eligible ? 'eligible' : 'disabled');
    layer.options.interactive = eligible;
  });
}

function presentNextCard() {
  if (!quiz.pool.length) {
    alert('Pool exhausted! Restart for a fresh round.');
    return endQuiz();
  }
  // Track the card we just showed so we can avoid serving it back-to-back.
  // Identify by cardKey, falling back to (cc, idx) when keys aren't unique.
  const lastKey = quiz.card?.cardKey
    ?? (quiz.card ? `${quiz.card.cc}:${quiz.card.idx}` : null);
  const isLast = (c) => {
    if (!lastKey) return false;
    const k = c.cardKey ?? `${c.cc}:${c.idx}`;
    return k === lastKey;
  };
  // Spaced-repetition first: if any wrong-answer review is due (its scheduled
  // reviewAt has passed), pick one with REVIEW_PICK_CHANCE probability.
  const dueIdx = [];
  for (let i = 0; i < quiz.reviewQueue.length; i++) {
    if (quiz.reviewQueue[i].reviewAt <= quiz.total
        && !isLast(quiz.reviewQueue[i].card)) {
      dueIdx.push(i);
    }
  }
  if (dueIdx.length && Math.random() < REVIEW_PICK_CHANCE) {
    const pickPos = dueIdx[Math.floor(Math.random() * dueIdx.length)];
    quiz.card = quiz.reviewQueue[pickPos].card;
    quiz.reviewQueue.splice(pickPos, 1);
    quiz.awaitingClick = true;
  } else {
    // Leitner-weighted random pick over the full pool, EXCLUDING the card
    // we just showed (so the same prompt never appears twice in a row).
    // Fall back to including it only when the pool is size 1.
    const eligible = quiz.pool.length > 1
      ? quiz.pool.filter(c => !isLast(c))
      : quiz.pool;
    const weights = eligible.map(c => Math.max(1, 6 - getLeitnerBox(c.cc, c.idx)));
    const total = weights.reduce((a, b) => a + b, 0);
    let roll = Math.random() * total;
    let pickIdx = 0;
    for (let i = 0; i < eligible.length; i++) {
      roll -= weights[i];
      if (roll <= 0) { pickIdx = i; break; }
    }
    quiz.card = eligible[pickIdx];
    quiz.awaitingClick = true;
  }

  // Header
  let metaText;
  if (quiz.card.mode === 'subregion') {
    metaText = `${state.tips[quiz.card.cc]?.name || quiz.card.cc} → ${quiz.card.type || 'Region'}`;
  } else if (quiz.card.mode === 'text_subregion') {
    metaText = `${state.tips[quiz.card.countryCc]?.name || quiz.card.countryCc} → ${quiz.card.type}`;
  } else {
    metaText = quiz.card.type || 'Meta';
  }
  $('quiz-meta').textContent = metaText;

  // Card body — image vs text card
  const imgEl = $('quiz-img');
  const textEl = $('quiz-text-card');
  const wrapEl = document.querySelector('.qimg-wrap');
  const maskEl = $('quiz-img-mask');
  const textModes = new Set(['text_country', 'text_subregion', 'mc_text']);
  if (textModes.has(quiz.card.mode)) {
    imgEl.style.display = 'none';
    if (wrapEl) wrapEl.classList.remove('show-mask');
    textEl.hidden = false;
    textEl.querySelector('.qtext-main').textContent = quiz.card.text || '';
    textEl.querySelector('.qtext-sub').textContent = quiz.card.subtext || '';
    // If the prompt is a 2-4 digit number (area code, calling code, etc.)
    // render a phone keypad next to it with the digits highlighted, so the
    // user can build spatial / T9-letter mnemonics as they study.
    renderKeypad(quiz.card.text || '');
  } else {
    imgEl.style.display = '';
    textEl.hidden = true;
    renderKeypad('');   // hide the keypad for non-text cards
    if (quiz.card.img) imgEl.src = quiz.card.img;
    // Show the inset-mask only for country-ID modes where the mask blocks
    // a giveaway. Reset to "masked" on each new card so user has to click
    // to peek if they want to see the corner.
    if (wrapEl) {
      const showMask = quiz.card.mode === 'country'
                    || quiz.card.mode === 'image_country'
                    || quiz.card.mode === 'subregion';
      wrapEl.classList.toggle('show-mask', showMask);
      if (maskEl) {
        maskEl.classList.remove('disabled');
        // Reset mask box for new card (default corner) until detector sets it
        maskEl.style.cssText = '';
        maskEl.classList.remove('detected', 'no-inset');
      }
      if (showMask) {
        // Auto-detect the inset's bbox in the actual image and reposition
        // the mask over it. Falls back to default corner mask if detection
        // finds nothing.
        const cardKey = quiz.card.cardKey;
        const onLoad = () => {
          if (quiz.card?.cardKey !== cardKey) return;   // card changed mid-flight
          const box = detectInsetBox(imgEl);
          applyMaskBox(maskEl, box);
        };
        if (imgEl.complete && imgEl.naturalWidth > 0) onLoad();
        else imgEl.addEventListener('load', onLoad, { once: true });
      }
    }
  }

  // MC button row (only for mc_text mode)
  const mcEl = $('quiz-mc');
  if (quiz.card.mode === 'mc_text') {
    mcEl.hidden = false;
    mcEl.innerHTML = (quiz.card.options || []).map(o =>
      `<button class="qmc-btn" data-opt="${escapeHtml(o)}">${escapeHtml(o)}</button>`
    ).join('');
    mcEl.querySelectorAll('.qmc-btn').forEach(btn => {
      btn.addEventListener('click', () => onMcClick(btn.dataset.opt));
    });
    // Re-highlight the region on the map for the new card. We rebuild the
    // layer (cheap) so canvas styling is baked in cleanly, then refit bounds.
    if (quiz.card.highlightCcs?.length && quiz.map) {
      const wanted = new Set(quiz.card.highlightCcs);
      buildHighlightLayer(wanted);
      const layers = [];
      quiz.geoLayer.eachLayer(layer => {
        const cc = layer.feature.properties.ISO_A2_EH || layer.feature.properties.ISO_A2;
        if (wanted.has(cc)) layers.push(layer);
      });
      if (layers.length) {
        quiz.map.fitBounds(L.featureGroup(layers).getBounds().pad(0.5), { animate: false });
      }
    }
  } else {
    mcEl.hidden = true;
    mcEl.innerHTML = '';
  }

  // Prompt
  if (quiz.card.mode === 'mc_text') {
    $('quiz-prompt').textContent = 'Pick the answer ↑';
  } else if (quiz.card.mode === 'subregion' || quiz.card.mode === 'text_subregion') {
    $('quiz-prompt').textContent = 'Click the sub-region on the map ↓';
  } else {
    $('quiz-prompt').textContent = 'Click the country on the map ↓';
  }

  $('quiz-feedback').hidden = true;
  $('quiz-feedback').className = 'quiz-feedback';
  $('quiz-next').hidden = true;
  updateQuizStats();
  // Reset any previous correct/wrong colours.
  if (quiz.card.mode === 'subregion' || quiz.card.mode === 'text_subregion') {
    quiz.subLayer?.eachLayer(layer => setLayerKind(layer, 'eligible'));
  } else if (quiz.card.mode === 'mc_text') {
    // Highlight layer is rebuilt in the block above with baked styling — skip
    // refreshGeoStyles which would clobber the highlight back to eligible.
  } else {
    refreshGeoStyles();
  }
}

function onSubregionClick(feat) {
  if (!quiz.awaitingClick) return;
  const m = quiz.card?.mode;
  if (m !== 'subregion' && m !== 'text_subregion') return;
  const p = feat.properties;
  const fid = p.iso_3166_2 || p.code_local || `${p.iso_a2}-${(p.name || 'X').slice(0,8)}`;
  let isRight;
  if (m === 'subregion') {
    isRight = (quiz.card.polygonIds || []).includes(fid);
  } else {
    // text_subregion: match by sub-region NAME (e.g., "California")
    const wantedNames = (quiz.card.correctSubregionNames || []).map(n => n.toLowerCase());
    isRight = wantedNames.includes((p.name || '').toLowerCase());
  }
  quiz.awaitingClick = false;
  finishQuizAnswer({ isRight, score: null, clickedFid: fid });
}

function onMcClick(opt) {
  if (!quiz.awaitingClick) return;
  if (quiz.card?.mode !== 'mc_text') return;
  quiz.awaitingClick = false;
  const isRight = opt === quiz.card.correctOption;
  // Visual: turn the picked button green/red, also reveal the correct one.
  document.querySelectorAll('.qmc-btn').forEach(btn => {
    btn.disabled = true;
    if (btn.dataset.opt === quiz.card.correctOption) btn.classList.add('correct');
    else if (btn.dataset.opt === opt) btn.classList.add('wrong');
  });
  finishQuizAnswer({ isRight, score: null });
}

function onCountryClick(feat) {
  if (!quiz.awaitingClick) return;
  const m = quiz.card?.mode;
  if (m === 'subregion' || m === 'text_subregion' || m === 'mc_text') return;
  const cc = feat.properties.ISO_A2_EH || feat.properties.ISO_A2;
  if (!cc || !focusCountries().has(cc)) return;
  quiz.awaitingClick = false;
  // Multi-answer: clicking ANY country in correctCcs counts as correct.
  const correct = quiz.card.correctCcs || [quiz.card.cc];
  const isRight = correct.includes(cc);
  const score = quiz.scoring === 'distance' && correct[0] ? computeDistanceScore(feat, correct[0]) : null;
  finishQuizAnswer({ isRight, score, clickedCc: cc });
}

// Shared answer-handling logic used by both country-mode and subregion-mode clicks.
function finishQuizAnswer({ isRight, score, clickedCc, clickedFid }) {
  quiz.total++;
  if (isRight) {
    quiz.correct++;
    quiz.streak++;
    if (quiz.streak > quiz.bestStreak) quiz.bestStreak = quiz.streak;
  } else {
    quiz.streak = 0;
  }

  // Stats + Leitner — keyed on the country (and idx). Always the *correct* cc,
  // so the dashboard reflects what you can't identify, not what you guessed.
  recordQuizAnswer(quiz.card.cc, isRight, score);
  recordTopicAnswer(quiz.card.topicId, isRight);
  if (quiz.card.cardKey) {
    recordCardAnswer(quiz.card.cardKey, quiz.card.cc, quiz.card.type, isRight);
  }
  const currentBox = getLeitnerBox(quiz.card.cc, quiz.card.idx);
  setLeitnerBox(quiz.card.cc, quiz.card.idx, isRight ? Math.min(5, currentBox + 1) : 1);

  // Schedule a review re-show if wrong (variable delay, 3-8 cards from now)
  if (!isRight) {
    const delay = REVIEW_DELAY_MIN + Math.floor(Math.random() * (REVIEW_DELAY_MAX - REVIEW_DELAY_MIN + 1));
    quiz.reviewQueue.push({
      card: quiz.card,
      reviewAt: quiz.total + delay,
    });
  }

  // Highlight on map (different layer per mode)
  const m = quiz.card.mode;
  if (m === 'mc_text') {
    // MC buttons already updated by onMcClick. Map stays at the regional
    // highlight from presentNextCard.
  } else if (m === 'subregion') {
    const correctIds = new Set(quiz.card.polygonIds || []);
    quiz.subLayer.eachLayer(layer => {
      const p = layer.feature.properties;
      const fid = p.iso_3166_2 || p.code_local || `${p.iso_a2}-${(p.name || 'X').slice(0,8)}`;
      if (correctIds.has(fid)) setLayerKind(layer, 'correct');
      else if (!isRight && fid === clickedFid) setLayerKind(layer, 'wrong');
    });
  } else if (m === 'text_subregion') {
    const wanted = new Set((quiz.card.correctSubregionNames || []).map(n => n.toLowerCase()));
    quiz.subLayer.eachLayer(layer => {
      const p = layer.feature.properties;
      const fid = p.iso_3166_2 || p.code_local || `${p.iso_a2}-${(p.name || 'X').slice(0,8)}`;
      const name = (p.name || '').toLowerCase();
      if (wanted.has(name)) setLayerKind(layer, 'correct');
      else if (!isRight && fid === clickedFid) setLayerKind(layer, 'wrong');
    });
  } else {
    const correctSet = new Set(quiz.card.correctCcs || [quiz.card.cc]);
    quiz.geoLayer.eachLayer(layer => {
      const lc = layer.feature.properties.ISO_A2_EH || layer.feature.properties.ISO_A2;
      if (correctSet.has(lc)) setLayerKind(layer, 'correct');
      else if (!isRight && lc === clickedCc) setLayerKind(layer, 'wrong');
    });
  }

  // Feedback text
  const fb = $('quiz-feedback');
  fb.hidden = false;
  fb.classList.add(isRight ? 'correct' : 'wrong');
  let verdict;
  if (m === 'mc_text') {
    verdict = isRight
      ? `Right — ${quiz.card.correctOption}`
      : `Wrong — answer was ${quiz.card.correctOption}`;
  } else if (m === 'subregion') {
    verdict = isRight ? `Right — ${quiz.card.regionName}` : `Wrong — answer was ${quiz.card.regionName}`;
  } else if (m === 'text_subregion') {
    const ans = (quiz.card.correctSubregionNames || []).join(', ');
    verdict = isRight ? `Right — ${ans}` : `Wrong — answer was ${ans}`;
  } else {
    const correct = quiz.card.correctCcs || [quiz.card.cc];
    if (correct.length === 1) {
      const name = state.tips[correct[0]]?.name || correct[0];
      verdict = isRight ? `Right — ${name}` : `Wrong — answer was ${name}`;
    } else {
      verdict = isRight ? `Right — one of ${correct.length} countries` : `Wrong — any of: ${correct.map(cc => state.tips[cc]?.name || cc).join(', ')}`;
    }
  }
  const scoreLine = score != null ? `<br><strong>${score}</strong> pts` : '';
  const flagPrefix = (quiz.card.correctCcs && quiz.card.correctCcs.length === 1)
    ? flagEmoji(quiz.card.correctCcs[0]) + ' '
    : (quiz.card.cc ? flagEmoji(quiz.card.cc) + ' ' : '');
  fb.innerHTML = `<strong>${flagPrefix}${verdict}</strong>${scoreLine}<br>${escapeHtml(quiz.card.description || '')}`;
  $('quiz-next').hidden = false;
  updateQuizStats();
  // Bring the Next button into view. Direct scrollTop assignment works
  // reliably; smooth-scroll APIs were inconsistent in testing.
  const btn = $('quiz-next');
  if (btn) {
    const rect = btn.getBoundingClientRect();
    if (rect.top > window.innerHeight - 60 || rect.top < 0) {
      const targetScroll = window.scrollY + rect.top - window.innerHeight + rect.height + 40;
      document.documentElement.scrollTop = Math.max(0, targetScroll);
    }
  }
}

// Crude distance score: bbox-centroid distance, mapped to 0-5000 via log scale.
// 0 km = 5000, 10000+ km = ~0. Decent enough proxy for the GG scoring curve.
function computeDistanceScore(clickedFeat, correctCc) {
  const correctLayer = findLayerByCc(correctCc);
  if (!correctLayer) return null;
  const a = clickedFeat.bbox ? boundsCenter(clickedFeat.bbox) : centerOfFeature(clickedFeat);
  const b = centerOfFeature(correctLayer.feature);
  const km = haversine(a.lat, a.lng, b.lat, b.lng);
  // Same scoring shape as GG world: 5000 * exp(-km / 2000).
  return Math.max(0, Math.round(5000 * Math.exp(-km / 2000)));
}
function findLayerByCc(cc) {
  let found = null;
  quiz.geoLayer.eachLayer((layer) => {
    const lc = layer.feature.properties.ISO_A2_EH || layer.feature.properties.ISO_A2;
    if (lc === cc) found = layer;
  });
  return found;
}
function boundsCenter(bbox) {
  return { lng: (bbox[0] + bbox[2]) / 2, lat: (bbox[1] + bbox[3]) / 2 };
}
function centerOfFeature(feat) {
  // Quick centroid via bounding box of all coordinates.
  const coords = [];
  const walk = (x) => {
    if (typeof x[0] === 'number') coords.push(x);
    else x.forEach(walk);
  };
  walk(feat.geometry.coordinates);
  let lat = 0, lng = 0;
  for (const [x, y] of coords) { lng += x; lat += y; }
  return { lat: lat / coords.length, lng: lng / coords.length };
}
function haversine(lat1, lng1, lat2, lng2) {
  const R = 6371;
  const toRad = (d) => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function updateQuizStats() {
  $('quiz-streak').textContent = quiz.streak;
  $('quiz-acc').textContent = quiz.total
    ? `${Math.round(quiz.correct / quiz.total * 100)}% (${quiz.correct}/${quiz.total})`
    : '—';
}

function endQuiz() {
  const acc = quiz.total ? Math.round(quiz.correct / quiz.total * 100) : 0;
  $('quiz-meta').textContent = 'Session over';
  $('quiz-img').removeAttribute('src');
  $('quiz-img').style.display = 'none';
  $('quiz-prompt').textContent = '';
  const fb = $('quiz-feedback');
  fb.hidden = false;
  fb.className = 'quiz-feedback';
  fb.innerHTML = `<strong>Session ended.</strong><br>${quiz.correct} right of ${quiz.total} (${acc}%) · best streak ${quiz.bestStreak}`;
  $('quiz-next').hidden = true;
  quiz.awaitingClick = false;
}

$('quiz-skip').addEventListener('click', () => {
  if (!quiz.awaitingClick) return;
  quiz.awaitingClick = false;
  finishQuizAnswer({ isRight: false, score: 0 });
});

// Click the inset mask to peek at what's underneath (manual override).
$('quiz-img-mask').addEventListener('click', () => {
  $('quiz-img-mask').classList.toggle('disabled');
});

// Hover-magnify lens — circular zoom follows cursor over the quiz image.
// Same pattern as the extension overlay's image thumbnails (overlay.js).
(() => {
  const wrap = document.querySelector('.qimg-wrap');
  const img = $('quiz-img');
  if (!wrap || !img) return;
  const LENS_SIZE = 180;
  const LENS_SCALE = 2.5;
  let lens = null;
  wrap.addEventListener('mouseenter', () => {
    if (lens || !img.src || !img.naturalWidth) return;
    lens = document.createElement('div');
    lens.className = 'qimg-lens';
    lens.style.backgroundImage = `url("${img.src.replace(/"/g, '\\"')}")`;
    wrap.appendChild(lens);
  });
  wrap.addEventListener('mousemove', (e) => {
    if (!lens) return;
    const imgRect = img.getBoundingClientRect();
    const x = e.clientX - imgRect.left;
    const y = e.clientY - imgRect.top;
    // Outside image bounds (letterbox) → hide lens
    if (x < 0 || y < 0 || x > imgRect.width || y > imgRect.height) {
      lens.style.display = 'none';
      return;
    }
    // Cursor over the inset-mask → also hide. Otherwise the lens would
    // magnify the IMAGE (which the mask hides in normal view), letting the
    // user peek the inset by hovering. Mask is only visible when
    // .show-mask is on the wrap and the mask isn't .disabled / .no-inset.
    const maskEl = $('quiz-img-mask');
    if (maskEl
        && wrap.classList.contains('show-mask')
        && !maskEl.classList.contains('disabled')
        && !maskEl.classList.contains('no-inset')) {
      const mr = maskEl.getBoundingClientRect();
      if (e.clientX >= mr.left && e.clientX <= mr.right
          && e.clientY >= mr.top  && e.clientY <= mr.bottom) {
        lens.style.display = 'none';
        return;
      }
    }
    lens.style.display = '';
    const w = imgRect.width, h = imgRect.height;
    const bgW = w * LENS_SCALE, bgH = h * LENS_SCALE;
    lens.style.backgroundSize = `${bgW}px ${bgH}px`;
    lens.style.backgroundPosition =
      `${-(x * LENS_SCALE - LENS_SIZE / 2)}px ${-(y * LENS_SCALE - LENS_SIZE / 2)}px`;
    const wrapRect = wrap.getBoundingClientRect();
    lens.style.left = (e.clientX - wrapRect.left - LENS_SIZE / 2) + 'px';
    lens.style.top  = (e.clientY - wrapRect.top  - LENS_SIZE / 2) + 'px';
  });
  wrap.addEventListener('mouseleave', () => {
    if (lens) { lens.remove(); lens = null; }
  });
  // ----- Touch support (iOS / Android) -----
  // Touch devices have no hover. Drag a finger over the image to show
  // the lens; lift to dismiss. We re-use the same lens DOM and the same
  // mask-region guard as the desktop hover handler.
  const touchEnter = (e) => {
    if (!img.naturalWidth) return;
    if (lens) lens.remove();
    lens = document.createElement('div');
    lens.className = 'qimg-lens';
    lens.style.backgroundImage = `url("${img.src.replace(/"/g, '\\"')}")`;
    wrap.appendChild(lens);
  };
  const touchMove = (e) => {
    if (!lens || !e.touches?.[0]) return;
    e.preventDefault();   // stop the page from scrolling under the finger
    const t = e.touches[0];
    const imgRect = img.getBoundingClientRect();
    const x = t.clientX - imgRect.left;
    const y = t.clientY - imgRect.top;
    if (x < 0 || y < 0 || x > imgRect.width || y > imgRect.height) {
      lens.style.display = 'none';
      return;
    }
    const maskEl = $('quiz-img-mask');
    if (maskEl
        && wrap.classList.contains('show-mask')
        && !maskEl.classList.contains('disabled')
        && !maskEl.classList.contains('no-inset')) {
      const mr = maskEl.getBoundingClientRect();
      if (t.clientX >= mr.left && t.clientX <= mr.right
          && t.clientY >= mr.top  && t.clientY <= mr.bottom) {
        lens.style.display = 'none';
        return;
      }
    }
    lens.style.display = '';
    const w = imgRect.width, h = imgRect.height;
    const bgW = w * LENS_SCALE, bgH = h * LENS_SCALE;
    lens.style.backgroundSize = `${bgW}px ${bgH}px`;
    lens.style.backgroundPosition =
      `${-(x * LENS_SCALE - LENS_SIZE / 2)}px ${-(y * LENS_SCALE - LENS_SIZE / 2)}px`;
    const wrapRect = wrap.getBoundingClientRect();
    lens.style.left = (t.clientX - wrapRect.left - LENS_SIZE / 2) + 'px';
    lens.style.top  = (t.clientY - wrapRect.top  - LENS_SIZE / 2) + 'px';
  };
  const touchEnd = () => {
    if (lens) { lens.remove(); lens = null; }
  };
  // passive:false on touchmove so e.preventDefault() actually blocks scroll.
  wrap.addEventListener('touchstart', touchEnter, { passive: true });
  wrap.addEventListener('touchmove', touchMove, { passive: false });
  wrap.addEventListener('touchend', touchEnd);
  wrap.addEventListener('touchcancel', touchEnd);
})();

$('quiz-blacklist').addEventListener('click', () => {
  if (!quiz.card?.cardKey) return;
  blacklistCard(quiz.card.cardKey);
  // Also drop from the live pool so it doesn't reappear this session
  quiz.pool = quiz.pool.filter(c => c.cardKey !== quiz.card.cardKey);
  quiz.reviewQueue = quiz.reviewQueue.filter(r => r.card.cardKey !== quiz.card.cardKey);
  // Treat as a skip and advance
  if (quiz.awaitingClick) {
    quiz.awaitingClick = false;
    quiz.streak = 0;
    quiz.total++;
    updateQuizStats();
  }
  $('quiz-img').style.display = '';
  presentNextCard();
  document.documentElement.scrollTop = 0;
});
$('quiz-next').addEventListener('click', () => {
  $('quiz-img').style.display = '';
  presentNextCard();
  // Scroll back to the top so the new card's image/text is in view.
  document.documentElement.scrollTop = 0;
});
$('quiz-quit').addEventListener('click', () => {
  showTab('home');
});

// ============================================================
// DASHBOARD — Supabase round history + heatmap
// ============================================================
const dash = { map: null, geoLayer: null, lastAgg: null };

function ensureDashMap() {
  if (dash.map) return;
  dash.map = L.map('dash-map', {
    minZoom: 2, maxZoom: 5, worldCopyJump: false,
    zoomControl: true, attributionControl: false,
    preferCanvas: true,
  }).setView([20, 0], 2);
  dash.geoLayer = L.geoJSON(state.geojson, {
    style: () => STYLE_DISABLED,
    onEachFeature: (feat, layer) => {
      const cc = feat.properties.ISO_A2_EH || feat.properties.ISO_A2;
      layer.bindTooltip(() => {
        const a = dash.lastAgg?.[cc];
        const name = state.tips[cc]?.name || feat.properties.NAME || cc;
        if (!a) return `${name} — untouched (click for fact-sheet)`;
        const parts = [`${name}: avg ${Math.round(a.avgScore)} pts (${a.count} total)`];
        if (a.ggCount) parts.push(`GG: ${a.ggCount}`);
        if (a.qCount) parts.push(`Quiz: ${a.qHit}/${a.qCount}`);
        parts.push('— click for fact-sheet');
        return parts.join(' · ');
      }, { sticky: true });
      layer.on('click', () => { if (cc && state.countries.has(cc)) openFactSheet(cc); });
    },
  }).addTo(dash.map);
}

function aggregateRounds(rounds, quizStats) {
  const agg = {};
  // GeoGuessr round data
  for (const r of rounds) {
    const cc = r.actual_country_iso2;
    if (!cc) continue;
    const a = agg[cc] || (agg[cc] = { ggCount: 0, ggTotal: 0, ggHit: 0, ggMiss: 0, qHit: 0, qMiss: 0, qScore: 0, qCount: 0 });
    a.ggCount++;
    if (typeof r.round_score === 'number') a.ggTotal += r.round_score;
    if (r.guess_country_iso2 === cc) a.ggHit++;
    else if (r.guess_country_iso2) a.ggMiss++;
  }
  // Localhost quiz stats
  for (const [cc, s] of Object.entries(quizStats || {})) {
    const a = agg[cc] || (agg[cc] = { ggCount: 0, ggTotal: 0, ggHit: 0, ggMiss: 0, qHit: 0, qMiss: 0, qScore: 0, qCount: 0 });
    a.qHit = s.hits || 0;
    a.qMiss = s.misses || 0;
    a.qCount = s.count || 0;
    a.qScore = s.totalScore || 0;
  }
  // Compute combined metrics. Quiz answers contribute as binary 0/5000 so
  // they blend with GG round scores cleanly.
  for (const [cc, a] of Object.entries(agg)) {
    a.count = a.ggCount + a.qCount;
    const totalScore = a.ggTotal + (a.qHit * 5000); // a quiz hit = 5000 pts
    a.avgScore = a.count ? totalScore / a.count : 0;
    const denom = a.ggHit + a.ggMiss + a.qHit + a.qMiss;
    a.hit = a.ggHit + a.qHit;
    a.miss = a.ggMiss + a.qMiss;
    a.acc = denom ? a.hit / denom : null;
  }
  return agg;
}

function heatKindForScore(s) {
  if (s == null) return 'disabled';
  if (s < 1500) return 'heat-0';
  if (s < 2500) return 'heat-1';
  if (s < 3500) return 'heat-2';
  if (s < 4500) return 'heat-3';
  return 'heat-4';
}

function paintDashMap(agg) {
  dash.lastAgg = agg;
  dash.geoLayer.eachLayer((layer) => {
    const cc = layer.feature.properties.ISO_A2_EH || layer.feature.properties.ISO_A2;
    const a = agg[cc];
    setLayerKind(layer, a ? heatKindForScore(a.avgScore) : 'disabled');
  });
}

function paintDashTables(rounds, agg) {
  const ranked = Object.entries(agg)
    .filter(([, v]) => v.count >= 2)
    .map(([cc, v]) => ({ cc, ...v }));
  const worst = ranked.slice().sort((a, b) => a.avgScore - b.avgScore).slice(0, 12);
  const best = ranked.slice().sort((a, b) => b.avgScore - a.avgScore).slice(0, 12);

  const renderRow = (r) => {
    const breakdown = [];
    if (r.ggCount) breakdown.push(`${r.ggCount}gg`);
    if (r.qCount) breakdown.push(`${r.qHit}/${r.qCount}q`);
    return `
    <tr data-cc="${r.cc}" style="cursor:pointer">
      <td class="flag">${flagEmoji(r.cc)}</td>
      <td class="cc">${r.cc}</td>
      <td>${escapeHtml(state.tips[r.cc]?.name || r.cc)}</td>
      <td class="acc">${Math.round(r.avgScore)} <span style="color:var(--muted);font-size:11px">(${breakdown.join(' · ')})</span></td>
    </tr>`;
  };

  $('tbl-worst').querySelector('tbody').innerHTML = worst.length
    ? worst.map(renderRow).join('')
    : '<tr class="empty"><td colspan="4">No data — play some rounds with Plonker installed.</td></tr>';
  $('tbl-best').querySelector('tbody').innerHTML = best.map(renderRow).join('') || '<tr class="empty"><td colspan="4">—</td></tr>';

  // Wire row clicks to open fact-sheet
  document.querySelectorAll('#tbl-worst tr[data-cc], #tbl-best tr[data-cc]').forEach(tr => {
    tr.addEventListener('click', () => openFactSheet(tr.dataset.cc));
  });

  const recent = rounds.slice(0, 12);
  $('tbl-recent').querySelector('tbody').innerHTML = recent.map(r => `
    <tr>
      <td class="flag">${flagEmoji(r.actual_country_iso2)}</td>
      <td class="cc">${r.actual_country_iso2 || '?'}</td>
      <td>${escapeHtml(r.movement_label || r.map_name || '?')}</td>
      <td class="acc">${r.round_score != null ? r.round_score : '—'}</td>
    </tr>`).join('') || '<tr class="empty"><td colspan="4">No rounds yet.</td></tr>';
}

async function refreshDashboard() {
  ensureDashMap();
  requestAnimationFrame(() => dash.map.invalidateSize());
  $('status').textContent = 'Loading…';
  const rounds = await loadRounds();
  state.rounds = rounds;
  const quizStats = loadQuizStats();
  const quizCount = Object.values(quizStats).reduce((a, s) => a + (s.count || 0), 0);
  $('dash-totals').textContent = `${rounds.length} GG rounds · ${quizCount} quiz answers`;
  const agg = aggregateRounds(rounds, quizStats);
  paintDashMap(agg);
  paintDashTables(rounds, agg);
  paintTopicTiles();
  $('status').textContent = '';
}

function paintTopicTiles() {
  const stats = loadTopicStats();
  const grid = $('dash-topics-grid');
  if (!grid || !state.topics) return;

  // Group topics by their group label so the dashboard mirrors the picker.
  const byGroup = {};
  for (const t of state.topics) (byGroup[t.group] = byGroup[t.group] || []).push(t);

  let totalCount = 0;
  let totalHits = 0;
  for (const s of Object.values(stats)) { totalCount += s.count; totalHits += s.hits; }
  $('dash-topics-totals').textContent = totalCount
    ? `${totalCount} answers · ${Math.round(totalHits / totalCount * 100)}% overall`
    : 'no quiz answers yet';

  const groupHtml = Object.entries(byGroup).map(([groupName, topics]) => {
    const tiles = topics.map(t => {
      const s = stats[t.id] || { hits: 0, misses: 0, count: 0 };
      const acc = s.count ? Math.round(s.hits / s.count * 100) : null;
      const accClass = acc == null ? 'untouched' : acc < 50 ? 'weak' : acc < 80 ? 'mid' : 'strong';
      return `
        <button class="topic-tile ${accClass}" data-topic-id="${t.id}" title="${escapeHtml(t.description || '')}">
          <div class="ttile-row">
            <span class="ttile-name">${escapeHtml(t.label)}</span>
            <span class="ttile-acc">${acc == null ? '—' : acc + '%'}</span>
          </div>
          <div class="ttile-row ttile-sub">
            <span>${s.count} answer${s.count === 1 ? '' : 's'}</span>
            <span>${s.hits}/${s.count || 0}</span>
          </div>
          ${acc != null ? `<div class="ttile-bar"><span style="width:${acc}%"></span></div>` : ''}
        </button>`;
    }).join('');
    return `<div class="topic-group">
      <div class="topic-group-label">${escapeHtml(groupName)}</div>
      <div class="topic-tile-row">${tiles}</div>
    </div>`;
  }).join('');

  grid.innerHTML = groupHtml;

  // Clicking a tile starts that topic's quiz immediately
  grid.querySelectorAll('.topic-tile').forEach(tile => {
    tile.addEventListener('click', () => {
      const topicId = tile.dataset.topicId;
      $('topic-select').value = topicId;
      const card = document.querySelector('.focus-card[data-focus-type="topic"]');
      selectFocusCard(card);
      showTab('home');
      // Auto-start
      $('start-btn').click();
    });
  });
}

$('dash-reload').addEventListener('click', refreshDashboard);

// ---------- Country fact-sheet & compare overlays ----------
function openFactSheet(cc) {
  const c = state.tips[cc];
  const facts = state.facts?.[cc];
  const ref = state.reference?.[cc];
  if (!c && !facts && !ref) return;
  $('fs-title').innerHTML = `${flagEmoji(cc)} ${escapeHtml(c?.name || cc)}`;
  const cardStats = loadCardStats();
  const body = $('fs-body');

  const factRows = [];
  const addFact = (label, value) => {
    if (value == null || value === '') return;
    factRows.push(`
      <div class="fs-fact">
        <div class="fs-fact-label">${escapeHtml(label)}</div>
        <div class="fs-fact-value">${escapeHtml(String(value))}</div>
      </div>`);
  };
  if (facts) {
    addFact('Driving side', facts.driving_side);
    addFact('Sign style', facts.sign_style);
    addFact('Stop sign text', facts.stop_text);
    addFact('Plate format', facts.plate_format);
    addFact('Speed limit max', facts.speed_limit_max_kmh ? `${facts.speed_limit_max_kmh} km/h` : null);
    addFact('Road lines', facts.road_lines);
    addFact('Chevron colour', facts.chevron_color);
    addFact('Ped sign stripes', facts.ped_stripes);
  }
  if (ref) {
    addFact('Calling code', ref.calling_code);
    addFact('TLD', ref.tld);
    addFact('Currency', `${ref.currency_code} (${ref.currency_symbol})`);
    addFact('Capital', ref.capital);
    addFact('Primary language', ref.primary_language);
    addFact('Scripts', (ref.scripts || []).join(', '));
    addFact('Official languages', (ref.official_languages || []).join(', '));
    addFact('ISO-3', ref.iso3);
  }

  const metas = c?.metas || [];
  const metaCards = metas.map((m, i) => {
    const cardKey = `${cc}:img:${i}`;   // matches imageGroupTopic key shape
    // Find any card stats for this country+metaType (heuristic — match by metaType)
    const matched = Object.values(cardStats).filter(s => s.cc === cc && s.metaType === m.type);
    const totalCount = matched.reduce((a, s) => a + s.count, 0);
    const totalHits = matched.reduce((a, s) => a + s.hits, 0);
    const acc = totalCount ? Math.round(totalHits / totalCount * 100) : null;
    const accClass = acc == null ? 'untouched' : acc < 50 ? 'weak' : acc < 80 ? 'mid' : 'strong';
    return `
      <div class="fs-meta-card">
        <span class="fs-meta-acc ${accClass}">${acc == null ? '—' : acc + '%'}</span>
        ${(m.images && m.images[0]) ? `<img src="${escapeHtml(m.images[0])}" alt="">` : ''}
        <div class="fs-meta-content">
          <div class="fs-meta-type">${escapeHtml(m.type || '')}</div>
          <div class="fs-meta-title">${escapeHtml(m.title || '')}</div>
          <div class="fs-meta-desc">${escapeHtml(m.description || '')}</div>
        </div>
      </div>`;
  }).join('');

  // Regions section
  let regionsHtml = '';
  const regions = c?.regions || {};
  if (Object.keys(regions).length) {
    const regionNames = Object.entries(regions)
      .filter(([, arr]) => arr.length)
      .sort((a, b) => b[1].length - a[1].length)
      .map(([n, arr]) => `<span class="fs-fact" style="display:inline-block;margin:2px 4px 2px 0;">${escapeHtml(n)} (${arr.length})</span>`)
      .join('');
    regionsHtml = `<div class="fs-section"><h3>Sub-regions</h3>${regionNames}</div>`;
  }

  body.innerHTML = `
    <div class="fs-section">
      <h3>Facts</h3>
      <div class="fs-facts">${factRows.join('')}</div>
    </div>
    ${regionsHtml}
    <div class="fs-section">
      <h3>Metas (${metas.length})</h3>
      <div class="fs-meta-list">${metaCards || '<div style="color:var(--muted)">No bundled metas.</div>'}</div>
    </div>
  `;

  // Wire compare button
  $('fs-compare-btn').onclick = () => openCompareSheet(cc);
  $('fs-quiz-btn').onclick = () => {
    $('country-select').value = cc;
    selectFocusCard(document.querySelector('.focus-card[data-focus-type="country"]'));
    closeFactSheet();
    showTab('home');
    $('start-btn').click();
  };
  $('factsheet').hidden = false;
  wireThumbnailLenses(body);
}
function closeFactSheet() { $('factsheet').hidden = true; }

function openCompareSheet(cc) {
  $('cs-title').innerHTML = `${flagEmoji(cc)} ${escapeHtml(state.tips[cc]?.name || cc)} vs ...`;
  // Populate the "other" select with countries from the same continent (more useful)
  const sameCont = Object.keys(REGION_GROUPS).find(k => REGION_GROUPS[k].includes(cc) && ['EU','AS','AF','NA','SA','OC'].includes(k));
  const candidates = (REGION_GROUPS[sameCont] || []).filter(other => other !== cc && state.countries.has(other));
  const sel = $('cs-other-select');
  sel.innerHTML = candidates.map(other =>
    `<option value="${other}">${flagEmoji(other)} ${escapeHtml(state.tips[other]?.name || other)}</option>`
  ).join('');
  const renderCompare = (other) => {
    const cols = [cc, other].map(code => {
      const c = state.tips[code];
      const facts = state.facts?.[code] || {};
      const ref = state.reference?.[code] || {};
      const factPairs = [
        ['Driving side', facts.driving_side],
        ['Stop sign', facts.stop_text],
        ['Sign style', facts.sign_style],
        ['Road lines', facts.road_lines],
        ['Plate', facts.plate_format],
        ['Speed (km/h)', facts.speed_limit_max_kmh],
        ['Calling code', ref.calling_code],
        ['TLD', ref.tld],
        ['Currency', ref.currency_code],
        ['Language', ref.primary_language],
        ['Scripts', (ref.scripts || []).join(', ')],
      ];
      const factsHtml = factPairs
        .filter(([, v]) => v != null && v !== '')
        .map(([k, v]) => `<div class="fs-fact"><div class="fs-fact-label">${escapeHtml(k)}</div><div class="fs-fact-value">${escapeHtml(String(v))}</div></div>`)
        .join('');
      const metaHtml = (c?.metas || []).slice(0, 6).map(m => `
        <div class="fs-meta-card">
          ${(m.images && m.images[0]) ? `<img src="${escapeHtml(m.images[0])}" alt="">` : ''}
          <div class="fs-meta-content">
            <div class="fs-meta-type">${escapeHtml(m.type || '')}</div>
            <div class="fs-meta-desc">${escapeHtml(m.description || '')}</div>
          </div>
        </div>
      `).join('');
      return `
        <div class="cs-col">
          <h3>${flagEmoji(code)} ${escapeHtml(c?.name || code)}</h3>
          <div class="fs-section"><h3>Facts</h3><div class="fs-facts">${factsHtml}</div></div>
          <div class="fs-section"><h3>Top metas</h3><div class="fs-meta-list">${metaHtml || '<div style="color:var(--muted)">No metas.</div>'}</div></div>
        </div>`;
    });
    $('cs-body').innerHTML = cols.join('');
    $('cs-title').innerHTML = `${flagEmoji(cc)} ${escapeHtml(state.tips[cc]?.name || cc)} vs ${flagEmoji(other)} ${escapeHtml(state.tips[other]?.name || other)}`;
  };
  if (candidates.length) renderCompare(candidates[0]);
  sel.onchange = () => renderCompare(sel.value);
  $('factsheet').hidden = true;  // close fact-sheet if open
  $('comparesheet').hidden = false;
}
function closeCompareSheet() { $('comparesheet').hidden = true; }

$('fs-close').addEventListener('click', closeFactSheet);
$('cs-close').addEventListener('click', closeCompareSheet);
$('factsheet').addEventListener('click', (e) => { if (e.target === $('factsheet')) closeFactSheet(); });
$('comparesheet').addEventListener('click', (e) => { if (e.target === $('comparesheet')) closeCompareSheet(); });

// ============================================================
// boot
// ============================================================
function populateRegionSelect() {
  const sel = $('region-select');
  sel.innerHTML = REGION_LABELS.map(grp => `
    <optgroup label="${escapeHtml(grp.group)}">
      ${grp.items.map(([key, label]) => `<option value="${key}">${escapeHtml(label)}</option>`).join('')}
    </optgroup>
  `).join('');
}

async function boot() {
  $('status').textContent = 'Loading data…';
  // Pull cloud progress + merge into localStorage BEFORE building topics so
  // the smart pools (Weak / Unseen) reflect the merged stats on first paint.
  // Don't block the UI on a slow Supabase round-trip beyond ~2s.
  await Promise.race([
    initProgressSync(),
    new Promise(r => setTimeout(r, 2000)),
  ]);
  await loadAll();
  state.topics = buildTopics();
  populateCountrySelect();
  populateRegionSelect();
  populateTopicSelect();
  // Default focus card is global; mark it
  const globalCard = document.querySelector('.focus-card[data-focus-type="global"]');
  globalCard.classList.add('selected');
  state.focus = { type: 'global', value: null };
  updateFocusMeta();

  document.querySelectorAll('.focus-card').forEach(card => {
    card.addEventListener('click', () => selectFocusCard(card));
  });
  ['continent-select','region-select','country-select','topic-select','personal-select'].forEach(id => {
    $(id).addEventListener('change', () => {
      const card = $(id).closest('.focus-card');
      selectFocusCard(card);
    });
    // Stop the change inside select from re-bubbling to parent click handler weirdly
    $(id).addEventListener('click', (e) => e.stopPropagation());
  });
  $('start-btn').addEventListener('click', startQuiz);

  // 🎲 Random focused quiz — pick a non-empty topic and jump straight in.
  $('random-quiz-btn')?.addEventListener('click', () => {
    // Pick from the topic-select options that have a non-zero pool count
    // (we encode the count in the option text as " (N)").
    const opts = Array.from(document.getElementById('topic-select').options)
      .map(o => ({ val: o.value, text: o.textContent.trim(), disabled: o.disabled }))
      .filter(o => !o.disabled);
    if (!opts.length) return;
    const pick = opts[Math.floor(Math.random() * opts.length)];
    // Switch focus to topic, set the topic, and start the quiz
    document.querySelector('[data-focus-type="topic"]')?.click();
    const ts = document.getElementById('topic-select');
    ts.value = pick.val;
    ts.dispatchEvent(new Event('change', { bubbles: true }));
    // Surface the picked topic name briefly in the status bar so the user
    // knows what was rolled.
    const status = document.getElementById('status');
    if (status) status.textContent = `🎲 ${pick.text}`;
    $('start-btn').click();
  });

  $('status').textContent = `${state.countries.size} countries loaded`;
}

boot();
