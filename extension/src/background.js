// Service worker. Owns the Supabase client (so the publishable key never
// leaks into the page world), persists rounds + notes, serves cached tip data.
import { SUPABASE_URL, SUPABASE_KEY } from './config.js';
import { CC2_TO_CC3, normalizeCountry } from './lib/country-codes.js';
import { LEARNABLE_META_MAP_IDS } from './data/learnable-meta-map-ids.js';
import { COUNTRY_BY_ISO2 } from './data/country-slugs.js';

const REST = `${SUPABASE_URL}/rest/v1`;
const baseHeaders = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
  'Content-Type': 'application/json',
  Prefer: 'return=representation'
};

const sb = {
  async insert(table, row, opts = {}) {
    const url = new URL(`${REST}/${table}`);
    if (opts.onConflict) url.searchParams.set('on_conflict', opts.onConflict);
    const headers = { ...baseHeaders };
    if (opts.onConflict) headers.Prefer = 'resolution=merge-duplicates,return=representation';
    const r = await fetch(url, { method: 'POST', headers, body: JSON.stringify(row) });
    if (!r.ok) throw new Error(`${table} insert ${r.status}: ${await r.text()}`);
    return r.json();
  },
  async select(table, params = {}) {
    const url = new URL(`${REST}/${table}`);
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    const r = await fetch(url, { headers: baseHeaders });
    if (!r.ok) throw new Error(`${table} select ${r.status}: ${await r.text()}`);
    return r.json();
  }
};

let TIPS_CACHE = null;
const loadTips = async () => {
  if (TIPS_CACHE) return TIPS_CACHE;
  const url = chrome.runtime.getURL('data/tips.json');
  TIPS_CACHE = await fetch(url).then(r => r.json()).catch(() => ({}));
  return TIPS_CACHE;
};

const persistRound = async (p) => {
  const cc2 = normalizeCountry(p.actual?.countryCode);
  const cc3 = cc2 ? CC2_TO_CC3[cc2] : null;
  const row = {
    game_id: p.gameId,
    game_token: p.gameId,
    round_index: p.roundIndex,
    game_type: p.gameType,
    game_mode: p.gameMode,
    forbid_moving: p.forbidMoving,
    forbid_panning: p.forbidPanning,
    forbid_zooming: p.forbidZooming,
    map_id: p.mapId,
    map_name: p.mapName,
    is_learnable_meta_map: LEARNABLE_META_MAP_IDS.has(p.mapId),
    actual_lat: p.actual?.lat,
    actual_lng: p.actual?.lng,
    actual_country_iso2: cc2,
    actual_country_iso3: cc3,
    guess_lat: p.guess?.lat,
    guess_lng: p.guess?.lng,
    guess_country_iso2: normalizeCountry(p.guess?.countryCode),
    round_score: p.guess?.roundScore,
    distance_m: p.guess?.distance
  };
  return sb.insert('plonker_round', row, { onConflict: 'game_id,round_index' });
};

const tipsForCountry = async (cc2) => {
  if (!cc2) return null;
  const tips = await loadTips();
  const u = cc2.toUpperCase();
  const bundled = tips[u] || tips[u.toLowerCase()] || null;
  const meta = COUNTRY_BY_ISO2[u] || null;
  if (!bundled && !meta) return null;
  return {
    name: bundled?.name || meta?.name || u,
    plonkit_slug: bundled?.plonkit_slug || meta?.slug || null,
    key_meta: bundled?.key_meta || '',
    sections: bundled?.sections || [],
    vs: bundled?.vs || {}
  };
};

const buildDiagnostic = async (actual2, guess2) => {
  if (!guess2 || guess2 === actual2) return null;
  const tips = await loadTips();
  const a = tips[actual2?.toUpperCase()];
  const g = tips[guess2?.toUpperCase()];
  if (!a || !g) return null;
  return {
    yours: { country: g.name, key: g.key_meta || '' },
    correct: { country: a.name, key: a.key_meta || '' },
    distinguisher: a.vs?.[guess2?.toUpperCase()] || null
  };
};

chrome.runtime.onMessage.addListener((msg, _sender, send) => {
  (async () => {
    try {
      if (msg.type === 'round_end') {
        const inserted = await persistRound(msg.payload).catch(e => ({ error: String(e) }));
        const cc2 = normalizeCountry(msg.payload.actual?.countryCode);
        const guess2 = normalizeCountry(msg.payload.guess?.countryCode);
        send({
          ok: !inserted.error,
          row: Array.isArray(inserted) ? inserted[0] : inserted,
          tips: await tipsForCountry(cc2),
          diagnostic: await buildDiagnostic(cc2, guess2),
          isLearnableMetaMap: LEARNABLE_META_MAP_IDS.has(msg.payload.mapId)
        });
      } else if (msg.type === 'save_note') {
        const r = await sb.insert('plonker_note', msg.payload);
        send({ ok: true, row: r[0] });
      } else if (msg.type === 'get_stats') {
        const rows = await sb.select('plonker_round', {
          select: 'actual_country_iso2,guess_country_iso2,movement_label,round_score,played_at',
          order: 'played_at.desc',
          limit: 500
        });
        send({ ok: true, rows });
      } else {
        send({ ok: false, error: 'unknown message type' });
      }
    } catch (e) {
      send({ ok: false, error: String(e) });
    }
  })();
  return true;
});
