// Post-round overlay (v0.7). Consumes the merged learnablemeta + plonkit
// bundle. Tabs: Identify (LM atomic metas) / General (country-wide rules) /
// Regional (per-region tips, filtered by round location) / Spotlight (place-
// specific) / Images / Notes. Auto-dismisses on `plonker:round-start`.

const META_TAGS = ['bollard', 'language', 'plate', 'vegetation', 'other'];

const flagEmoji = (cc2) => {
  if (!cc2 || cc2.length !== 2) return '';
  const A = 0x1F1E6;
  return String.fromCodePoint(...[...cc2.toUpperCase()].map(c => A + c.charCodeAt(0) - 65));
};
const escape = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const ensureContainer = () => {
  let el = document.getElementById('plonker-overlay-root');
  if (el) el.remove();
  el = document.createElement('div');
  el.id = 'plonker-overlay-root';
  document.body.appendChild(el);
  return el;
};
const settings = async () => {
  const got = await chrome.storage.local.get(['noSpoilers', 'lastTab']);
  return { noSpoilers: !!got.noSpoilers, lastTab: got.lastTab || null };
};
const dismiss = () => {
  const el = document.getElementById('plonker-overlay-root');
  if (el) el.remove();
  closeLightbox();
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
const imageThumb = (src, caption) => `
  <button class="plonker-img-inline" data-src="${escape(src)}" data-caption="${escape(caption || '')}">
    <img src="${escape(src)}" loading="lazy" alt="">
  </button>`;

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

const wireImageHandlers = (overlay) => {
  overlay.querySelectorAll('.plonker-img-inline, .plonker-img-tile').forEach(btn => {
    btn.addEventListener('click', () => openLightbox(btn.dataset.src, btn.dataset.caption));
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
    return `<div class="plonker-img-grid">${tab.items.map(img => `
      <button class="plonker-img-tile" data-src="${escape(img.src)}" data-caption="${escape(img.caption || '')}">
        <img src="${escape(img.src)}" loading="lazy" alt="">
      </button>`).join('')}</div>`;
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
  const guessCc = round.guess?.countryCode?.toUpperCase() ?? null;
  const diag = server?.diagnostic;
  const isLM = server?.isLearnableMetaMap;
  const { noSpoilers, lastTab } = await settings();

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
  let activeId = (lastTab && tabs.some(t => t.id === lastTab)) ? lastTab : (tabs[0]?.id || 'notes');

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
  const diagHtml = () => (view.mode === 'actual' && diag) ? `
    <div class="plonker-diag">
      <strong>Why ${escape(diag.correct.country)}, not ${escape(diag.yours.country)}?</strong><br>
      ${escape(diag.distinguisher || diag.correct.key || '')}
    </div>` : '';

  const tabsHtml = () => `
    <div class="plonker-tab-strip" role="tablist">
      ${tabs.map(t => `
        <button class="plonker-tab ${t.id === activeId ? 'active' : ''}"
                data-tab="${escape(t.id)}" role="tab" aria-selected="${t.id === activeId}">
          ${escape(t.label)}
        </button>`).join('')}
    </div>`;

  const fullRender = () => {
    container.innerHTML = `
    <div class="plonker-overlay" role="dialog" aria-label="Plonker round summary">
      ${headerHtml()}
      ${isLM ? '<div class="plonker-meta">Learnable-meta map \u2014 deliberate drill</div>' : ''}
      ${modeSwitchHtml()}
      ${keyMetaHtml()}
      ${diagHtml()}
      ${linksHtml()}
      ${tabsHtml()}
      <div class="plonker-tab-content" data-tab-content></div>
    </div>
  `;
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
    contentEl.innerHTML = renderTabContent(tab, ctx);
    if (tab.kind === 'notes') wireNotesTab(overlay, ctx);
    else wireImageHandlers(overlay);
    overlay.querySelectorAll('.plonker-show-all').forEach(btn => {
      btn.addEventListener('click', () => { ctx.showAll = true; setTab(tab.id); });
    });
    chrome.storage.local.set({ lastTab: tab.id });
  };

  const wireOverlayChrome = () => {
    overlay.querySelectorAll('.plonker-tab').forEach(b => {
      b.addEventListener('click', () => { ctx.showAll = false; setTab(b.dataset.tab); });
    });
    overlay.querySelectorAll('[data-reveal]').forEach(el => {
      el.addEventListener('click', () => el.classList.remove('plonker-spoiler-veil'));
    });
    overlay.querySelector('.plonker-close').addEventListener('click', dismiss);
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
  };

  wireOverlayChrome();
  setTab(activeId);
};

window.addEventListener('plonker:round-end', (e) => {
  render(e.detail).catch(err => console.error('[plonker overlay]', err));
});
window.addEventListener('plonker:round-start', dismiss);
console.log('[plonker overlay v0.7] ready');
