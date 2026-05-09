// Post-round overlay (v0.7). Consumes the merged learnablemeta + plonkit
// bundle. Tabs: Identify (LM atomic metas) / General (country-wide rules) /
// Regional (per-region tips, filtered by round location) / Spotlight (place-
// specific) / Images / Notes. Auto-dismisses on `plonker:round-start`.

const META_TAGS = ['bollard', 'language', 'plate', 'vegetation', 'other'];

// ---------- Quick Compare facts ----------
// Categorical country-level facts pulled from extension/data/country_facts.json
// (driving side, sign style, stop sign text, plate format, etc.). Renders a
// strip above the tabs that, in "your guess" mode, highlights only the fields
// that differ between actual and guess.
//
// Each field has an associated `slide` — clicking the value pops a lightbox
// of the source map from the "10 Useful Maps" deck, with a marker on the
// country if the slide is a calibrated Robinson world projection.
const FACT_FIELDS = [
  { key: 'driving_side', label: 'Drives on',
    fmt: (v) => v === 'left' ? 'left' : 'right',
    slide: 'slide1.png', proj: 'robinson_world' },
  { key: 'sign_style',   label: 'Sign style', fmt: (v) => v,
    slide: 'slide3.png', proj: 'robinson_world' },
  { key: 'stop_text',    label: 'Stop sign',  fmt: (v) => v,
    slide: 'slide4.png', proj: null },
  { key: 'plate_format', label: 'Plates', fmt: (v, f) => {
      const map = { 'front+rear': 'front + rear', 'rear_only': 'rear only', 'varies': 'varies' };
      const base = map[v] || v;
      return f?.plate_subdivision ? `${base} (${f.plate_subdivision})` : base;
    },
    // Slide depends on country: US→6, CA→7. Resolved in slideForFact().
    slide: 'plate', proj: null },
  { key: 'speed_limit_max_kmh', label: 'Top speed',
    fmt: (v) => v == null ? null : v >= 999 ? 'no limit' : `${v} kmh`,
    slide: 'slide10.png', proj: 'robinson_world' },
  { key: 'road_lines',   label: 'Road lines', fmt: (v) => ({
      'yellow_center_white_edge': 'yellow center / white edge',
      'yellow_or_white_center_white_edge': 'yellow or white center / white edge',
      'white_center_yellow_edge': 'white center / yellow edge',
      'white_center_white_edge': 'white center / white edge',
    }[v] || v),
    slide: 'slide9.png', proj: 'robinson_world' },
  { key: 'chevron_color', label: 'Curve chevron', fmt: (v) => ({
      yellow_black: 'yellow + black', red_white: 'red + white',
      blue_yellow: 'blue + yellow', black_white: 'black + white',
    }[v] || v),
    slide: 'slide5.png', proj: null },
  { key: 'ped_stripes', label: 'Ped sign stripes',
    fmt: (v) => v == null ? null : `${v}`,
    slide: 'slide8.png', proj: null },
];

// Slide bboxes (left, top, right, bottom) in 960x540 native image coords —
// matches scraper/sample_slide_facts.py's SLIDE_MAPS for the world maps.
const SLIDE_BBOX = {
  'slide1.png':  [-10, 30, 920, 470],
  'slide3.png':  [-10, 50, 920, 460],
  'slide9.png':  [-10, 50, 920, 460],
  'slide10.png': [-10, 30, 920, 470],
};
const SLIDE_W = 960, SLIDE_H = 540;

// Robinson projection lookup at 5° latitude steps (Snyder 1987).
const ROBINSON_TABLE = [
  [0,1.0000,0.0000],[5,0.9986,0.0620],[10,0.9954,0.1240],[15,0.9900,0.1860],
  [20,0.9822,0.2480],[25,0.9730,0.3100],[30,0.9600,0.3720],[35,0.9427,0.4340],
  [40,0.9216,0.4958],[45,0.8962,0.5571],[50,0.8679,0.6176],[55,0.8350,0.6769],
  [60,0.7986,0.7346],[65,0.7597,0.7903],[70,0.7186,0.8435],[75,0.6732,0.8936],
  [80,0.6213,0.9394],[85,0.5722,0.9761],[90,0.5322,1.0000],
];

const robinsonForward = (lat, lng) => {
  const sign = lat < 0 ? -1 : 1;
  const a = Math.abs(lat);
  let X = ROBINSON_TABLE[ROBINSON_TABLE.length - 1][1];
  let Y = ROBINSON_TABLE[ROBINSON_TABLE.length - 1][2];
  for (let i = 0; i < ROBINSON_TABLE.length - 1; i++) {
    const [l0, X0, Y0] = ROBINSON_TABLE[i];
    const [l1, X1, Y1] = ROBINSON_TABLE[i + 1];
    if (a >= l0 && a <= l1) {
      const t = l0 === l1 ? 0 : (a - l0) / (l1 - l0);
      X = X0 + t * (X1 - X0);
      Y = Y0 + t * (Y1 - Y0);
      break;
    }
  }
  const x = 0.8487 * (Math.PI / 180) * lng * X;
  const y = 1.3523 * Y * sign;
  return [x, y];
};

// Project (lat, lng) to a percentage position within the slide image (0–100).
// Returns null if the slide has no calibrated projection.
const projectMarker = (slideFile, lat, lng) => {
  if (lat == null || lng == null) return null;
  const bbox = SLIDE_BBOX[slideFile];
  if (!bbox) return null;
  const [x0, y0, x1, y1] = bbox;
  const [u, v] = robinsonForward(lat, lng);
  const px = x0 + (u / 2.667 + 1) / 2 * (x1 - x0);
  const py = y1 - (v / 1.3523 + 1) / 2 * (y1 - y0);
  return {
    leftPct: 100 * px / SLIDE_W,
    topPct: 100 * py / SLIDE_H,
  };
};

// plate_format slide depends on country (US→6, CA→7, otherwise none).
const slideForFact = (field, cc2) => {
  if (field.key === 'plate_format') {
    if (cc2 === 'US') return 'slide6.png';
    if (cc2 === 'CA') return 'slide7.png';
    return null;
  }
  return field.slide;
};

const factVal = (facts, field) => {
  if (!facts) return null;
  const raw = facts[field.key];
  if (raw == null || raw === '') return null;
  const out = field.fmt(raw, facts);
  return out == null || out === '' ? null : out;
};

// Renders one fact value as a clickable button if a slide is available, or
// a plain span otherwise. Clicking pops the source map in the lightbox with
// a marker on the country (when the slide has a calibrated projection).
const factValueHtml = (text, field, cc2, lat, lng, side) => {
  const slide = slideForFact(field, cc2);
  if (!slide) {
    return `<span class="plonker-fact-value plonker-fact-${side}">${escape(text)}</span>`;
  }
  const cls = side ? `plonker-fact-${side}` : 'plonker-fact-value';
  return `<button type="button" class="plonker-fact-value plonker-fact-clickable ${cls}"
    data-slide="${escape(slide)}"
    data-caption="${escape(field.label + ': ' + text)}"
    data-lat="${lat ?? ''}" data-lng="${lng ?? ''}"
  >${escape(text)}</button>`;
};

const renderFactsStrip = (actualFacts, guessFacts, mode, round, server) => {
  if (!actualFacts) return '';
  const inGuess = mode === 'guess' && guessFacts;
  const facts = inGuess ? guessFacts : actualFacts;
  const actualCc = (round?.actual?.countryCode || '').toUpperCase();
  const guessCc = (server?.guessCountryCode || round?.guess?.countryCode || '').toUpperCase();
  const aLat = round?.actual?.lat, aLng = round?.actual?.lng;
  const gLat = round?.guess?.lat, gLng = round?.guess?.lng;
  // In guess-mode, filter to fields that differ from actual.
  const fields = FACT_FIELDS.filter(f => {
    const a = factVal(actualFacts, f);
    const g = factVal(guessFacts, f);
    if (inGuess) return a != null && g != null && a !== g;
    return factVal(facts, f) != null;
  });
  if (!fields.length) return '';
  const heading = inGuess
    ? `<div class="plonker-facts-head">Diff vs your guess</div>`
    : `<div class="plonker-facts-head">Quick facts <span class="plonker-facts-hint">— click a value to see the map</span></div>`;
  return `
    <div class="plonker-facts">
      ${heading}
      <div class="plonker-facts-row">
        ${fields.map(f => {
          const a = factVal(actualFacts, f);
          const g = factVal(guessFacts, f);
          if (inGuess) {
            return `
              <div class="plonker-fact plonker-fact-diff">
                <span class="plonker-fact-label">${escape(f.label)}</span>
                <span class="plonker-fact-pair">
                  ${factValueHtml(a, f, actualCc, aLat, aLng, 'actual')}
                  <span class="plonker-fact-arrow">vs</span>
                  ${factValueHtml(g, f, guessCc, gLat, gLng, 'guess')}
                </span>
              </div>`;
          }
          const cc2 = mode === 'guess' ? guessCc : actualCc;
          const lat = mode === 'guess' ? gLat : aLat;
          const lng = mode === 'guess' ? gLng : aLng;
          return `
            <div class="plonker-fact">
              <span class="plonker-fact-label">${escape(f.label)}</span>
              ${factValueHtml(factVal(facts, f), f, cc2, lat, lng, null)}
            </div>`;
        }).join('')}
      </div>
    </div>`;
};

const flagEmoji = (cc2) => {
  if (!cc2 || cc2.length !== 2) return '';
  const A = 0x1F1E6;
  return String.fromCodePoint(...[...cc2.toUpperCase()].map(c => A + c.charCodeAt(0) - 65));
};
const escape = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// Bundled images live under assets/img/ inside the extension. tips.json
// stores them as paths like 'assets/img/plonkit/ireland/foo.png'. Anything
// that already starts with http(s) is left as-is (legacy fallback).
const resolveImg = (path) => {
  if (!path) return path;
  if (/^https?:\/\//.test(path)) return path;
  try { return chrome.runtime.getURL(path); }
  catch (e) { return path; }
};

const ensureContainer = () => {
  let el = document.getElementById('plonker-overlay-root');
  if (el) el.remove();
  el = document.createElement('div');
  el.id = 'plonker-overlay-root';
  document.body.appendChild(el);
  return el;
};
const settings = async () => {
  const got = await chrome.storage.local.get(['noSpoilers', 'overlayGeom']);
  return {
    noSpoilers: !!got.noSpoilers,
    geom: got.overlayGeom || null,
  };
};

const saveGeom = (geom) => {
  chrome.storage.local.set({ overlayGeom: geom }).catch(() => {});
};

const DEFAULT_GEOM = { left: 16, top: 16, width: 480, height: null };
const MIN_W = 320;
const MIN_H = 200;
const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
// Cache of the last rendered round so we can re-open the overlay after the
// user dismisses it (e.g., to revisit metas while panning around in the
// post-round street view).
let lastRoundDetail = null;

const dismiss = () => {
  const el = document.getElementById('plonker-overlay-root');
  if (el) el.remove();
  closeLightbox();
  if (lastRoundDetail) showReopenChip();
};

const removeReopenChip = () => {
  const c = document.getElementById('plonker-reopen-chip');
  if (c) c.remove();
};

const showReopenChip = () => {
  removeReopenChip();
  const cc2 = (lastRoundDetail?.round?.actual?.countryCode || '').toUpperCase();
  const flag = flagEmoji(cc2);
  const chip = document.createElement('button');
  chip.id = 'plonker-reopen-chip';
  chip.title = 'Show last round metas';
  chip.innerHTML = `<span class="plonker-reopen-flag">${flag || '\u{1F30D}'}</span><span class="plonker-reopen-label">Metas</span>`;
  chip.addEventListener('click', () => {
    if (!lastRoundDetail) return;
    removeReopenChip();
    render(lastRoundDetail).catch(err => console.error('[plonker overlay]', err));
  });
  document.body.appendChild(chip);
};

const fullDismiss = () => {
  // Used by round-start: drop the cache too so a stale chip doesn't sit
  // around when a new round begins.
  lastRoundDetail = null;
  removeReopenChip();
  dismiss();
};

// ---------- lightbox ----------
const closeLightbox = () => {
  const lb = document.getElementById('plonker-lightbox');
  if (lb) lb.remove();
  document.removeEventListener('keydown', onLightboxKey);
};
const onLightboxKey = (e) => { if (e.key === 'Escape') closeLightbox(); };
const openLightbox = (src, caption) => {
  closeLightbox();
  const lb = document.createElement('div');
  lb.id = 'plonker-lightbox';
  lb.innerHTML = `
    <div class="plonker-lb-bg"></div>
    <figure class="plonker-lb-fig">
      <img src="${escape(src)}" alt="">
      ${caption ? `<figcaption>${escape(caption)}</figcaption>` : ''}
      <button class="plonker-lb-close" aria-label="Close">\u00d7</button>
    </figure>`;
  document.body.appendChild(lb);
  lb.querySelector('.plonker-lb-bg').addEventListener('click', closeLightbox);
  lb.querySelector('.plonker-lb-close').addEventListener('click', closeLightbox);
  document.addEventListener('keydown', onLightboxKey);
};

// Map-aware lightbox for the fact-strip slide images. If the slide has a
// calibrated Robinson world bbox, an animated marker is overlaid at the
// country's projected pixel position.
const openMapLightbox = (slideFile, caption, lat, lng) => {
  closeLightbox();
  const url = chrome.runtime.getURL(`assets/img/maps/${slideFile}`);
  const marker = projectMarker(slideFile, lat, lng);
  const lb = document.createElement('div');
  lb.id = 'plonker-lightbox';
  const markerHtml = marker
    ? `<span class="plonker-map-marker" style="left:${marker.leftPct}%;top:${marker.topPct}%"></span>`
    : '';
  lb.innerHTML = `
    <div class="plonker-lb-bg"></div>
    <figure class="plonker-lb-fig plonker-lb-map">
      <div class="plonker-map-frame">
        <img src="${escape(url)}" alt="">
        ${markerHtml}
      </div>
      ${caption ? `<figcaption>${escape(caption)}</figcaption>` : ''}
      <button class="plonker-lb-close" aria-label="Close">\u00d7</button>
    </figure>`;
  document.body.appendChild(lb);
  lb.querySelector('.plonker-lb-bg').addEventListener('click', closeLightbox);
  lb.querySelector('.plonker-lb-close').addEventListener('click', closeLightbox);
  document.addEventListener('keydown', onLightboxKey);
};

// ---------- region matching ----------
const norm = (s) => String(s).toLowerCase().normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]/g, '');

const NAME_ALIASES = {
  upperaustria: ['oberosterreich'], loweraustria: ['niederosterreich'],
  styria: ['steiermark'], carinthia: ['karnten'], tyrol: ['tirol'], vienna: ['wien'],
  bavaria: ['bayern'], saxony: ['sachsen'], thuringia: ['thuringen'],
  newsouthwales: ['nsw'], queensland: ['qld'], victoria: ['vic'],
  westernaustralia: ['wa'], southaustralia: ['sa'], tasmania: ['tas'],
  northernterritory: ['nt'], australiancapitalterritory: ['act'],
  britishcolumbia: ['bc'], ontario: ['on'], quebec: ['qc'], alberta: ['ab'],
  bavaria_de: ['bayern'], lowersaxony: ['niedersachsen'],
  northrhinewestphalia: ['nordrheinwestfalen', 'nrw'],
  rhinelandpalatinate: ['rheinlandpfalz'],
};
const expand = (n) => {
  const out = new Set([n]);
  if (NAME_ALIASES[n]) NAME_ALIASES[n].forEach(a => out.add(a));
  for (const [k, vs] of Object.entries(NAME_ALIASES)) {
    if (vs.includes(n)) out.add(k);
  }
  return out;
};
const placesMatch = (regionName, roundPlaces) => {
  if (!roundPlaces?.length) return false;
  const rn = norm(regionName);
  const rnSet = expand(rn);
  for (const rp of roundPlaces) {
    const np = norm(rp);
    if (np.length < 3) continue;
    for (const v of rnSet) {
      if (v.length < 3) continue;
      if (np.includes(v) || v.includes(np)) return true;
    }
  }
  return false;
};

// ---------- card renderers ----------
const imageThumb = (src, caption) => {
  const url = resolveImg(src);
  return `
  <button class="plonker-img-inline" data-src="${escape(url)}" data-caption="${escape(caption || '')}">
    <img src="${escape(url)}" loading="lazy" alt="">
  </button>`;
};

const renderMetaCard = (meta) => `
  <div class="plonker-card">
    <div class="plonker-card-head">
      <span class="plonker-card-type">${escape(meta.type || 'Meta')}</span>
    </div>
    ${meta.images?.length ? imageThumb(meta.images[0], meta.title) : ''}
    <p class="plonker-card-desc">${escape(meta.description)}</p>
    ${meta.comparison ? `<p class="plonker-card-compare"><strong>vs:</strong> ${escape(meta.comparison)}</p>` : ''}
  </div>`;

const renderRuleCard = (rule) => `
  <div class="plonker-card">
    <div class="plonker-card-head">
      <span class="plonker-card-type">${escape(rule.topic || 'Rule')}</span>
    </div>
    ${(rule.images || []).slice(0, 1).map(src => imageThumb(src, rule.topic)).join('')}
    <p class="plonker-card-desc">${escape(rule.text)}</p>
  </div>`;

const renderRegionGroup = (regionName, items) => `
  <div class="plonker-region-group">
    <h4 class="plonker-region-head">${escape(regionName)}</h4>
    ${items.map(it => `
      <div class="plonker-card">
        ${(it.images || []).slice(0, 1).map(src => imageThumb(src, regionName)).join('')}
        <p class="plonker-card-desc">${escape(it.text)}</p>
      </div>
    `).join('')}
  </div>`;

const renderSpotlight = (items) => items.map(it => `
  <div class="plonker-card">
    <div class="plonker-card-head">
      <span class="plonker-card-type">${escape(it.place)}</span>
    </div>
    ${(it.images || []).slice(0, 1).map(src => imageThumb(src, it.place)).join('')}
    <p class="plonker-card-desc">${escape(it.text)}</p>
  </div>`).join('');

// Hover-magnify (lens) handler. Pattern lifted from learnablemeta's geometa
// userscript: https://github.com/likeon/geometa — a circular lens follows
// the cursor and shows the SAME image scaled 2x with background-position
// math, so the patch under the cursor appears centered and magnified.
const LENS_SIZE = 160;
const LENS_SCALE = 2.4;

const wireImageHandlers = (overlay) => {
  overlay.querySelectorAll('.plonker-img-inline, .plonker-img-tile').forEach(btn => {
    if (btn.dataset.lensWired === '1') return;
    btn.dataset.lensWired = '1';
    const src = btn.dataset.src;
    if (!src) return;
    const img = btn.querySelector('img');
    if (!img) return;
    let lens = null;
    const onEnter = () => {
      if (lens || !img.naturalWidth) return;
      lens = document.createElement('div');
      lens.className = 'plonker-img-lens';
      lens.style.width = LENS_SIZE + 'px';
      lens.style.height = LENS_SIZE + 'px';
      lens.style.backgroundImage = `url("${src.replace(/"/g, '\\"')}")`;
      btn.appendChild(lens);
    };
    const onMove = (e) => {
      if (!lens) return;
      const rect = btn.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      // Image inside the button is contained, but typically fills the button
      // box for our thumbs. Scale background to the rendered image size, not
      // the natural size, so the visible magnification matches the displayed
      // pixels the user is hovering over.
      const w = rect.width, h = rect.height;
      const bgW = w * LENS_SCALE, bgH = h * LENS_SCALE;
      lens.style.backgroundSize = `${bgW}px ${bgH}px`;
      lens.style.backgroundPosition =
        `${-(x * LENS_SCALE - LENS_SIZE / 2)}px ${-(y * LENS_SCALE - LENS_SIZE / 2)}px`;
      lens.style.left = (x - LENS_SIZE / 2) + 'px';
      lens.style.top = (y - LENS_SIZE / 2) + 'px';
    };
    const onLeave = () => {
      if (lens) { lens.remove(); lens = null; }
    };
    btn.addEventListener('mouseenter', onEnter);
    btn.addEventListener('mousemove', onMove);
    btn.addEventListener('mouseleave', onLeave);
    // Type changed from <button>: don't accidentally submit forms/etc.
    btn.addEventListener('click', (e) => e.preventDefault());
  });
};

// ---------- tabs ----------
const buildTabs = (tips, ctx) => {
  const tabs = [];
  const t = tips || {};

  if (t.metas?.length) {
    tabs.push({ id: 'identify', label: 'Identify', kind: 'metas', items: t.metas });
  }
  if (t.general_rules?.length) {
    tabs.push({ id: 'general', label: 'General', kind: 'rules', items: t.general_rules });
  }

  // Regional: filter regions to those matching the round's geocoded places.
  const allRegions = t.regions || {};
  const regionEntries = Object.entries(allRegions);
  const matchedRegions = ctx.roundPlaces?.length
    ? regionEntries.filter(([name]) => placesMatch(name, ctx.roundPlaces))
    : [];
  if (regionEntries.length) {
    tabs.push({
      id: 'regional', label: 'Regional', kind: 'regions',
      allRegions, matchedRegions,
    });
  }

  // Spotlight: filter to places matching round.
  const spotlight = t.spotlight || [];
  const matchedSpot = ctx.roundPlaces?.length
    ? spotlight.filter(it => placesMatch(it.place, ctx.roundPlaces))
    : [];
  if (spotlight.length) {
    tabs.push({
      id: 'spotlight', label: 'Spotlight', kind: 'spotlight',
      all: spotlight, matched: matchedSpot,
    });
  }

  // Images: aggregate from everywhere.
  const allImages = [];
  for (const m of (t.metas || [])) (m.images || []).forEach(s => allImages.push({ src: s, caption: m.title }));
  for (const g of (t.general_rules || [])) (g.images || []).forEach(s => allImages.push({ src: s, caption: g.topic }));
  for (const [name, items] of Object.entries(allRegions)) {
    items.forEach(it => (it.images || []).forEach(s => allImages.push({ src: s, caption: name })));
  }
  for (const sp of spotlight) (sp.images || []).forEach(s => allImages.push({ src: s, caption: sp.place }));
  if (allImages.length) {
    tabs.push({ id: 'images', label: `Images (${allImages.length})`, kind: 'images', items: allImages });
  }

  tabs.push({ id: 'notes', label: 'Notes', kind: 'notes' });
  return tabs;
};

const renderTabContent = (tab, ctx) => {
  if (tab.kind === 'metas') {
    return `<div class="plonker-cards">${tab.items.map(renderMetaCard).join('')}</div>`;
  }
  if (tab.kind === 'rules') {
    return `<div class="plonker-cards">${tab.items.map(renderRuleCard).join('')}</div>`;
  }
  if (tab.kind === 'regions') {
    const useFiltered = !ctx.showAll && ctx.roundPlaces?.length;
    const entries = useFiltered ? tab.matchedRegions : Object.entries(tab.allRegions);
    if (entries.length === 0) {
      return `<div class="plonker-empty">
        No region-specific tips matched <strong>${escape(ctx.roundPlaces?.slice(0, 2).join(', ') || 'this location')}</strong>.
        <button class="plonker-show-all">Show all regions</button>
      </div>`;
    }
    const totalRegions = Object.keys(tab.allRegions).length;
    const filteredOut = totalRegions - entries.length;
    const chip = (useFiltered && filteredOut > 0)
      ? `<div class="plonker-filter-chip">
           <span>Showing <strong>${entries.length}</strong> of ${totalRegions} regions matched to ${escape(ctx.roundPlaces.slice(0, 3).join(', '))}.</span>
           <button class="plonker-show-all">Show all</button>
         </div>` : '';
    return chip + entries.map(([name, items]) => renderRegionGroup(name, items)).join('');
  }
  if (tab.kind === 'spotlight') {
    const useFiltered = !ctx.showAll && ctx.roundPlaces?.length;
    const items = useFiltered ? tab.matched : tab.all;
    if (items.length === 0) {
      return `<div class="plonker-empty">
        No spotlight tips for <strong>${escape(ctx.roundPlaces?.slice(0, 2).join(', ') || 'this location')}</strong>.
        <button class="plonker-show-all">Show all</button>
      </div>`;
    }
    const filteredOut = tab.all.length - items.length;
    const chip = (useFiltered && filteredOut > 0)
      ? `<div class="plonker-filter-chip">
           <span>Showing <strong>${items.length}</strong> of ${tab.all.length}, filtered to ${escape(ctx.roundPlaces.slice(0, 3).join(', '))}.</span>
           <button class="plonker-show-all">Show all</button>
         </div>` : '';
    return chip + `<div class="plonker-cards">${renderSpotlight(items)}</div>`;
  }
  if (tab.kind === 'images') {
    return `<div class="plonker-img-grid">${tab.items.map(img => {
      const url = resolveImg(img.src);
      return `
      <button class="plonker-img-tile" data-src="${escape(url)}" data-caption="${escape(img.caption || '')}">
        <img src="${escape(url)}" loading="lazy" alt="">
      </button>`;
    }).join('')}</div>`;
  }
  if (tab.kind === 'notes') {
    return `
      <div class="plonker-note">
        <div class="plonker-tags">
          ${META_TAGS.map(t => `<button class="plonker-tag" data-tag="${t}">${t}</button>`).join('')}
        </div>
        <textarea placeholder="What did you miss? (e.g., red/white striped bollard)"></textarea>
        <button class="plonker-save" disabled>Save note</button>
        <div class="plonker-meta" data-status></div>
      </div>`;
  }
  return '';
};

const wireNotesTab = (overlay, ctx) => {
  const ta = overlay.querySelector('textarea');
  const save = overlay.querySelector('.plonker-save');
  const status = overlay.querySelector('[data-status]');
  if (!ta || !save) return;
  let chosenTag = null;
  const checkEnable = () => { save.disabled = !chosenTag && !ta.value.trim(); };
  overlay.querySelectorAll('.plonker-tag').forEach(b => {
    b.addEventListener('click', () => {
      overlay.querySelectorAll('.plonker-tag').forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      chosenTag = b.dataset.tag;
      checkEnable();
    });
  });
  ta.addEventListener('input', checkEnable);
  save.addEventListener('click', () => {
    save.disabled = true;
    status.textContent = 'saving\u2026';
    chrome.runtime.sendMessage({
      type: 'save_note',
      payload: { round_id: ctx.roundId, meta_tag: chosenTag, comment: ta.value.trim() || null }
    }, (resp) => {
      status.textContent = resp?.ok ? 'saved \u2713' : `error: ${resp?.error || 'unknown'}`;
      if (resp?.ok) setTimeout(dismiss, 700);
      else save.disabled = false;
    });
  });
};

const render = async ({ round, server }) => {
  const container = ensureContainer();
  const actualCc = round.actual?.countryCode?.toUpperCase() ?? '??';
  // Server fills guessCountryCode either from GG (rare in classic mode) or
  // from a Nominatim reverse-geocode of the guess coords (common).
  const guessCc = (server?.guessCountryCode || round.guess?.countryCode || '').toUpperCase() || null;
  const isLM = server?.isLearnableMetaMap;
  const { noSpoilers, geom: storedGeom } = await settings();
  // Position + size persist across rounds. Falls back to default if storage
  // is empty or stored geometry would put the overlay off-screen (e.g., user
  // resized their window since last play).
  const geom = { ...DEFAULT_GEOM, ...(storedGeom || {}) };

  // View modes: actual (default) and guess (your guessed country, if it
  // differs and we have data for it).
  const haveGuessTips = !!server?.guessTips && guessCc && guessCc !== actualCc;
  const view = {
    mode: 'actual',
  };

  const viewData = () => view.mode === 'guess'
    ? {
        cc2: guessCc,
        tips: server.guessTips,
        places: server.guessPlaces || [],
      }
    : {
        cc2: actualCc,
        tips: server?.tips,
        places: server?.places || [],
      };

  // Stateful view bindings — these are MUTATED by the mode switch (Actual/
  // Your Guess), so all the render helpers below close over them and re-read
  // their current values each call.
  const veilCls = noSpoilers ? 'plonker-spoiler-veil' : '';
  let { cc2, tips, places } = viewData();
  let country = tips?.name || cc2;
  const ctx = {
    roundId: server?.row?.id,
    roundPlaces: places,
    showAll: false,
  };
  let tabs = buildTabs(tips, ctx);
  // If the user nailed the country, the Identify tab is wasted real-estate
  // — they already know what country it is. Drop them on Regional/Spotlight
  // instead so they can refine to within-country accuracy. Fall back to
  // Identify if no region content is available for this country.
  const gotCountryRight = !!guessCc && guessCc === actualCc;
  const preferredTabs = gotCountryRight
    ? ['regional', 'spotlight', 'identify']
    : ['identify'];
  let activeId =
    (preferredTabs.map(id => tabs.find(t => t.id === id)).find(Boolean)
     || tabs[0])?.id || 'notes';

  const headerHtml = () => `
      <h3>
        <span><span class="plonker-flag ${veilCls}" data-reveal>${escape(flagEmoji(cc2))}</span><span class="${veilCls}" data-reveal>${escape(country)}</span></span>
        <span class="plonker-h3-actions">
          ${round.guess?.roundScore != null ? `<span class="plonker-score">${escape(round.guess.roundScore)} pts</span>` : ''}
          <button class="plonker-close" title="Close">\u00d7</button>
        </span>
      </h3>`;

  const modeSwitchHtml = () => {
    if (!haveGuessTips) return '';
    const guessName = server.guessTips?.name || guessCc;
    return `
      <div class="plonker-mode-switch" role="tablist">
        <button class="plonker-mode-btn ${view.mode === 'actual' ? 'active' : ''}" data-mode="actual">
          \u2714 ${escape(tips?.name || actualCc)}
        </button>
        <button class="plonker-mode-btn ${view.mode === 'guess' ? 'active' : ''}" data-mode="guess">
          Your guess: ${escape(guessName)}
        </button>
      </div>`;
  };

  const linksHtml = () => {
    const slug = tips?.plonkit_slug || (country.toLowerCase().replace(/\s+/g, '-'));
    const lat = round.actual?.lat;
    const lng = round.actual?.lng;
    const streetViewLink = (view.mode === 'actual' && lat != null && lng != null)
      ? `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}&heading=${round.actual?.heading ?? 0}&pitch=${round.actual?.pitch ?? 0}`
      : null;
    return `
      <div class="plonker-links">
        ${slug ? `<a href="https://www.plonkit.net/${escape(slug)}" target="_blank" rel="noopener">plonkit</a>` : ''}
        ${streetViewLink ? `<a href="${escape(streetViewLink)}" target="_blank" rel="noopener">street view</a>` : ''}
        <a href="https://learnablemeta.com/maps" target="_blank" rel="noopener">learn meta</a>
      </div>`;
  };

  const keyMetaHtml = () => tips?.key_meta
    ? `<div class="plonker-keymeta"><strong>Key:</strong> ${escape(tips.key_meta)}</div>` : '';

  const tabsHtml = () => `
    <div class="plonker-tab-strip" role="tablist">
      ${tabs.map(t => `
        <button class="plonker-tab ${t.id === activeId ? 'active' : ''}"
                data-tab="${escape(t.id)}" role="tab" aria-selected="${t.id === activeId}">
          ${escape(t.label)}
        </button>`).join('')}
    </div>`;

  const factsStripHtml = () => renderFactsStrip(
    server?.actualFacts, server?.guessFacts, view.mode, round, server
  );

  const fullRender = () => {
    container.innerHTML = `
    <div class="plonker-overlay" role="dialog" aria-label="Plonker round summary">
      ${headerHtml()}
      ${isLM ? '<div class="plonker-meta">Learnable-meta map \u2014 deliberate drill</div>' : ''}
      ${modeSwitchHtml()}
      ${factsStripHtml()}
      ${keyMetaHtml()}
      ${linksHtml()}
      ${tabsHtml()}
      <div class="plonker-tab-content" data-tab-content></div>
      <div class="plonker-resize-handle plonker-resize-n"  data-dir="n"  title="Drag to resize"></div>
      <div class="plonker-resize-handle plonker-resize-s"  data-dir="s"  title="Drag to resize"></div>
      <div class="plonker-resize-handle plonker-resize-e"  data-dir="e"  title="Drag to resize"></div>
      <div class="plonker-resize-handle plonker-resize-w"  data-dir="w"  title="Drag to resize"></div>
      <div class="plonker-resize-handle plonker-resize-nw" data-dir="nw" title="Drag to resize"></div>
      <div class="plonker-resize-handle plonker-resize-ne" data-dir="ne" title="Drag to resize"></div>
      <div class="plonker-resize-handle plonker-resize-sw" data-dir="sw" title="Drag to resize"></div>
      <div class="plonker-resize-handle plonker-resize-se" data-dir="se" title="Drag to resize"><span class="plonker-resize-grip"></span></div>
    </div>
  `;
    applyGeom();
  };

  const applyGeom = () => {
    const el = container.querySelector('.plonker-overlay');
    if (!el) return;
    // Clamp to viewport so a resize doesn't push the overlay off-screen.
    const maxLeft = Math.max(0, window.innerWidth - MIN_W);
    const maxTop = Math.max(0, window.innerHeight - 80);
    el.style.left = clamp(geom.left, 0, maxLeft) + 'px';
    el.style.top = clamp(geom.top, 0, maxTop) + 'px';
    el.style.width = Math.max(MIN_W, geom.width || DEFAULT_GEOM.width) + 'px';
    if (geom.height != null) {
      el.style.height = Math.max(MIN_H, geom.height) + 'px';
      el.style.maxHeight = 'none';
    }
  };

  fullRender();

  let overlay = container.querySelector('.plonker-overlay');
  let contentEl = overlay.querySelector('[data-tab-content]');

  const setTab = (id) => {
    const tab = tabs.find(t => t.id === id) || tabs[0];
    activeId = tab.id;
    overlay.querySelectorAll('.plonker-tab').forEach(b => {
      const on = b.dataset.tab === tab.id;
      b.classList.toggle('active', on);
      b.setAttribute('aria-selected', on);
    });
    try {
      contentEl.innerHTML = renderTabContent(tab, ctx);
      if (tab.kind === 'notes') wireNotesTab(overlay, ctx);
      else wireImageHandlers(overlay);
      overlay.querySelectorAll('.plonker-show-all').forEach(btn => {
        btn.addEventListener('click', () => { ctx.showAll = true; setTab(tab.id); });
      });
    } catch (e) {
      console.error('[plonker overlay] tab render failed', tab.id, e);
      contentEl.innerHTML = `<div class="plonker-empty">Couldn't render this tab. ${escape(e.message || '')}</div>`;
    }
  };

  const wireDragResize = () => {
    // Use pointer events + setPointerCapture so drags survive even when the
    // cursor crosses host-page UI that captures mouse events (Google Maps,
    // GeoGuessr's own panes, etc.). Critical pairing with `touch-action:
    // none` in CSS — without that, the browser may swallow vertical drags
    // to pan the host page.
    const header = overlay.querySelector('h3');
    if (header) {
      header.addEventListener('pointerdown', (e) => {
        if (e.button != null && e.button !== 0) return;
        if (e.target.closest('button, a, [data-reveal]')) return;
        e.preventDefault();
        try { header.setPointerCapture(e.pointerId); } catch (_) {}
        const startX = e.clientX, startY = e.clientY;
        const startLeft = parseFloat(overlay.style.left) || 0;
        const startTop = parseFloat(overlay.style.top) || 0;
        const onMove = (m) => {
          if (m.pointerId !== e.pointerId) return;
          geom.left = startLeft + (m.clientX - startX);
          geom.top = startTop + (m.clientY - startY);
          applyGeom();
        };
        const onUp = (u) => {
          if (u.pointerId !== e.pointerId) return;
          header.removeEventListener('pointermove', onMove);
          header.removeEventListener('pointerup', onUp);
          header.removeEventListener('pointercancel', onUp);
          try { header.releasePointerCapture(e.pointerId); } catch (_) {}
          saveGeom(geom);
        };
        header.addEventListener('pointermove', onMove);
        header.addEventListener('pointerup', onUp);
        header.addEventListener('pointercancel', onUp);
      });
    }

    // 8-direction resize. Each handle has data-dir = 'n'|'s'|'e'|'w'|
    // 'ne'|'nw'|'se'|'sw'. Direction string contains chars indicating which
    // edges to move; we apply deltas to those edges and clamp to MIN_W/MIN_H
    // so the opposite edge doesn't drift past the dragged one.
    overlay.querySelectorAll('.plonker-resize-handle').forEach(h => {
      h.addEventListener('pointerdown', (e) => {
        if (e.button != null && e.button !== 0) return;
        e.preventDefault();
        e.stopPropagation();
        try { h.setPointerCapture(e.pointerId); } catch (_) {}
        const dir = h.dataset.dir || '';
        const startX = e.clientX, startY = e.clientY;
        const startW = overlay.offsetWidth;
        const startH = overlay.offsetHeight;
        const startLeft = parseFloat(overlay.style.left) || 0;
        const startTop = parseFloat(overlay.style.top) || 0;
        const onMove = (m) => {
          if (m.pointerId !== e.pointerId) return;
          let dx = m.clientX - startX;
          let dy = m.clientY - startY;
          let newLeft = startLeft;
          let newTop = startTop;
          let newW = startW;
          let newH = startH;
          if (dir.includes('e')) {
            newW = Math.max(MIN_W, startW + dx);
          } else if (dir.includes('w')) {
            // Clamp dx so width never falls below MIN_W; the left edge is
            // pinned to the right edge minus MIN_W in that case.
            const clampedDx = Math.min(dx, startW - MIN_W);
            newW = startW - clampedDx;
            newLeft = startLeft + clampedDx;
          }
          if (dir.includes('s')) {
            newH = Math.max(MIN_H, startH + dy);
          } else if (dir.includes('n')) {
            const clampedDy = Math.min(dy, startH - MIN_H);
            newH = startH - clampedDy;
            newTop = startTop + clampedDy;
          }
          geom.left = newLeft;
          geom.top = newTop;
          geom.width = newW;
          geom.height = newH;
          applyGeom();
        };
        const onUp = (u) => {
          if (u.pointerId !== e.pointerId) return;
          h.removeEventListener('pointermove', onMove);
          h.removeEventListener('pointerup', onUp);
          h.removeEventListener('pointercancel', onUp);
          try { h.releasePointerCapture(e.pointerId); } catch (_) {}
          saveGeom(geom);
        };
        h.addEventListener('pointermove', onMove);
        h.addEventListener('pointerup', onUp);
        h.addEventListener('pointercancel', onUp);
      });
    });
  };

  const wireOverlayChrome = () => {
    overlay.querySelectorAll('.plonker-tab').forEach(b => {
      b.addEventListener('click', () => { ctx.showAll = false; setTab(b.dataset.tab); });
    });
    overlay.querySelectorAll('[data-reveal]').forEach(el => {
      el.addEventListener('click', () => el.classList.remove('plonker-spoiler-veil'));
    });
    overlay.querySelector('.plonker-close').addEventListener('click', dismiss);
    overlay.querySelectorAll('.plonker-fact-clickable').forEach(btn => {
      btn.addEventListener('click', (e) => {
        // Don't start a drag if the user clicks a fact button inside the header.
        e.stopPropagation();
        const slide = btn.dataset.slide;
        if (!slide) return;
        const lat = parseFloat(btn.dataset.lat);
        const lng = parseFloat(btn.dataset.lng);
        openMapLightbox(slide, btn.dataset.caption || '',
          isFinite(lat) ? lat : null, isFinite(lng) ? lng : null);
      });
    });
    overlay.querySelectorAll('.plonker-mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        if (view.mode === btn.dataset.mode) return;
        view.mode = btn.dataset.mode;
        ({ cc2, tips, places } = viewData());
        country = tips?.name || cc2;
        ctx.roundPlaces = places;
        ctx.showAll = false;
        tabs = buildTabs(tips, ctx);
        if (!tabs.some(t => t.id === activeId)) activeId = tabs[0].id;
        fullRender();
        overlay = container.querySelector('.plonker-overlay');
        contentEl = overlay.querySelector('[data-tab-content]');
        wireOverlayChrome();
        setTab(activeId);
      });
    });
    wireDragResize();
  };

  wireOverlayChrome();
  setTab(activeId);
};

// Cache TTL for cross-domain reopen: 1 hour. Long enough to revisit a round
// from Google Maps street view, short enough that yesterday's session won't
// pop up unsolicited.
const ROUND_CACHE_TTL_MS = 60 * 60 * 1000;

window.addEventListener('plonker:round-end', (e) => {
  lastRoundDetail = e.detail;
  // Persist so the chip can re-appear on google.com/maps after the user
  // clicks the round-result flag, even though that's a different origin.
  try {
    chrome.storage.local.set({
      plonkerLastRound: { detail: e.detail, savedAt: Date.now() }
    }).catch(() => {});
  } catch (_) { /* extension context invalidated, ignore */ }
  removeReopenChip();
  render(e.detail).catch(err => console.error('[plonker overlay]', err));
});
window.addEventListener('plonker:round-start', () => {
  try { chrome.storage.local.remove('plonkerLastRound').catch(() => {}); }
  catch (_) { /* swallow */ }
  fullDismiss();
});

// Auto-bootstrap on Google Maps: if there's a recent cached round from a
// just-finished GeoGuessr session, show the re-open chip so the user can
// pop the metas back open while exploring the actual location's pano.
(async () => {
  try {
    const onMaps =
      location.hostname.endsWith('google.com') &&
      location.pathname.startsWith('/maps');
    if (!onMaps) return;
    const got = await chrome.storage.local.get('plonkerLastRound');
    const cached = got.plonkerLastRound;
    if (!cached) return;
    const ageMs = Date.now() - (cached.savedAt || 0);
    if (ageMs > ROUND_CACHE_TTL_MS) return;
    lastRoundDetail = cached.detail;
    showReopenChip();
  } catch (e) { /* swallow */ }
})();

console.log('[plonker overlay v0.7] ready');
