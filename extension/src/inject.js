// Runs in the MAIN world on geoguessr.com from document_start.
// Monkey-patches window.fetch so we can snoop GeoGuessr's own API responses
// (game state, round result, lat/lng, country code) without re-authenticating.
// Strategy borrowed from miraclewhips/geoguessr-event-framework — proven for ~3 years.

(() => {
  if (window.__plonkerInstalled) return;
  window.__plonkerInstalled = true;

  const send = (type, payload) => {
    window.postMessage({ source: 'plonker', type, payload }, '*');
  };

  const state = {
    currentGameId: null,
    currentRound: 0,
    lastSnapshot: null
  };

  const handleClassicGame = (data) => {
    if (!data || !data.token || !Array.isArray(data.rounds)) return;
    const guesses = data.player?.guesses ?? [];
    const roundJustEnded = guesses.length === data.round;
    const newGame = data.token !== state.currentGameId || data.round !== state.currentRound;

    if (newGame && !roundJustEnded) {
      state.currentGameId = data.token;
      state.currentRound = data.round;
      send('round_start', summarizeRound(data));
    }

    if (roundJustEnded) {
      state.currentGameId = data.token;
      state.currentRound = data.round;
      send('round_end', summarizeRound(data));
    }

    state.lastSnapshot = data;
  };

  const summarizeRound = (data) => {
    const idx = data.round - 1;
    const r = data.rounds[idx] ?? {};
    const g = (data.player?.guesses ?? [])[idx] ?? {};
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
      guess: g.lat != null ? {
        lat: g.lat,
        lng: g.lng,
        countryCode: g.streakLocationCode || null,
        roundScore: g.roundScoreInPoints ?? g.roundScore?.amount,
        distance: g.distanceInMeters ?? g.distance?.meters?.amount
      } : null
    };
  };

  const origFetch = window.fetch;
  window.fetch = async function(...args) {
    const res = await origFetch.apply(this, args);
    try {
      const url = typeof args[0] === 'string' ? args[0] : args[0]?.url ?? '';
      if (url.includes('/api/v3/games/') || url.includes('/api/v3/challenges/')) {
        const clone = res.clone();
        clone.json().then(handleClassicGame).catch(() => {});
      }
    } catch (e) { /* swallow */ }
    return res;
  };

  // On initial challenge page load the data is in __NEXT_DATA__.
  try {
    const nd = document.getElementById('__NEXT_DATA__');
    if (nd) {
      const d = JSON.parse(nd.textContent);
      const snap = d?.props?.pageProps?.gameSnapshot ?? d?.props?.pageProps?.game;
      if (snap) handleClassicGame(snap);
    }
  } catch (e) { /* swallow */ }

  send('inject_ready', { v: '0.1.0' });
})();
