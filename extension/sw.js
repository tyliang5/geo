// Service worker for the Plonker PWA. Two goals:
//   1. Make the app installable + work offline (cache the static shell).
//   2. Auto-update — when we deploy a new version of any cached file, the
//      next launch fetches the new file and the user gets the update.
//
// Strategy:
//   - Pre-cache the app shell (HTML/CSS/JS/topics) at install.
//   - On fetch:
//       * Same-origin requests → "stale-while-revalidate" (serve cached
//         immediately, refresh from network in background, swap on next
//         load). This is the auto-update path: zero user action needed.
//       * Cross-origin (flagcdn, learnablemeta, supabase, nominatim) →
//         pass through to the network. We don't cache these because they
//         are huge in aggregate and we'd thrash the cache.
//   - On activate, sweep old versioned caches.
//
// Bump CACHE_VERSION whenever you ship breaking changes you want to force
// users onto immediately. For most edits the stale-while-revalidate path
// already updates within one launch, so version bumps are rarely needed.

const CACHE_VERSION = 'plonker-v1';
const SHELL = [
  './',
  './app.html',
  './app.css',
  './app.js',
  './topics.js',
  './app.webmanifest',
  // Data files — large but small enough to bundle so the app works fully offline.
  './data/tips.json',
  './data/countries.geojson',
  './data/admin1.geojson',
  './data/subregion_polygons.json',
  './data/country_facts.json',
  './data/country_reference.json',
  './data/us_area_codes.json',
  './data/us_area_code_notes.json',
  './data/country_area_codes.json',
  './data/compendium_quizzes.json',
  './data/meta_extras.json',
  './data/giveaway_blacklist.json',
  './data/plonkit_covered.json',
  './data/geographic_aliases.json',
  './data/mask_boxes.json',
  // Icons referenced by the manifest
  './assets/icon-192.png',
  './assets/icon-512.png',
  './assets/icon-180.png',
  './assets/icon-128.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) =>
      // addAll fails the whole install if ANY URL 404s. Use individual put()
      // so missing optional files don't break install (e.g. some data files
      // are auto-generated in dev and may be absent on first deploy).
      Promise.all(SHELL.map((url) =>
        fetch(url, { cache: 'no-cache' })
          .then((r) => r.ok ? cache.put(url, r) : null)
          .catch(() => null)
      ))
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Only handle GETs; let POSTs (e.g., supabase round-import) go straight through.
  if (event.request.method !== 'GET') return;
  // Cross-origin requests: pass through, don't cache.
  if (url.origin !== self.location.origin) return;
  // Stale-while-revalidate for same-origin assets.
  event.respondWith(
    caches.open(CACHE_VERSION).then((cache) =>
      cache.match(event.request).then((cached) => {
        const networkFetch = fetch(event.request)
          .then((resp) => {
            if (resp && resp.ok) cache.put(event.request, resp.clone());
            return resp;
          })
          .catch(() => cached);  // offline: fall back to cache if any
        return cached || networkFetch;
      })
    )
  );
});
