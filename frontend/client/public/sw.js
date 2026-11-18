const SHELL_CACHE = 'kawastock-shell-v1';

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    const response = await fetch('/index.html', { cache: 'reload' });
    if (!response.ok) throw new Error(`Unable to precache the KawaStock shell (${response.status}).`);

    const html = await response.clone().text();
    await cache.put('/index.html', response);
    const assetPaths = [
      ...Array.from(html.matchAll(/(?:src|href)=["']([^"']+)["']/g), match => match[1])
        .filter(path => path.startsWith('/assets/')),
      '/kawastock-mark.svg',
      '/kawastock-shop-unsplash.jpg',
      '/manifest.webmanifest',
    ];

    await Promise.all(assetPaths.map(async path => {
      const asset = await fetch(path, { cache: 'reload' });
      if (!asset.ok) throw new Error(`Unable to precache ${path} (${asset.status}).`);
      await cache.put(path, asset);
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames
      .filter(name => name.startsWith('kawastock-shell-') && name !== SHELL_CACHE)
      .map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  if (
    request.method !== 'GET' ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/api/v1/') ||
    url.pathname.startsWith('/media/') ||
    url.pathname.startsWith('/__manus__/')
  ) return;

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (response.ok) {
          const cache = await caches.open(SHELL_CACHE);
          await cache.put('/index.html', response.clone());
          return response;
        }
      } catch {
        // Fall through to the cached application shell.
      }
      return await caches.match('/index.html') ||
        new Response('KawaStock is unavailable offline until it has been opened once online.', {
          status: 503,
          headers: { 'Content-Type': 'text/plain; charset=utf-8' },
        });
    })());
    return;
  }

  event.respondWith((async () => {
    const cached = await caches.match(request);
    if (cached) return cached;

    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(SHELL_CACHE);
      await cache.put(request, response.clone());
    }
    return response;
  })());
});
