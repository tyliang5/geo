// Post-round overlay. Listens for the `plonker:round-end` CustomEvent
// dispatched by content.js (after background returns the persisted row + tips),
// renders a card in the bottom-right. Auto-dismisses on `plonker:round-start`.

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
  const got = await chrome.storage.local.get(['noSpoilers']);
  return { noSpoilers: !!got.noSpoilers };
};

const dismiss = () => {
  const el = document.getElementById('plonker-overlay-root');
  if (el) el.remove();
};

const render = async ({ round, server }) => {
  const container = ensureContainer();
  const cc2 = round.actual?.countryCode?.toUpperCase() ?? '??';
  const tips = server?.tips;
  const diag = server?.diagnostic;
  const isLM = server?.isLearnableMetaMap;
  const { noSpoilers } = await settings();

  const veilCls = noSpoilers ? 'plonker-spoiler-veil' : '';
  const country = tips?.name || cc2;
  const haveTips = (tips?.identify?.length ?? 0) > 0;
  const tipBullets = haveTips
    ? tips.identify.slice(0, 8).map(t => `<li>${escape(t)}</li>`).join('')
    : `<li><em>No bundled tips for ${escape(country)} yet \u2014 run <code>scraper/scrape_plonkit.py</code> to backfill, or click the plonkit link \u2192</em></li>`;

  const keyMetaHtml = (tips?.key_meta?.length ?? 0) > 0
    ? `<div class="plonker-keymeta"><strong>Key:</strong> ${tips.key_meta.slice(0, 3).map(escape).join(' \u00b7 ')}</div>`
    : '';

  const imagesHtml = (tips?.images?.length ?? 0) > 0
    ? `<div class="plonker-imgs">
        ${tips.images.slice(0, 6).map((img, i) => `
          <a class="plonker-img" href="${escape(img.full || img.src)}" target="_blank" rel="noopener" title="${escape(img.caption || '')}">
            <img src="${escape(img.src)}" loading="lazy" alt="">
          </a>`).join('')}
      </div>`
    : '';

  const diagHtml = diag ? `
    <div class="plonker-diag">
      <strong>Why ${escape(diag.correct.country)}, not ${escape(diag.yours.country)}?</strong><br>
      ${escape(diag.distinguisher || diag.correct.key || '')}
    </div>` : '';

  const plonkitSlug = tips?.plonkit_slug || (country.toLowerCase().replace(/\s+/g, '-'));
  const learnSlug = tips?.learnablemeta_slug;

  const lat = round.actual?.lat;
  const lng = round.actual?.lng;
  const streetViewLink = (lat != null && lng != null)
    ? `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${lat},${lng}&heading=${round.actual?.heading ?? 0}&pitch=${round.actual?.pitch ?? 0}`
    : null;

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
      <ul class="plonker-tip-list">${tipBullets}</ul>
      ${imagesHtml}
      ${diagHtml}
      <div class="plonker-links">
        ${plonkitSlug ? `<a href="https://www.plonkit.net/${plonkitSlug}" target="_blank" rel="noopener">plonkit</a>` : ''}
        ${learnSlug ? `<a href="https://learnablemeta.com/maps/${learnSlug}" target="_blank" rel="noopener">learn meta</a>` : ''}
        ${streetViewLink ? `<a href="${escape(streetViewLink)}" target="_blank" rel="noopener">street view</a>` : ''}
      </div>
      <div class="plonker-note">
        <div class="plonker-tags">
          ${META_TAGS.map(t => `<button class="plonker-tag" data-tag="${t}">${t}</button>`).join('')}
        </div>
        <textarea placeholder="What did you miss? (e.g., red/white striped bollard)"></textarea>
        <button class="plonker-save" disabled>Save note</button>
        <div class="plonker-meta" data-status></div>
      </div>
    </div>
  `;

  let chosenTag = null;
  const overlay = container.querySelector('.plonker-overlay');
  const ta = overlay.querySelector('textarea');
  const save = overlay.querySelector('.plonker-save');
  const status = overlay.querySelector('[data-status]');
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

  overlay.querySelectorAll('[data-reveal]').forEach(el => {
    el.addEventListener('click', () => el.classList.remove('plonker-spoiler-veil'));
  });

  overlay.querySelector('.plonker-close').addEventListener('click', dismiss);

  save.addEventListener('click', () => {
    save.disabled = true;
    status.textContent = 'saving\u2026';
    chrome.runtime.sendMessage({
      type: 'save_note',
      payload: {
        round_id: server?.row?.id,
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

window.addEventListener('plonker:round-end', (e) => {
  render(e.detail).catch(err => console.error('[plonker overlay]', err));
});

// Auto-dismiss when GG starts the next round so the card doesn't cover the pano.
window.addEventListener('plonker:round-start', dismiss);

console.log('[plonker overlay] ready');
