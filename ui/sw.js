// HackKnow AI OS — service worker (offline shell + cache-first for static assets)
const CACHE = "hackknow-v1";
const SHELL = ["/", "/manifest.webmanifest"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ).then(() => self.clients.claim()));
});

self.addEventListener("fetch", event => {
  const u = new URL(event.request.url);
  // API: always go network, never cache
  if (u.pathname.startsWith("/execute") || u.pathname.startsWith("/agents") ||
      u.pathname.startsWith("/keys") || u.pathname.startsWith("/meter") ||
      u.pathname.startsWith("/finetune") || u.pathname.startsWith("/workflows") ||
      u.pathname.startsWith("/browser") || u.pathname.startsWith("/automations") ||
      u.pathname.startsWith("/skills") || u.pathname.startsWith("/repos") ||
      u.pathname.startsWith("/voice") || u.pathname.startsWith("/healthcheck")) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then(hit => hit || fetch(event.request).then(resp => {
      const copy = resp.clone();
      caches.open(CACHE).then(c => c.put(event.request, copy));
      return resp;
    })).catch(() => caches.match("/"))
  );
});
