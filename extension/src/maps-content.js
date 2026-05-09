// Slim content script for Google Maps. The user often clicks the result-page
// flag in GeoGuessr after a round, which jumps them to google.com/maps at
// the actual location. This script loads the overlay so the chip+popup can
// re-appear there using the cached round data persisted by overlay.js.

const log = (...a) => console.log('[plonker/maps]', ...a);

(async () => {
  // Bail out if we already loaded (URL changes can re-trigger).
  if (window.__plonkerMapsLoaded) return;
  window.__plonkerMapsLoaded = true;

  const cssHref = chrome.runtime.getURL('src/overlay/overlay.css');
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = cssHref;
  (document.head || document.documentElement).appendChild(link);

  // overlay.js auto-bootstraps the chip on Google Maps by reading the cached
  // round from chrome.storage.local — see the bottom of overlay.js.
  const jsSrc = chrome.runtime.getURL('src/overlay/overlay.js');
  await import(jsSrc);

  log('overlay loaded on Google Maps');
})();
