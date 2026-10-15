/* ProjectXY agent service worker.
 *
 * Two jobs:
 *   1. Cache the agent shell so it opens even with no network.
 *   2. Attempt a background heartbeat via Periodic Background Sync where the
 *      browser supports it (Chrome/Android for installed PWAs). This is
 *      best-effort: iOS does not support it, and even on Android the browser
 *      decides the cadence. The in-page 60s timer remains the primary loop
 *      while the app is open; this just helps while it's backgrounded.
 *
 * The SW holds no secret. It reads the device id + secret from where the page
 * stored them. localStorage is not available in a SW, so the page mirrors the
 * credential into a cache entry the SW can read (see writeCreds in the page is
 * NOT used; instead we post it to the SW on register). To keep this simple and
 * dependency-free, the SW asks the page for current creds via postMessage when
 * it needs them, and falls back silently if the page isn't open.
 */

const SHELL_CACHE = 'pxy-agent-shell-v1';
const SHELL_URLS = ['/agent'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((c) => c.addAll(SHELL_URLS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Serve the shell from cache when offline.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.mode === 'navigate' && url.pathname.startsWith('/agent')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('/agent'))
    );
  }
});

// The page posts its credentials here after enrollment so the SW can heartbeat
// while backgrounded.
let creds = null; // { deviceId, secret }
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'pxy-creds') {
    creds = event.data.creds; // may be null on disconnect
  }
});

async function doHeartbeat() {
  if (!creds || !creds.deviceId || !creds.secret) return;
  try {
    await fetch(`/api/v1/sensor/${creds.deviceId}/heartbeat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${creds.secret}` },
      body: JSON.stringify({ status: 'online' }),
    });
  } catch (_) {
    // offline; the next sync or the in-page timer will retry
  }
}

// Periodic Background Sync (Chrome/Android, installed PWA only).
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'pxy-heartbeat') {
    event.waitUntil(doHeartbeat());
  }
});