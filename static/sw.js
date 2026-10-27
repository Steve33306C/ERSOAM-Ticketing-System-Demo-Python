// ---------- Service worker: ERS O&M technician app (PWA, 13 Okt) ----------
//
// Deliberately conservative. This prototype's pages, CSS and JS change often,
// and the server is the only source of truth for ticket data, so:
//
//   * /api/*         -> NEVER touched here. Always goes straight to the
//                       network, so a technician can never be shown a stale
//                       ticket status out of a cache.
//   * Page loads     -> network first. Only if the network fails does the
//                       user get offline.html (instead of the browser's own
//                       error screen). Pages themselves are not cached.
//   * CSS/JS/icons   -> network first, cached copy used only as a fallback
//                       (so offline.html and the app shell can still style
//                       themselves). Every online load gets the latest file,
//                       so code updates reach users immediately.
//
// Bump CACHE_VERSION whenever this file or the PRECACHE list changes. The
// new worker then waits, and the app shows a "new version" banner (see
// initTechnicianPwa() in shared.js) instead of switching mid-task.

const CACHE_VERSION = "ers-om-v1";

const PRECACHE = [
  "offline.html",
  "style.css",
  "shared.js",
  "icons/icon-192.png",
  "icons/icon-512.png",
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_VERSION).then(cache => cache.addAll(PRECACHE)));
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE_VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Sent by the "Reload" button on the update banner.
self.addEventListener("message", event => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.includes("/api/")) return; // live data: never cached

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("offline.html"))
    );
    return;
  }

  if (/\.(css|js|png|svg|json)$/.test(url.pathname)) {
    event.respondWith(
      fetch(req)
        .then(res => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE_VERSION).then(cache => cache.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req))
    );
  }
});
