const CACHE_NAME = 'keyhub-cache-v1';
const urlsToCache = [
  '/static/logo.png',
  // Add your Bootstrap CSS link here if you want it offline, 
  // otherwise the app will look unstyled when offline.
  // Note: External CDNs (jsdelivr) require different caching logic. 
  // For simplicity, we cache the manifest and offline fallback if you have one.
  '/static/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

// "Network First" Strategy
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request)
      .then(networkResponse => {
        // If we get a valid response from the network, cache it for next time
        if(networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
        }
        return networkResponse;
      })
      .catch(() => {
        // If network fails (offline), look in the cache
        return caches.match(event.request);
      })
  );
});