/* Leafline service worker: the newest published files always win when online; cached copies keep the app opening offline. */
const V = "leafline-11.3.0-32cdd5f6";
const CORE = ["./", "index.html", "engine.js", "config.js", "manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(V).then((c) => Promise.all(CORE.map((u) => fetch(new Request(u, { cache: "reload" })).then((r) => (r.ok ? c.put(u, r) : null)).catch(() => null)))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin || u.pathname.endsWith("/version.json")) return;   // database calls and the version check go straight to the network
  e.respondWith((async () => {
    try {
      const res = await fetch(r, { cache: "no-cache" });
      if (res.ok) { const c = await caches.open(V); c.put(r, res.clone()); }
      return res;
    } catch (err) {
      const hit = await caches.match(r, { ignoreSearch: true });
      if (hit) return hit;
      if (r.mode === "navigate") { const idx = await caches.match("index.html"); if (idx) return idx; }
      throw err;
    }
  })());
});
