// Plonker Dashboard (v0.9). Loads round history from Supabase, computes
// per-country accuracy, paints a world heatmap + ranked tables. Click
// a country to drill into per-meta and recent-rounds detail.

const $ = (id) => document.getElementById(id);
const flagEmoji = (cc2) => {
  if (!cc2 || cc2.length !== 2) return '';
  const A = 0x1F1E6;
  return String.fromCodePoint(...[...cc2.toUpperCase()].map(c => A + c.charCodeAt(0) - 65));
};
const escape = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// ISO-2 -> ISO-3 (subset, used to match Natural Earth path IDs which use 3-letter codes).
const ISO3 = {
  AD:'AND',AE:'ARE',AF:'AFG',AG:'ATG',AI:'AIA',AL:'ALB',AM:'ARM',AO:'AGO',AR:'ARG',AS:'ASM',AT:'AUT',AU:'AUS',AW:'ABW',AZ:'AZE',
  BA:'BIH',BB:'BRB',BD:'BGD',BE:'BEL',BF:'BFA',BG:'BGR',BH:'BHR',BI:'BDI',BJ:'BEN',BM:'BMU',BN:'BRN',BO:'BOL',BR:'BRA',BS:'BHS',BT:'BTN',BW:'BWA',BY:'BLR',BZ:'BLZ',
  CA:'CAN',CD:'COD',CF:'CAF',CG:'COG',CH:'CHE',CI:'CIV',CL:'CHL',CM:'CMR',CN:'CHN',CO:'COL',CR:'CRI',CU:'CUB',CY:'CYP',CZ:'CZE',
  DE:'DEU',DJ:'DJI',DK:'DNK',DM:'DMA',DO:'DOM',DZ:'DZA',
  EC:'ECU',EE:'EST',EG:'EGY',ER:'ERI',ES:'ESP',ET:'ETH',
  FI:'FIN',FJ:'FJI',FK:'FLK',FM:'FSM',FR:'FRA',
  GA:'GAB',GB:'GBR',GD:'GRD',GE:'GEO',GH:'GHA',GL:'GRL',GM:'GMB',GN:'GIN',GQ:'GNQ',GR:'GRC',GT:'GTM',GW:'GNB',GY:'GUY',
  HN:'HND',HR:'HRV',HT:'HTI',HU:'HUN',
  ID:'IDN',IE:'IRL',IL:'ISR',IN:'IND',IQ:'IRQ',IR:'IRN',IS:'ISL',IT:'ITA',
  JM:'JAM',JO:'JOR',JP:'JPN',
  KE:'KEN',KG:'KGZ',KH:'KHM',KI:'KIR',KM:'COM',KP:'PRK',KR:'KOR',KW:'KWT',KZ:'KAZ',
  LA:'LAO',LB:'LBN',LC:'LCA',LI:'LIE',LK:'LKA',LR:'LBR',LS:'LSO',LT:'LTU',LU:'LUX',LV:'LVA',LY:'LBY',
  MA:'MAR',MC:'MCO',MD:'MDA',ME:'MNE',MG:'MDG',MK:'MKD',ML:'MLI',MM:'MMR',MN:'MNG',MR:'MRT',MT:'MLT',MU:'MUS',MV:'MDV',MW:'MWI',MX:'MEX',MY:'MYS',MZ:'MOZ',
  NA:'NAM',NE:'NER',NG:'NGA',NI:'NIC',NL:'NLD',NO:'NOR',NP:'NPL',NZ:'NZL',
  OM:'OMN',
  PA:'PAN',PE:'PER',PG:'PNG',PH:'PHL',PK:'PAK',PL:'POL',PR:'PRI',PT:'PRT',PY:'PRY',
  QA:'QAT',
  RO:'ROU',RS:'SRB',RU:'RUS',RW:'RWA',
  SA:'SAU',SB:'SLB',SC:'SYC',SD:'SDN',SE:'SWE',SG:'SGP',SI:'SVN',SK:'SVK',SL:'SLE',SM:'SMR',SN:'SEN',SO:'SOM',SR:'SUR',SS:'SSD',SV:'SLV',SY:'SYR',SZ:'SWZ',
  TD:'TCD',TG:'TGO',TH:'THA',TJ:'TJK',TL:'TLS',TM:'TKM',TN:'TUN',TO:'TON',TR:'TUR',TT:'TTO',TW:'TWN',TZ:'TZA',
  UA:'UKR',UG:'UGA',US:'USA',UY:'URY',UZ:'UZB',
  VA:'VAT',VC:'VCT',VE:'VEN',VN:'VNM',VU:'VUT',
  XK:'XKX',
  YE:'YEM',
  ZA:'ZAF',ZM:'ZMB',ZW:'ZWE'
};
const ISO2_FROM_ISO3 = Object.fromEntries(Object.entries(ISO3).map(([a, b]) => [b, a]));

const colorFor = (acc) => {
  if (acc == null) return '#1f2937';
  if (acc < 0.2) return '#ef4444';
  if (acc < 0.4) return '#f59e0b';
  if (acc < 0.6) return '#facc15';
  if (acc < 0.8) return '#84cc16';
  return '#10b981';
};

let TIPS = null;
const loadTips = async () => {
  if (TIPS) return TIPS;
  TIPS = await fetch(chrome.runtime.getURL('data/tips.json')).then(r => r.json());
  return TIPS;
};

let WORLD = null;
const loadWorldMap = async () => {
  if (WORLD) return WORLD;
  // Inline SVG path data shipped as a static asset.
  const url = chrome.runtime.getURL('assets/world.svg');
  const txt = await fetch(url).then(r => r.text()).catch(() => '');
  WORLD = txt;
  return WORLD;
};

async function loadRounds() {
  const resp = await chrome.runtime.sendMessage({ type: 'get_stats' });
  if (!resp?.ok) {
    console.warn('[dashboard] get_stats failed', resp);
    return [];
  }
  return resp.rows || [];
}

function aggregateByCountry(rounds) {
  const agg = {};
  for (const r of rounds) {
    const cc = r.actual_country_iso2;
    if (!cc) continue;
    const a = agg[cc] || (agg[cc] = { hit: 0, miss: 0, total: 0 });
    a.total++;
    if (r.guess_country_iso2 === cc) a.hit++;
    else if (r.guess_country_iso2) a.miss++;
  }
  for (const a of Object.values(agg)) {
    // Accuracy denominator is hit+miss (i.e. rounds with a guess) so timeouts
    // / abandoned rounds don't tank the percentage. Matches popup logic.
    const denom = a.hit + a.miss;
    a.acc = denom ? a.hit / denom : 0;
  }
  return agg;
}

function paintMap(svgText, agg) {
  const mapEl = $('map');
  if (!svgText) {
    mapEl.innerHTML = `<div style="padding:20px;color:#9ca3af">
      Map asset missing (assets/world.svg). Heatmap disabled; ranked lists still work.
    </div>`;
    return;
  }
  mapEl.innerHTML = svgText;
  const svg = mapEl.querySelector('svg');
  if (!svg) return;
  // amCharts world SVG uses id="ISO2" on each <path>; some other sources use
  // ISO-3 or data attributes. Cover all of them.
  const paths = svg.querySelectorAll('path');
  paths.forEach(p => {
    const rawId = (p.id || '').toUpperCase();
    const a3 = (p.getAttribute('data-iso-a3') || '').toUpperCase();
    const a2 = (p.getAttribute('data-iso-a2') || '').toUpperCase();
    let cc = null;
    if (rawId.length === 2) cc = rawId;
    else if (rawId.length === 3 && ISO2_FROM_ISO3[rawId]) cc = ISO2_FROM_ISO3[rawId];
    else if (a2.length === 2) cc = a2;
    else if (a3.length === 3 && ISO2_FROM_ISO3[a3]) cc = ISO2_FROM_ISO3[a3];
    if (!cc) return;
    p.classList.add('country');
    p.setAttribute('data-cc', cc);
    const a = agg[cc];
    p.setAttribute('fill', colorFor(a?.acc));
    p.addEventListener('click', () => openDrilldown(cc));
    const tipBits = a
      ? `${cc}: ${Math.round(a.acc * 100)}% (${a.hit}/${a.total})`
      : `${cc}: untouched`;
    p.setAttribute('title', tipBits);
  });
}

function paintTables(rounds, agg, tips) {
  const ranked = Object.entries(agg)
    .filter(([, v]) => v.total >= 2)
    .map(([cc, v]) => ({ cc, ...v }));
  const worst = ranked.slice().sort((a, b) => a.acc - b.acc).slice(0, 12);
  const best = ranked.slice().sort((a, b) => b.acc - a.acc).slice(0, 12);

  const renderRow = (r) => `
    <tr data-cc="${r.cc}">
      <td class="flag">${flagEmoji(r.cc)}</td>
      <td class="cc">${r.cc}</td>
      <td>${escape(tips[r.cc]?.name || r.cc)}</td>
      <td class="acc">${Math.round(r.acc * 100)}% (${r.hit}/${r.total})</td>
    </tr>`;
  const wireClicks = (table) => {
    table.querySelectorAll('tr[data-cc]').forEach(tr => {
      tr.addEventListener('click', () => openDrilldown(tr.dataset.cc));
    });
  };

  const wt = $('worst').querySelector('tbody');
  wt.innerHTML = worst.map(renderRow).join('') || '<tr><td colspan=4 style="color:#9ca3af">No data yet — play some rounds.</td></tr>';
  wireClicks($('worst'));
  const bt = $('best').querySelector('tbody');
  bt.innerHTML = best.map(renderRow).join('') || '';
  wireClicks($('best'));

  const recent = rounds.slice(0, 10);
  const rt = $('recent').querySelector('tbody');
  rt.innerHTML = recent.map(r => `
    <tr data-cc="${r.actual_country_iso2 || ''}">
      <td class="flag">${flagEmoji(r.actual_country_iso2)}</td>
      <td class="cc">${r.actual_country_iso2 || '?'}</td>
      <td>${r.movement_label || '?'} ${r.round_score != null ? `${r.round_score}` : ''}</td>
      <td class="acc">${r.guess_country_iso2 === r.actual_country_iso2 ? '\u2713' : (r.guess_country_iso2 ? '\u2717' : '\u2014')}</td>
    </tr>`).join('') || '<tr><td colspan=4 style="color:#9ca3af">No rounds yet.</td></tr>';
  wireClicks($('recent'));
}

async function openDrilldown(cc) {
  const tips = await loadTips();
  const c = tips[cc];
  if (!c) return;
  $('dhCountry').textContent = `${flagEmoji(cc)} ${c.name}`;
  const body = $('dbody');
  const sections = [];
  if (c.metas?.length) {
    sections.push(`<h3>Identify</h3><ul>${c.metas.slice(0, 6).map(m => `
      <li><strong>${escape(m.type)}:</strong> ${escape(m.description)}</li>`).join('')}</ul>`);
  }
  if (c.regions && Object.keys(c.regions).length) {
    sections.push(`<h3>Regions covered</h3><div>${Object.keys(c.regions).map(r => `<span style="background:#374151;padding:2px 8px;border-radius:999px;margin-right:4px;font-size:12px">${escape(r)}</span>`).join('')}</div>`);
  }
  if (c.spotlight?.length) {
    sections.push(`<h3>Spotlight places</h3><div>${c.spotlight.map(s => escape(s.place)).filter((v,i,a)=>a.indexOf(v)===i).slice(0,8).map(p => `<span style="background:#374151;padding:2px 8px;border-radius:999px;margin-right:4px;font-size:12px">${p}</span>`).join('')}</div>`);
  }
  body.innerHTML = sections.join('') || '<div style="color:#9ca3af">No tip data for this country.</div>';
  $('drilldown').style.display = 'flex';
}

async function refresh() {
  const tips = await loadTips();
  const rounds = await loadRounds();
  $('totals').textContent = `${rounds.length} rounds`;
  const agg = aggregateByCountry(rounds);
  paintTables(rounds, agg, tips);
  const svg = await loadWorldMap();
  paintMap(svg, agg);
}

document.addEventListener('DOMContentLoaded', () => {
  $('reload').addEventListener('click', refresh);
  $('dhClose').addEventListener('click', () => { $('drilldown').style.display = 'none'; });
  $('drilldown').addEventListener('click', (e) => {
    if (e.target === $('drilldown')) $('drilldown').style.display = 'none';
  });
  refresh();
});
