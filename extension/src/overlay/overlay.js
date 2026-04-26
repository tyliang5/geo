// Post-round overlay. Listens for the `plonker:round-end` CustomEvent
// dispatched by content.js (after background returns the persisted row + tips),
// renders a card in the bottom-right.

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

const render = async ({ round, server }) => {
  const container = ensureContainer();
  const cc2 = round.actual?.countryCode?.toUpperCase() ?? '??';
  const tips = server?.tips;
  const diag = server?.diagnostic;
  const isLM = server?.isLearnableMetaMap;
  const { noSpoilers } = await settings();

  const veilCls = noSpoilers ? 'plonker-spoiler-veil' : '';
  const country = tips?.name || cc2;
  const tipBullets = (tips?.identify || []).slice(0, 5).map(t => `<li>${escape(t)}</li>`).join('') || '<li><em>No bundled tips for this country yet — check the plonkit link.</em></li>';

  const diagHtml = diag ? `
    <div class="plonker-diag">
      <strong>Why ${escape(diag.correct.country)}, not ${escape(diag.yours.country)}?</strong><br>
      ${escape(diag.distinguisher || diag.correct.key || '')}
    </div>` : '';

  const plonkitSlug = (tips?.plonkit_slug) || (country.toLowerCase().replace(/\s+/g, '-'));
  const learnSlug = tips?.learnablemeta_slug;

  container.innerHTML = `
    <div class="plonker-overlay">
      <h3>
        <span><span class="plonker-flag ${veilCls}" data-reveal>${escape(flagEmoji(cc2))}</span><span class="${veilCls}" data-reveal>${escape(country)}</span></span>
        <button class="plonker-close" title="Close">\u00d7</button>
      </h3>
      ${isLM ? '<div class="plonker-meta">Learnable-meta map — these are deliberate drills.</div>' : ''}
      <ul class="plonker-tip-list">${tipBullets}</ul>
      ${diagHtml}
      <div class="plonker-links">
        <a href="https://www.plonkit.net/${plonkitSlug}" target="_blank" rel="noopener">plonkit</a>
        ${learnSlug ? `<a href="https://learnablemeta.com/maps/${learnSlug}" target="_blank" rel="noopener">learnable meta</a>` : ''}
        ${round.actual?.lat != null ? `<a href="https://www.google.com/maps?q=${round.actual.lat},${round.actual.lng}" target="_blank" rel="noopener">street view</a>` : ''}
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

  overlay.querySelector('.plonker-close').addEventListener('click', () => container.remove());

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
      if (resp?.ok) setTimeout(() => container.remove(), 900);
      else save.disabled = false;
    });
  });
};

window.addEventListener('plonker:round-end', (e) => {
  render(e.detail).catch(err => console.error('[plonker overlay]', err));
});

console.log('[plonker overlay] ready');
