const CACHE_NAME = "kafkaf-shell-v2";
const APP_SHELL = ["/", "/static/style.css", "/static/app.js", "/static/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Only cache GETs — /chat, /audit, etc. are POSTs or always-fresh reads
  // and must never be served stale from the cache.
  if (event.request.method !== "GET") return;
  // Network-first, cache as a fallback for offline use only. The previous
  // cache-first strategy meant that once "/", app.js, and style.css were
  // cached on a user's very first visit, every later update this app ever
  // shipped was invisible to them forever — the browser never asked the
  // network for those files again. Always try the network; only serve the
  // cached copy when the network request itself fails.
  //
  // "cache: no-store" on this inner fetch is required, not optional: without
  // it, the browser's own ordinary HTTP cache can still transparently return
  // a stale response for this exact URL (no network round trip at all, so
  // this handler thinks it "fetched fresh" when it didn't) — a real failure
  // mode found via live testing, not a hypothetical one.
  event.respondWith(
    fetch(event.request, { cache: "no-store" })
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
