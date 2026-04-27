// Post-round overlay. Tabbed UI driven by per-country sections from tips.json.
// Each section's items are rendered in plonkit's original order so an image
// stays adjacent to the text that explains it. Click an image to pop the
// lightbox; auto-dismiss on `plonker:round-start`.

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

// ---------- tabs ----------
// Walk Regional + Spotlight items. Untagged text (and the images that follow
// it) is country-wide-but-useful-for-regional-ID material — phone numbers,
// plate region letters, postal code patterns. Pull those out into a General
// tab so Regional/Spotlight can be strictly location-matched.
const partitionRegionItems = (tips) => {
  const general = [];
  const regional = { id: 'regional', title: 'Regional', items: [] };
  const spotlight = { id: 'spotlight', title: 'Spotlight', items: [] };
  for (const sec of tips?.sections || []) {
    if (sec.id === 'identify') continue;
    const target = sec.id === 'spotlight' ? spotlight : regional;
    let lastWasGeneral = false;
    for (const it of sec.items) {
      if (it.type === 'text') {
        const isGen = !it.places || it.places.length === 0;
        if (isGen) {
          general.push({ ...it, _from: sec.title });
          lastWasGeneral = true;
        } else {
          target.items.push(it);
          lastWasGeneral = false;
        }
      } else if (it.type === 'image') {
        if (lastWasGeneral) general.push(it);
        else target.items.push(it);
      }
    }
  }
  return { general, regional, spotlight };
};

const buildTabs = (tips) => {
  const tabs = [];
  if (tips?.sections?.length) {
    const identify = tips.sections.find(s => s.id === 'identify');
    if (identify) {
      tabs.push({ id: 'identify', label: identify.title, kind: 'section', section: identify });
    }
    const { general, regional, spotlight } = partitionRegionItems(tips);
    if (general.length) {
      tabs.push({ id: 'general', label: 'General', kind: 'section',
                  section: { id: 'general', title: 'General', items: general } });
    }
    if (regional.items.length) {
      tabs.push({ id: 'regional', label: regional.title, kind: 'section', section: regional });
    }
    if (spotlight.items.length) {
      tabs.push({ id: 'spotlight', label: spotlight.title, kind: 'section', section: spotlight });
    }
    const allImages = tips.sections.flatMap(s =>
      (s.items || []).filter(i => i.type === 'image')
    );
    if (allImages.length > 0) {
      tabs.push({ id: 'images', label: `Images (${allImages.length})`, kind: 'images', images: allImages });
    }
  }
  tabs.push({ id: 'notes', label: 'Notes', kind: 'notes' });
  return tabs;
};

// Filter section items by place match. A text item is kept if:
//   * it has no `places` tags (general country-wide tip), OR
//   * any of its `places` overlaps with the round's geocoded place names.
// Adjacent images travel with the previous text decision so visual pairing
// is preserved. Identify section is never filtered.
//
// `norm` decomposes Unicode (NFD) and strips combining marks so umlauts and
// accents fold consistently — Nominatim returns "Oberösterreich", plonkit
// often uses "Upper Austria"; both must match each other AND each other's
// ASCII forms after stripping.
const norm = (s) => String(s)
  .toLowerCase()
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .replace(/[^a-z0-9]/g, '');

// Common English<->local name pairs we know plonkit uses on one side and
// Nominatim returns on the other. Only the cases that genuinely break
// substring matching belong here.
const NAME_ALIASES = {
  'upperaustria':       ['oberosterreich'],
  'loweraustria':       ['niederosterreich'],
  'styria':             ['steiermark'],
  'carinthia':          ['karnten'],
  'tyrol':              ['tirol'],
  'vienna':             ['wien'],
  'bavaria':            ['bayern'],
  'saxony':             ['sachsen'],
  'thuringia':          ['thuringen'],
  'mecklenburgvorpommern': ['mecklenburgwesternpomerania'],
  'newsouthwales':      ['nsw'],
  'queensland':         ['qld'],
  'victoria':           ['vic'],
  'westernaustralia':   ['wa'],
  'southaustralia':     ['sa'],
  'tasmania':           ['tas'],
};
const expand = (n) => {
  const out = new Set([n]);
  if (NAME_ALIASES[n]) NAME_ALIASES[n].forEach(a => out.add(a));
  for (const [k, vs] of Object.entries(NAME_ALIASES)) {
    if (vs.includes(n)) out.add(k);
  }
  return out;
};
const placeMatch = (tipPlaces, roundPlaces) => {
  if (!tipPlaces || tipPlaces.length === 0) return null; // general
  const rpExpanded = new Set();
  roundPlaces.forEach(p => expand(norm(p)).forEach(x => rpExpanded.add(x)));
  for (const tp of tipPlaces) {
    const variants = expand(norm(tp));
    for (const v of variants) {
      if (v.length < 3) continue;
      for (const r of rpExpanded) {
        if (r.length < 3) continue;
        if (r.includes(v) || v.includes(r)) return true;
      }
    }
  }
  return false;
};

const filterSectionItems = (section, roundPlaces, showAll) => {
  // Identify and General are country-wide; never filtered by location.
  if (showAll || section.id === 'identify' || section.id === 'general' || !roundPlaces?.length) {
    return section.items;
  }
  const out = [];
  let lastTextKept = true;
  for (const it of section.items) {
    if (it.type === 'text') {
      // After partitioning, Regional/Spotlight only contain place-tagged text.
      // We strictly drop place mismatches here (no "general -> keep" fallback).
      const m = placeMatch(it.places, roundPlaces);
      const keep = m === true;
      if (keep) out.push(it);
      lastTextKept = keep;
    } else if (it.type === 'image') {
      if (lastTextKept) out.push(it);
    }
  }
  return out;
};

const renderItem = (it) => {
  if (it.type === 'text') return `<p class="plonker-tip">${escape(it.text)}</p>`;
  if (it.type === 'image') {
    return `<button class="plonker-img-inline" data-src="${escape(it.src)}" data-caption="${escape(it.caption || '')}">
      <img src="${escape(it.src)}" loading="lazy" alt="">
      ${it.caption ? `<span class="plonker-img-cap">${escape(it.caption)}</span>` : ''}
    </button>`;
  }
  return '';
};

const renderTabContent = (tab, ctx) => {
  if (tab.kind === 'section') {
    if (!tab.section.items?.length) return '<div class="plonker-empty">No content for this section.</div>';
    const filtered = filterSectionItems(tab.section, ctx.roundPlaces, ctx.showAll);
    if (filtered.length === 0) {
      return `<div class="plonker-empty">
        No region-specific tips matched <strong>${escape(ctx.roundPlaces.slice(0, 2).join(', ') || 'this location')}</strong>.
        <button class="plonker-show-all" style="margin-top:10px;display:inline-block">Show all anyway</button>
      </div>`;
    }
    const filteredOut = tab.section.items.length - filtered.length;
    const isFilterable = !['identify', 'general'].includes(tab.id);
    const filterChip = (isFilterable && ctx.roundPlaces?.length && filteredOut > 0 && !ctx.showAll)
      ? `<div class="plonker-filter-chip">
           <span>Filtered to <strong>${escape(ctx.roundPlaces.slice(0, 3).join(', '))}</strong> \u2014 hiding ${filteredOut} unrelated tip${filteredOut === 1 ? '' : 's'}.</span>
           <button class="plonker-show-all">Show all</button>
         </div>` : '';
    return `${filterChip}<div class="plonker-section">${filtered.map(renderItem).join('')}</div>`;
  }
  if (tab.kind === 'images') {
    return `<div class="plonker-img-grid">${tab.images.map(img => `
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

const wireImageHandlers = (overlay) => {
  overlay.querySelectorAll('.plonker-img-inline, .plonker-img-tile').forEach(btn => {
    btn.addEventListener('click', () => {
      openLightbox(btn.dataset.src, btn.dataset.caption);
    });
  });
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
      payload: {
        round_id: ctx.roundId,
        meta_tag: chosenTag,
        comment: ta.value.trim() || null
      }
    }, (resp) => {
      status.textContent = resp?.ok ? 'saved \u2713' : `error: ${resp?.error || 'unknown'}`;
      if (resp?.ok) setTimeout(dismiss, 700);
      else save.disabled = false;
    });
  });
};

const render = async ({ round, server }) => {
  const container = ensureContainer();
  const cc2 = round.actual?.countryCode?.toUpperCase() ?? '??';
  const tips = server?.tips;
  const diag = server?.diagnostic;
  const isLM = server?.isLearnableMetaMap;
  const { noSpoilers, lastTab } = await settings();

  const veilCls = noSpoilers ? 'plonker-spoiler-veil' : '';
  const country = tips?.name || cc2;

  const tabs = buildTabs(tips);
  const activeId = (lastTab && tabs.some(t => t.id === lastTab)) ? lastTab : tabs[0].id;

  const keyMetaHtml = tips?.key_meta
    ? `<div class="plonker-keymeta"><strong>Key:</strong> ${escape(tips.key_meta)}</div>`
    : '';
  const diagHtml = diag ? `
    <div class="plonker-diag">
      <strong>Why ${escape(diag.correct.country)}, not ${escape(diag.yours.country)}?</strong><br>
      ${escape(diag.distinguisher || diag.correct.key || '')}
    </div>` : '';

  const plonkitSlug = tips?.plonkit_slug || (country.toLowerCase().replace(/\s+/g, '-'));
  const lat = round.actual?.lat;
  const lng = round.actual?.lng;
  const streetViewLink = (lat != null && lng != null)
    ? `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}&heading=${round.actual?.heading ?? 0}&pitch=${round.actual?.pitch ?? 0}`
    : null;

  const tabsHtml = `
    <div class="plonker-tab-strip" role="tablist">
      ${tabs.map(t => `
        <button class="plonker-tab ${t.id === activeId ? 'active' : ''}"
                data-tab="${escape(t.id)}" role="tab" aria-selected="${t.id === activeId}">
          ${escape(t.label)}
        </button>`).join('')}
    </div>`;

  container.innerHTML = `
    <div class="plonker-overlay" role="dialog" aria-label="Plonker round summary">
      <h3>
        <span><span class="plonker-flag ${veilCls}" data-reveal>${escape(flagEmoji(cc2))}</span><span class="${veilCls}" data-reveal>${escape(country)}</span></span>
        <span class="plonker-h3-actions">
          ${round.guess?.roundScore != null ? `<span class="plonker-score">${escape(round.guess.roundScore)} pts</span>` : ''}
          <button class="plonker-close" title="Close">\u00d7</button>
        </span>
      </h3>
      ${isLM ? '<div class="plonker-meta">Learnable-meta map \u2014 deliberate drill</div>' : ''}
      ${keyMetaHtml}
      ${diagHtml}
      <div class="plonker-links">
        ${plonkitSlug ? `<a href="https://www.plonkit.net/${plonkitSlug}" target="_blank" rel="noopener">plonkit</a>` : ''}
        ${streetViewLink ? `<a href="${escape(streetViewLink)}" target="_blank" rel="noopener">street view</a>` : ''}
        <a href="https://learnablemeta.com/maps" target="_blank" rel="noopener">learn meta</a>
      </div>
      ${tabsHtml}
      <div class="plonker-tab-content" data-tab-content></div>
    </div>
  `;

  const overlay = container.querySelector('.plonker-overlay');
  const contentEl = overlay.querySelector('[data-tab-content]');
  const ctx = {
    roundId: server?.row?.id,
    roundPlaces: server?.places || [],
    showAll: false
  };

  const setTab = (id) => {
    const tab = tabs.find(t => t.id === id) || tabs[0];
    overlay.querySelectorAll('.plonker-tab').forEach(b => {
      const on = b.dataset.tab === tab.id;
      b.classList.toggle('active', on);
      b.setAttribute('aria-selected', on);
    });
    contentEl.innerHTML = renderTabContent(tab, ctx);
    if (tab.kind === 'notes') wireNotesTab(overlay, ctx);
    else wireImageHandlers(overlay);
    const showAllBtn = overlay.querySelector('.plonker-show-all');
    if (showAllBtn) {
      showAllBtn.addEventListener('click', () => {
        ctx.showAll = true;
        setTab(tab.id);
      });
    }
    chrome.storage.local.set({ lastTab: tab.id });
  };

  overlay.querySelectorAll('.plonker-tab').forEach(b => {
    b.addEventListener('click', () => {
      ctx.showAll = false; // reset filter when switching tabs
      setTab(b.dataset.tab);
    });
  });
  overlay.querySelectorAll('[data-reveal]').forEach(el => {
    el.addEventListener('click', () => el.classList.remove('plonker-spoiler-veil'));
  });
  overlay.querySelector('.plonker-close').addEventListener('click', dismiss);

  setTab(activeId);
};

window.addEventListener('plonker:round-end', (e) => {
  render(e.detail).catch(err => console.error('[plonker overlay]', err));
});
window.addEventListener('plonker:round-start', dismiss);

console.log('[plonker overlay] ready');
