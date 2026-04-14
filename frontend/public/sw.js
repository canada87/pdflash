/**
 * pdflash Service Worker — CacheFirst for all /cache/* assets.
 *
 * Every asset under /cache/ uses a content-hash path (SHA-256 of the PDF),
 * so URLs are effectively immutable.  Cache forever, never revalidate.
 */

const CACHE = 'pdflash-v1';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (e) => {
  // Delete any caches from older SW versions.
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const { request } = e;
  const url = new URL(request.url);

  // Only intercept GET requests under /cache/
  if (request.method !== 'GET' || !url.pathname.startsWith('/cache/')) return;

  e.respondWith(
    caches.open(CACHE).then((cache) =>
      cache.match(request).then((cached) => {
        if (cached) return cached;
        return fetch(request).then((res) => {
          // Only cache successful responses
          if (res.ok) cache.put(request, res.clone());
          return res;
        });
      })
    )
  );
});
