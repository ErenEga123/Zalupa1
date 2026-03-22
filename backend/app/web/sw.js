const CACHE_NAME = 'reader-system-v2';
const APP_SHELL = ['/app', '/app/styles.css', '/app/app.js', '/manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => cached);
  return cached || fetchPromise;
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith('/api/v1/books/') && url.pathname.includes('/chapter/')) {
    event.respondWith(staleWhileRevalidate(event.request));
    return;
  }
  if (url.pathname === '/app' || url.pathname.startsWith('/app/') || url.pathname === '/manifest.webmanifest') {
    event.respondWith(staleWhileRevalidate(event.request));
  }
});
