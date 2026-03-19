const CACHE_NAME = 'observa-pe-v6';
const API_CACHE = 'observa-pe-api-v1';
const ASSETS = [
  '/',
  '/manifest.json',
  '/icon.svg',
  '/sw.js',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      for (const asset of ASSETS) {
        try {
          await cache.add(asset);
        } catch (_) {
          // Ignora falhas de um asset isolado para nao quebrar a instalacao do SW.
        }
      }
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys
        .filter((key) => key !== CACHE_NAME && key !== API_CACHE)
        .map((key) => caches.delete(key))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const reqUrl = new URL(event.request.url);
  const isNavigation = event.request.mode === 'navigate';

  // Navegacao prioriza cache para abrir rapido e atualiza em background.
  if (isNavigation) {
    event.respondWith(
      caches.match('/').then((cached) => {
        const networkFetch = fetch(event.request)
          .then((response) => {
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put('/', copy));
            return response;
          })
          .catch(() => cached || caches.match(event.request));

        if (cached) {
          event.waitUntil(networkFetch);
          return cached;
        }

        return networkFetch;
      })
    );
    return;
  }

  if (reqUrl.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(API_CACHE).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match('/'));
    })
  );
});
