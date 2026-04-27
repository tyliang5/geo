// Runs in MAIN world at document_start. Snoops GeoGuessr's own API responses
// (game state, round result, lat/lng, country) without re-authenticating.
// Defends against GG re-wrapping fetch by:
//   1) Object.defineProperty + non-configurable
//   2) XHR fallback (GG sometimes uses XHR via axios for game APIs)
//   3) Periodic re-patch as belt-and-suspenders
// Strategy adapted from miraclewhips/geoguessr-event-framework.

(() => {
  if (window.__plonkerInstalled) return;
  window.__plonkerInstalled = true;
  const log = (...a) => console.log('[plonker/inject]', ...a);

  const send = (type, payload) => {
    window.postMessage({ source: 'plonker', type, payload }, '*');
  };

  const state = {
    currentGameId: null,
    currentRound: 0
  };

  const summarizeRound = (data) => {
    const idx = (data.round || 1) - 1;
    const r = (data.rounds || [])[idx] ?? {};
    const guesses = data.player?.guesses ?? [];
    const g = guesses[idx] ?? null;
    return {
      gameId: data.token,
      gameType: data.type,
      gameMode: data.mode,
      mapId: data.map,
      mapName: data.mapName,
      forbidMoving: !!data.forbidMoving,
      forbidPanning: !!data.forbidRotating,
      forbidZooming: !!data.forbidZooming,
      timeLimit: data.timeLimit,
      roundIndex: idx,
      actual: {
        lat: r.lat,
        lng: r.lng,
        panoId: r.panoId,
        heading: r.heading,
        pitch: r.pitch,
        zoom: r.zoom,
        countryCode: r.streakLocationCode || null
      },
      guess: g && g.lat != null ? {
        lat: g.lat,
        lng: g.lng,
        countryCode: g.streakLocationCode || null,
        roundScore: g.roundScoreInPoints ?? g.roundScore?.amount,
        distance: g.distanceInMeters ?? g.distance?.meters?.amount
      } : null
    };
  };

  const handleClassicGame = (data) => {
    if (!data || !data.token || !Array.isArray(data.rounds)) return;
    const guesses = data.player?.guesses ?? [];
    const roundJustEnded = guesses.length === data.round;
    const newGame = data.token !== state.currentGameId || data.round !== state.currentRound;

    if (roundJustEnded) {
      state.currentGameId = data.token;
      state.currentRound = data.round;
      log('round_end', data.token, 'r', data.round);
      send('round_end', summarizeRound(data));
    } else if (newGame) {
      state.currentGameId = data.token;
      state.currentRound = data.round;
      log('round_start', data.token, 'r', data.round);
      send('round_start', summarizeRound(data));
    }
  };

  const isInteresting = (url) => {
    if (typeof url !== 'string') return false;
    return url.includes('/api/v3/games/') || url.includes('/api/v3/challenges/');
  };

  // ---- fetch patch ----
  const realFetch = window.fetch.bind(window);
  const plonkerFetch = async function(...args) {
    const res = await realFetch(...args);
    try {
      const url = typeof args[0] === 'string' ? args[0] : args[0]?.url ?? '';
      if (isInteresting(url)) {
        res.clone().json().then(handleClassicGame).catch(() => {});
      }
    } catch (e) { /* swallow */ }
    return res;
  };
  plonkerFetch.__plonker = true;

  const installFetch = () => {
    try {
      Object.defineProperty(window, 'fetch', {
        configurable: false,
        writable: false,
        enumerable: true,
        value: plonkerFetch
      });
      return 'defineProperty';
    } catch (e) {
      try { window.fetch = plonkerFetch; return 'assign'; } catch (e2) { return 'failed'; }
    }
  };
  log('fetch install:', installFetch());
  // Belt-and-suspenders: if GG manages to swap fetch via setter on Window.prototype etc.,
  // re-check periodically and re-install via direct assignment if needed.
  let watchdogTicks = 0;
  const watchdog = setInterval(() => {
    watchdogTicks++;
    if (window.fetch !== plonkerFetch && !window.fetch?.__plonker) {
      try { window.fetch = plonkerFetch; log('re-patched fetch on tick', watchdogTicks); } catch (e) {}
    }
    if (watchdogTicks > 60) clearInterval(watchdog); // ~30s of monitoring after load
  }, 500);

  // ---- XHR patch (axios fallback) ----
  const realOpen = XMLHttpRequest.prototype.open;
  const realSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.__plonkerUrl = url;
    return realOpen.call(this, method, url, ...rest);
  };
  XMLHttpRequest.prototype.send = function(...args) {
    if (isInteresting(this.__plonkerUrl)) {
      this.addEventListener('load', () => {
        try {
          const data = JSON.parse(this.responseText);
          handleClassicGame(data);
        } catch (e) { /* swallow */ }
      });
    }
    return realSend.apply(this, args);
  };

  // ---- initial NEXT_DATA snapshot (challenge / game pages render with state inline) ----
  try {
    const nd = document.getElementById('__NEXT_DATA__');
    if (nd) {
      const d = JSON.parse(nd.textContent);
      const snap = d?.props?.pageProps?.gameSnapshot ?? d?.props?.pageProps?.game;
      if (snap) handleClassicGame(snap);
    }
  } catch (e) { /* swallow */ }

  send('inject_ready', { v: '0.1.1' });
  log('inject ready');
})();
