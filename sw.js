/**
 * Service Worker for daily-arXiv-ai-enhanced
 *
 * Strategy:
 * - Navigation requests (HTML): network-first with `cache: 'no-cache'`
 *   → always revalidates with server, bypassing stale HTTP cache (max-age=600)
 * - Static assets (JS/CSS/images): stale-while-revalidate
 *   → serves from cache instantly, updates in background
 * - Cross-origin (data files, CDNs): pass-through (browser default)
 *
 * Bump CACHE_VERSION when deploying breaking changes to force SW update.
 */

const CACHE_VERSION = 'arxiv-daily-v3';
const CACHE_NAME = CACHE_VERSION;

// --- Install: skip waiting so new SW activates immediately ---
self.addEventListener('install', (event) => {
    self.skipWaiting();
});

// --- Activate: claim all clients + purge old caches ---
self.addEventListener('activate', (event) => {
    event.waitUntil(
        Promise.all([
            // Delete old cache versions
            caches.keys().then((keys) =>
                Promise.all(
                    keys
                        .filter((k) => k !== CACHE_NAME)
                        .map((k) => caches.delete(k))
                )
            ),
            // Take control of all open tabs immediately
            self.clients.claim(),
        ])
    );
});

// --- Fetch: route requests by type ---
self.addEventListener('fetch', (event) => {
    const request = event.request;

    // Only intercept GET requests
    if (request.method !== 'GET') return;

    // 1) Navigation requests (HTML pages) — network-first, always fresh
    if (request.mode === 'navigate') {
        event.respondWith(
            fetch(request, { cache: 'no-cache' })
                .then((response) => {
                    // Cache a copy for offline fallback
                    const copy = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
                    return response;
                })
                .catch(() =>
                    // Offline: serve cached HTML
                    caches.match(request).then((r) => r || caches.match('/'))
                )
        );
        return;
    }

    // 2) Same-origin static assets — stale-while-revalidate
    const url = new URL(request.url);
    if (url.origin === self.location.origin) {
        event.respondWith(
            caches.match(request).then((cached) => {
                const fetchPromise = fetch(request)
                    .then((response) => {
                        // Only cache valid responses
                        if (response.ok || response.type === 'opaque') {
                            const copy = response.clone();
                            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
                        }
                        return response;
                    })
                    .catch(() => cached);
                return cached || fetchPromise;
            })
        );
        return;
    }

    // 3) Cross-origin requests (raw.githubusercontent.com data, CDNs) — pass through
    //    Don't intercept; let browser handle with its default caching.
    //    Data files change daily and are fetched via XHR/fetch() in app.js.
});
