// Isolated-world content script. Bridges page-world events from inject.js
// to the background service worker, and injects the post-round overlay UI.

const log = (...a) => console.log('[plonker]', ...a);

let overlayLoaded = false;

const ensureOverlay = async () => {
  if (overlayLoaded) return;
  overlayLoaded = true;
  const cssHref = chrome.runtime.getURL('src/overlay/overlay.css');
  const jsSrc = chrome.runtime.getURL('src/overlay/overlay.js');
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = cssHref;
  (document.head || document.documentElement).appendChild(link);
  await import(jsSrc);
};

window.addEventListener('message', async (e) => {
  if (e.source !== window) return;
  const msg = e.data;
  if (!msg || msg.source !== 'plonker') return;

  if (msg.type === 'inject_ready') {
    log('inject ready');
    return;
  }

  if (msg.type === 'round_end') {
    await ensureOverlay();
    chrome.runtime.sendMessage({ type: 'round_end', payload: msg.payload }, (resp) => {
      // chrome.runtime.lastError is set if the SW dropped/errored. Log it
      // for debugging but still dispatch the event with whatever we got
      // (or null) so the overlay at least renders something.
      if (chrome.runtime.lastError) {
        console.warn('[plonker] background round_end error:', chrome.runtime.lastError.message);
      }
      window.dispatchEvent(new CustomEvent('plonker:round-end', {
        detail: { round: msg.payload, server: resp || null }
      }));
    });
  } else if (msg.type === 'round_start') {
    // Auto-dismiss the previous round's overlay so it doesn't sit on top of the new pano.
    window.dispatchEvent(new CustomEvent('plonker:round-start', { detail: msg.payload }));
    chrome.runtime.sendMessage({ type: 'round_start', payload: msg.payload });
  }
});

log('content script loaded');
