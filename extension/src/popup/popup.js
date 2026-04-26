const SETTING_KEYS = ['noSpoilers', 'lives', 'mcOptions', 'postRoundEnabled'];
const DEFAULTS = { noSpoilers: false, lives: 3, mcOptions: 4, postRoundEnabled: true };

const $ = (id) => document.getElementById(id);

const loadSettings = async () => {
  const stored = await chrome.storage.local.get(SETTING_KEYS);
  const merged = { ...DEFAULTS, ...stored };
  for (const k of SETTING_KEYS) {
    const el = $(k);
    if (!el) continue;
    if (el.type === 'checkbox') el.checked = !!merged[k];
    else el.value = merged[k];
    el.addEventListener('change', () => {
      const v = el.type === 'checkbox' ? el.checked : Number(el.value);
      chrome.storage.local.set({ [k]: v });
    });
  }
};

const refreshStats = async () => {
  chrome.runtime.sendMessage({ type: 'get_stats' }, (resp) => {
    if (!resp?.ok) {
      $('rounds').textContent = '!';
      return;
    }
    const rows = resp.rows || [];
    $('rounds').textContent = rows.length;

    const correct = rows.filter(r => r.actual_country_iso2 && r.guess_country_iso2 && r.actual_country_iso2 === r.guess_country_iso2).length;
    const ofTotal = rows.filter(r => r.guess_country_iso2).length;
    $('acc').textContent = ofTotal ? `${Math.round(correct / ofTotal * 100)}%` : '\u2014';

    const missByCountry = {};
    for (const r of rows) {
      if (!r.actual_country_iso2) continue;
      const m = missByCountry[r.actual_country_iso2] ||= { hit: 0, miss: 0 };
      if (r.actual_country_iso2 === r.guess_country_iso2) m.hit++;
      else if (r.guess_country_iso2) m.miss++;
    }
    const ranked = Object.entries(missByCountry)
      .filter(([, v]) => v.hit + v.miss >= 3)
      .sort((a, b) => (b[1].miss / (b[1].hit + b[1].miss)) - (a[1].miss / (a[1].hit + a[1].miss)));
    $('weak').textContent = ranked[0]?.[0] || '\u2014';
  });
};

loadSettings();
refreshStats();
