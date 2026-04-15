const CACHE_NAME = "pjaa-v1";
const STATIC_ASSETS = ["/offline.html"];

// Install: pre-cache offline fallback, then activate immediately
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activate: clean old caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: network-first for navigation, stale-while-revalidate for static assets
self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  if (request.url.includes("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/offline.html"))
    );
    return;
  }

  if (
    request.url.match(/\.(js|css|png|jpg|svg|woff2?)$/) ||
    request.url.includes("/_next/static/")
  ) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const fetching = fetch(request).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, clone));
          }
          return response;
        });
        return cached || fetching;
      })
    );
    return;
  }
});

// Push notification handling — show notification + relay to open tabs
self.addEventListener("push", (event) => {
  let data = { title: "PJAA Compliance", body: "Notifikasi baru" };
  try {
    data = event.data.json();
  } catch {
    data.body = event.data?.text() || data.body;
  }

  // Only allow relative URLs (same-origin)
  const url = data.url && data.url.startsWith("/") ? data.url : "/scorecard";

  event.waitUntil(
    Promise.all([
      self.registration.showNotification(data.title, {
        body: data.body,
        icon: "/icons/icon-192.svg",
        badge: "/icons/icon-192.svg",
        tag: data.tag || "default",
        data: { url },
      }),
      // Relay to open tabs for in-app notification display
      self.clients
        .matchAll({ includeUncontrolled: true, type: "window" })
        .then((clients) =>
          clients.forEach((client) =>
            client.postMessage({
              type: "push-notification",
              title: data.title,
              body: data.body,
              url,
            })
          )
        ),
    ])
  );
});

// Notification click: open the app (same-origin URLs only)
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/scorecard";
  if (!url.startsWith("/")) return;

  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(url) && "focus" in client) return client.focus();
      }
      return self.clients.openWindow(url);
    })
  );
});
