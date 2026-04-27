// Plonker study mode (v0.9). Country-identification MC quiz with Leitner-box
// spaced repetition. Cards are pulled from tips.json metas; distractors are
// drawn from regional neighbors when "hard" is selected.

const $ = (id) => document.getElementById(id);

// ---------- region groupings (focus filter) ----------
const REGION_GROUPS = {
  EU: ['AL','AD','AT','BY','BE','BA','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IS','IE','IM','IT','JE','XK','LV','LI','LT','LU','MT','MD','MC','ME','NL','MK','NO','PL','PT','RO','SM','RS','SK','SI','ES','SE','CH','UA','GB','VA'],
  AS: ['AF','AM','AZ','BH','BD','BT','BN','KH','CN','GE','HK','IN','ID','IR','IQ','IL','JP','JO','KZ','KW','KG','LA','LB','MO','MY','MV','MN','MM','NP','KP','OM','PK','PS','PH','QA','SA','SG','KR','LK','SY','TW','TJ','TH','TL','TR','TM','AE','UZ','VN','YE'],
  AF: ['DZ','AO','BJ','BW','BF','BI','CM','CV','CF','TD','KM','CG','CD','CI','DJ','EG','GQ','ER','SZ','ET','GA','GM','GH','GN','GW','KE','LS','LR','LY','MG','MW','ML','MR','MU','MA','MZ','NA','NE','NG','RW','ST','SN','SC','SL','SO','ZA','SS','SD','TZ','TG','TN','UG','ZM','ZW','EH'],
  NA: ['AG','BS','BB','BZ','CA','CR','CU','DM','DO','SV','GD','GT','HT','HN','JM','MX','NI','PA','KN','LC','VC','TT','US','PR','VI','BM','GP','MQ','GL','PM'],
  SA: ['AR','BO','BR','CL','CO','EC','FK','GF','GY','PY','PE','SR','UY','VE'],
  OC: ['AS','AU','CK','FJ','PF','GU','KI','MH','FM','NR','NC','NZ','MP','PW','PG','WS','SB','TK','TO','TV','VU','WF'],
  baltic: ['LV','LT','EE'],
  nordic: ['SE','NO','DK','FI','IS','SJ','FO','GL'],
  balkan: ['AL','BA','BG','HR','XK','MK','ME','RO','RS','SI'],
  'se-asia': ['BN','KH','ID','LA','MY','MM','PH','SG','TH','TL','VN'],
  latam: ['AR','BO','BR','CL','CO','CR','CU','DO','EC','SV','GT','HN','MX','NI','PA','PY','PE','PR','UY','VE'],
  'confused-eu-east': ['BY','RU','UA'],
  'confused-cz-sk': ['CZ','SK'],
  'confused-ar-uy': ['AR','UY'],
};

// Hard-distractor neighbors per country. When the user picks "hard"
// distractors, we draw from this set first.
const NEIGHBORS = {
  AT: ['DE','CH','IT','SI','HU','SK','CZ','LI'],
  BY: ['RU','UA','PL','LT','LV'],
  RU: ['BY','UA','KZ','EE','LV','LT','FI','MN','GE'],
  UA: ['RU','BY','PL','SK','HU','RO','MD'],
  CZ: ['SK','PL','DE','AT'],
  SK: ['CZ','PL','UA','HU','AT'],
  AR: ['UY','CL','PY','BO','BR'],
  UY: ['AR','BR'],
  CL: ['AR','BO','PE'],
  PE: ['CL','BO','BR','EC','CO'],
  CO: ['VE','BR','PE','EC','PA'],
  BR: ['UY','AR','PY','BO','PE','CO','VE','GY','SR','GF'],
  DE: ['NL','BE','LU','FR','CH','AT','CZ','PL','DK'],
  FR: ['BE','LU','DE','CH','IT','MC','ES','AD'],
  ES: ['PT','FR','AD','MA'],
  PT: ['ES'],
  IT: ['FR','CH','AT','SI','SM','VA','MT'],
  PL: ['DE','CZ','SK','UA','BY','LT','RU'],
  AU: ['NZ'],
  NZ: ['AU'],
  JP: ['KR','TW'],
  KR: ['JP','KP','CN','TW'],
  TH: ['LA','MM','KH','MY'],
  VN: ['LA','KH','CN'],
  ID: ['MY','SG','PH','TL','PG','BN'],
  MY: ['ID','SG','TH','BN'],
  IN: ['PK','NP','BT','BD','MM','LK','CN'],
  PK: ['IN','AF','IR','CN'],
  US: ['CA','MX'],
  CA: ['US','GL'],
  MX: ['US','GT','BZ'],
  GR: ['AL','BG','MK','TR'],
  TR: ['GR','BG','GE','AM','AZ','SY','IQ','IR'],
  HU: ['SK','UA','RO','RS','HR','SI','AT'],
  RO: ['HU','UA','MD','BG','RS'],
  RS: ['HU','RO','BG','MK','XK','ME','BA','HR'],
  HR: ['SI','HU','RS','BA','ME'],
  SI: ['IT','AT','HU','HR'],
  BA: ['HR','RS','ME'],
  ME: ['HR','BA','RS','XK','AL'],
  XK: ['RS','MK','AL','ME'],
  MK: ['XK','RS','BG','GR','AL'],
  AL: ['ME','XK','MK','GR'],
  BG: ['RO','RS','MK','GR','TR'],
  ZA: ['NA','BW','ZW','MZ','SZ','LS'],
  EG: ['LY','SD','IL'],
  KE: ['UG','TZ','ET','SO','SS'],
  NG: ['BJ','NE','TD','CM'],
  IL: ['LB','SY','JO','EG','PS'],
  // Add more as needed; falls back to random when no entry.
};

const flagEmoji = (cc2) => {
  if (!cc2 || cc2.length !== 2) return '';
  const A = 0x1F1E6;
  return String.fromCodePoint(...[...cc2.toUpperCase()].map(c => A + c.charCodeAt(0) - 65));
};

const escape = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const resolveImg = (path) => {
  if (!path) return path;
  if (/^https?:\/\//.test(path)) return path;
  try { return chrome.runtime.getURL(path); }
  catch (e) { return path; }
};

let TIPS = null;
const loadTips = async () => {
  if (TIPS) return TIPS;
  const url = chrome.runtime.getURL('data/tips.json');
  TIPS = await fetch(url).then(r => r.json());
  return TIPS;
};

// ---------- Leitner box state in chrome.storage.local ----------
const leitnerKey = (cc, idx) => `leitner:${cc}:${idx}`;
const getLeitner = async (keys) => {
  const all = await chrome.storage.local.get(keys);
  return all;
};
const setLeitner = async (key, state) => {
  await chrome.storage.local.set({ [key]: state });
};

// ---------- card pool ----------
async function buildPool(focus) {
  const tips = await loadTips();
  let allowed = null;
  if (focus !== 'all') allowed = new Set(REGION_GROUPS[focus] || []);

  const pool = [];
  for (const [cc, c] of Object.entries(tips)) {
    if (cc === '_meta') continue;
    if (allowed && !allowed.has(cc)) continue;
    const metas = c.metas || [];
    metas.forEach((m, i) => {
      const imgs = m.images || [];
      if (!imgs.length) return;
      pool.push({ cc, name: c.name, type: m.type, title: m.title, img: imgs[0],
                  description: m.description, comparison: m.comparison, idx: i });
    });
  }
  return pool;
}

function pickHardDistractors(correctCc, allCcs, n) {
  const neighbors = (NEIGHBORS[correctCc] || []).filter(cc => cc !== correctCc && allCcs.has(cc));
  const out = [];
  // Shuffle neighbors for variety.
  for (const cc of neighbors.sort(() => Math.random() - 0.5)) {
    if (out.length >= n) break;
    out.push(cc);
  }
  // Top up with random covered countries.
  const remaining = [...allCcs].filter(cc => cc !== correctCc && !out.includes(cc));
  for (const cc of remaining.sort(() => Math.random() - 0.5)) {
    if (out.length >= n) break;
    out.push(cc);
  }
  return out.slice(0, n);
}

function pickRandomDistractors(correctCc, allCcs, n) {
  return [...allCcs].filter(cc => cc !== correctCc).sort(() => Math.random() - 0.5).slice(0, n);
}

function chooseDistractors(mode, correctCc, allCcs, n) {
  if (mode === 'random') return pickRandomDistractors(correctCc, allCcs, n);
  if (mode === 'mixed') {
    const hard = pickHardDistractors(correctCc, allCcs, 1);
    const rand = pickRandomDistractors(correctCc, allCcs, n - hard.length).filter(cc => !hard.includes(cc));
    return [...hard, ...rand].slice(0, n);
  }
  return pickHardDistractors(correctCc, allCcs, n);
}

// ---------- session state ----------
const session = {
  pool: [],
  allCcs: new Set(),
  livesMax: 3,
  lives: 3,
  mc: 4,
  dist: 'hard',
  streak: 0,
  bestStreak: 0,
  correct: 0,
  total: 0,
  byCountry: {},
};

function pickCard() {
  // Weight: prefer cards in lower Leitner boxes (= less mastered).
  // For v1: random pick for simplicity. SRS weighting comes after we have
  // some data per card.
  const live = session.pool.filter(c => session.allCcs.has(c.cc));
  return live[Math.floor(Math.random() * live.length)];
}

async function presentCard(card) {
  const distractorCcs = chooseDistractors(session.dist, card.cc, session.allCcs, session.mc - 1);
  const choices = [card.cc, ...distractorCcs].sort(() => Math.random() - 0.5);
  const tips = await loadTips();

  const stage = $('stage');
  stage.innerHTML = `
    <div class="qcard">
      <div class="qmeta">${escape(card.type || 'Meta')}</div>
      <img class="qimg" src="${escape(resolveImg(card.img))}" alt="">
      <div class="qprompt">Which country?</div>
      <div class="qchoices">
        ${choices.map((cc, i) => `
          <button class="qchoice" data-cc="${cc}" data-idx="${i+1}">
            <span class="flag">${flagEmoji(cc)}</span>${escape(tips[cc]?.name || cc)}
            <span class="kbd" style="float:right">${i+1}</span>
          </button>
        `).join('')}
      </div>
      <div class="feedback" id="fb"></div>
      <div class="next-row" id="nextRow" style="display:none">
        <button class="primary" id="nextBtn">Next \u2192 <span class="kbd">space</span></button>
      </div>
    </div>
  `;

  const handleAnswer = async (chosenCc) => {
    const isRight = chosenCc === card.cc;
    session.total++;
    if (isRight) {
      session.correct++;
      session.streak++;
      if (session.streak > session.bestStreak) session.bestStreak = session.streak;
    } else {
      session.lives--;
      session.streak = 0;
    }
    session.byCountry[card.cc] = session.byCountry[card.cc] || { hit: 0, miss: 0 };
    if (isRight) session.byCountry[card.cc].hit++;
    else session.byCountry[card.cc].miss++;

    // Update Leitner state for this card.
    const lk = leitnerKey(card.cc, card.idx);
    const stored = (await getLeitner([lk]))[lk] || { box: 1, lastSeen: 0 };
    if (isRight) stored.box = Math.min(5, stored.box + 1);
    else stored.box = 1;
    stored.lastSeen = Date.now();
    await setLeitner(lk, stored);

    document.querySelectorAll('.qchoice').forEach(btn => {
      btn.disabled = true;
      if (btn.dataset.cc === card.cc) btn.classList.add('correct');
      else if (btn.dataset.cc === chosenCc) btn.classList.add('wrong');
    });
    const fb = $('fb');
    fb.classList.add('shown', isRight ? 'correct' : 'wrong');
    fb.innerHTML = `
      <strong>${isRight ? 'Right' : 'Wrong'} \u2014 ${escape(tips[card.cc]?.name || card.cc)}</strong><br>
      ${escape(card.description || '')}
      ${card.comparison ? `<br><em>vs:</em> ${escape(card.comparison)}` : ''}
    `;
    $('nextRow').style.display = '';
    updateTopbar();
  };

  document.querySelectorAll('.qchoice').forEach(btn => {
    btn.addEventListener('click', () => handleAnswer(btn.dataset.cc));
  });
  $('nextBtn').addEventListener('click', advance);

  // Number-key shortcuts for choices, space for next.
  document.onkeydown = (e) => {
    if (e.key >= '1' && e.key <= '8') {
      const btn = document.querySelector(`.qchoice[data-idx="${e.key}"]:not(:disabled)`);
      if (btn) btn.click();
    } else if (e.key === ' ' || e.key === 'Enter') {
      const next = document.getElementById('nextBtn');
      if (next) { e.preventDefault(); next.click(); }
    }
  };
}

function updateTopbar() {
  $('lives').textContent = '\u2764'.repeat(Math.max(0, session.lives))
                         + '\u2661'.repeat(Math.max(0, session.livesMax - session.lives));
  $('streak').textContent = session.streak;
  $('acc').textContent = session.total
    ? `${Math.round(session.correct / session.total * 100)}% (${session.correct}/${session.total})`
    : '\u2014';
}

function advance() {
  if (session.lives <= 0) return endSession();
  presentCard(pickCard());
}

function endSession() {
  document.onkeydown = null;
  const acc = session.total ? Math.round(session.correct / session.total * 100) : 0;
  $('stage').innerHTML = `
    <div class="qcard gameover">
      <h1>Session over</h1>
      <div class="stats">
        <span>${session.correct}</span> right of <span>${session.total}</span> &middot;
        accuracy <span>${acc}%</span> &middot;
        best streak <span>${session.bestStreak}</span>
      </div>
      <div class="stats">
        Worst countries: ${Object.entries(session.byCountry)
          .filter(([, v]) => v.hit + v.miss >= 2)
          .sort((a, b) => (b[1].miss/(b[1].hit+b[1].miss)) - (a[1].miss/(a[1].hit+a[1].miss)))
          .slice(0, 6)
          .map(([cc, v]) => `<span>${flagEmoji(cc)} ${cc} ${v.miss}/${v.hit+v.miss}</span>`).join(' ')}
      </div>
      <div class="actions">
        <button class="primary" id="restartBtn">Play again</button>
      </div>
    </div>
  `;
  $('restartBtn').addEventListener('click', () => location.reload());
}

async function start() {
  session.livesMax = +$('livesInput').value || 3;
  session.lives = session.livesMax;
  session.mc = +$('mcInput').value || 4;
  session.dist = $('distInput').value || 'hard';
  session.streak = 0;
  session.correct = 0;
  session.total = 0;
  session.bestStreak = 0;
  session.byCountry = {};

  const focus = $('focus').value || 'all';
  session.pool = await buildPool(focus);
  session.allCcs = new Set(session.pool.map(c => c.cc));

  if (session.pool.length === 0) {
    alert('No cards in this focus. Pick another filter.');
    return;
  }

  updateTopbar();
  presentCard(pickCard());
}

document.addEventListener('DOMContentLoaded', () => {
  $('startBtn').addEventListener('click', start);
  $('quitBtn').addEventListener('click', () => location.reload());
  $('settingsBtn').addEventListener('click', () => location.reload());
});
