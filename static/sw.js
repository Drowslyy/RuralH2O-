// ============================================================
//  RuralH2O — Service Worker  (Iteración 5 — v4)
//  Cambio clave: install resiliente — cada URL se cachea por
//  separado con try/catch. Un fallo en Leaflet CDN no arruina
//  el caché de campo.html / login.html / etc.
// ============================================================

const CACHE_NAME = "ruralh2o-v6";

const STATIC_URLS = [
  "/view/campo.html",
  "/view/mediciones.html",
  "/view/index.html",
  "/view/login.html",
  "/view/manifest.json",
  "/view/icon-192.png",
  "/view/icon-512.png",
];

const EXTERNAL_URLS = [
  "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
  "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
];

// Cachea una URL individualmente — nunca lanza excepción
async function cacheUrl(cache, url, opts = {}) {
  try {
    const res = await fetch(url, opts);
    if (res && res.status === 200) await cache.put(url, res);
  } catch (_) {}
}

// ── INSTALL ──────────────────────────────────────────────────
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      // Archivos propios: cachear uno a uno (resiliente)
      await Promise.all(STATIC_URLS.map((url) => cacheUrl(cache, url)));
      // Leaflet CDN: igual, sin bloquear si falla
      await Promise.all(EXTERNAL_URLS.map((url) =>
        cacheUrl(cache, url, { mode: "cors" })
      ));
    })
  );
  self.skipWaiting(); // Activar inmediatamente sin esperar que se cierren tabs
});

// ── ACTIVATE ─────────────────────────────────────────────────
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim(); // Tomar control de todas las tabs abiertas
});

// ── FETCH ─────────────────────────────────────────────────────
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  const esPropio   = url.origin === self.location.origin;
  const esLeaflet  = url.hostname === "unpkg.com";
  const esTile     = url.hostname.endsWith(".tile.openstreetmap.org");
  const esStatic   = esPropio && url.pathname.startsWith("/view/");
  const esApiGet   = esPropio && !esStatic && e.request.method === "GET";

  // ── /view/* propios: Cache-first + actualización background ─
  if (esStatic) {
    e.respondWith(
      caches.match(e.request).then(async (cached) => {
        // Actualizar en background (stale-while-revalidate)
        fetch(e.request).then((res) => {
          if (res && res.status === 200)
            caches.open(CACHE_NAME).then((c) => c.put(e.request, res.clone()));
        }).catch(() => {});

        if (cached) return cached;

        // No está en caché → intentar red
        try {
          const res = await fetch(e.request);
          if (res && res.status === 200)
            caches.open(CACHE_NAME).then((c) => c.put(e.request, res.clone()));
          return res;
        } catch (_) {
          // Sin red y sin caché → fallback de navegación a la página pedida.
          // Si pedía index.html devolvemos index; si no, campo.html.
          if (e.request.mode === "navigate") {
            const pedirIndex = url.pathname.includes("index.html");
            const fallback = pedirIndex ? "/view/index.html" : "/view/campo.html";
            return (await caches.match(fallback)) || (await caches.match("/view/campo.html"));
          }
        }
      })
    );
    return;
  }

  // ── Leaflet CSS/JS ───────────────────────────────────────────
  if (esLeaflet) {
    e.respondWith(
      caches.match(e.request).then((cached) => {
        if (cached) return cached;
        return fetch(e.request, { mode: "cors" }).then((res) => {
          if (res && res.status === 200)
            caches.open(CACHE_NAME).then((c) => c.put(e.request, res.clone()));
          return res;
        }).catch(() => cached);
      })
    );
    return;
  }

  // ── Tiles OpenStreetMap: Cache-first con URL normalizada ────
  // Normalizamos a→a (a/b/c subdomains → siempre "a") para que
  // los tiles pre-cacheados coincidan con cualquier subdomain que pida Leaflet.
  if (esTile) {
    const tileUrl = e.request.url.replace(
      /^https?:\/\/[abc]\.tile\.openstreetmap\.org/,
      "https://a.tile.openstreetmap.org"
    );
    const canonReq = tileUrl === e.request.url
      ? e.request
      : new Request(tileUrl);
    e.respondWith(
      caches.match(canonReq).then((cached) => {
        if (cached) return cached;
        return fetch(e.request).then((res) => {
          if (res && res.status === 200)
            caches.open(CACHE_NAME).then((c) => c.put(canonReq, res.clone()));
          return res;
        }).catch(() => { /* Sin tile offline: Leaflet muestra cuadro gris */ });
      })
    );
    return;
  }

  // ── API GETs: Network-first con fallback a caché ────────────
  if (esApiGet) {
    e.respondWith(
      fetch(e.request).then((res) => {
        if (res && res.status === 200)
          caches.open(CACHE_NAME).then((c) => c.put(e.request, res.clone()));
        return res;
      }).catch(() => caches.match(e.request))
    );
    return;
  }

  // POSTs → sin interceptar (IndexedDB los gestiona en la app)
});