// Application installable (Android : Chrome → Installer l'application). La page s'ouvre même hors connexion
// (dernière version gardée). Les données du robot sont toujours lues en direct quand le réseau répond ; les vidéos et les
// appels à GitHub ne sont jamais gardés.
const CACHE = "regie-gilbert-v1";
const COQUILLE = ["./", "manifest.webmanifest", "logo-192.png", "logo-512.png", "logo-apple.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(COQUILLE))); self.skipWaiting(); });
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(k => Promise.all(k.filter(x => x !== CACHE).map(x => caches.delete(x)))));
  self.clients.claim();
});
const garder = (req, r) => { if (r && r.ok) { const c = r.clone(); caches.open(CACHE).then(x => x.put(req, c)); } return r; };
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.endsWith(".mp4")) return;
  if (e.request.mode === "navigate" || u.pathname.endsWith("/") || u.pathname.endsWith(".html") || u.pathname.includes("/donnees/")) {
    // page et données : la version la plus récente si le réseau répond en moins de 3 s, sinon la copie gardée
    const cle = u.pathname.includes("/donnees/") ? u.origin + u.pathname : e.request;     // (sans le ?t=… anti-cache)
    e.respondWith(new Promise(ok => {
      let fini = false;
      const copie = () => caches.match(cle).then(r => r || caches.match("./"));
      const minuteur = setTimeout(() => copie().then(r => { if (r && !fini) { fini = true; ok(r); } }), 3000);
      fetch(e.request).then(r => { garder(cle, r); if (!fini) { fini = true; clearTimeout(minuteur); ok(r); } })
        .catch(() => copie().then(r => { if (!fini) { fini = true; clearTimeout(minuteur); ok(r || Response.error()); } }));
    }));
    return;
  }
  // icônes, miniatures : copie gardée tout de suite, mise à jour en arrière-plan
  e.respondWith(caches.match(e.request).then(c => { const f = fetch(e.request).then(r => garder(e.request, r)).catch(() => c); return c || f; }));
});
