# PWA + Push Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Ancol MoM Compliance frontend installable as a PWA with offline support and push notifications for HITL review alerts and obligation deadline reminders.

**Architecture:** Manual service worker (no next-pwa, which is unmaintained for App Router). Custom `public/sw.js` with cache-first strategy for static assets, network-first for API calls. Web Push API with VAPID keys for server-to-client push. Backend push subscription storage in the existing API gateway. Notification center enhanced to show real push notifications.

**Tech Stack:** Next.js 15 App Router, Web Push API, Service Worker API, existing FastAPI backend

---

## File Structure

### PWA Core

| File | Action | Responsibility |
|------|--------|----------------|
| `web/public/manifest.json` | Create | PWA manifest with app name, icons, theme, display mode |
| `web/public/sw.js` | Create | Service worker: caching, push event handling, offline fallback |
| `web/public/offline.html` | Create | Simple offline fallback page |
| `web/src/app/layout.tsx` | Modify | Add manifest link, theme-color meta, viewport export |
| `web/src/components/shared/sw-register.tsx` | Create | Client component that registers the service worker on mount |
| `web/src/lib/push.ts` | Create | Push subscription helper (subscribe, unsubscribe, get status) |
| `web/src/components/shared/notification-center.tsx` | Modify | Show real notifications, push permission prompt |

### Backend (Push Subscription Storage)

| File | Action | Responsibility |
|------|--------|----------------|
| `services/api-gateway/src/api_gateway/routers/notifications.py` | Create | Push subscription CRUD endpoints |
| `services/api-gateway/tests/test_notifications.py` | Create | Tests for notification endpoints |

---

## Task 1: PWA Manifest + Icons + Offline Page

**Files:**
- Create: `web/public/manifest.json`
- Create: `web/public/icons/icon-192.svg`, `web/public/icons/icon-512.svg`
- Create: `web/public/offline.html`

- [ ] **Step 1: Create the public directory, manifest, and icons**

Create `web/public/manifest.json`:

```json
{
  "name": "PJAA Compliance System",
  "short_name": "PJAA",
  "description": "MoM & Contract Lifecycle Management — PT Pembangunan Jaya Ancol Tbk",
  "start_url": "/scorecard",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#1a237e",
  "orientation": "portrait-primary",
  "icons": [
    {
      "src": "/icons/icon-192.svg",
      "sizes": "192x192",
      "type": "image/svg+xml"
    },
    {
      "src": "/icons/icon-512.svg",
      "sizes": "512x512",
      "type": "image/svg+xml"
    },
    {
      "src": "/icons/icon-512.svg",
      "sizes": "512x512",
      "type": "image/svg+xml",
      "purpose": "maskable"
    }
  ],
  "categories": ["business", "productivity"],
  "lang": "id"
}
```

Create `web/public/icons/icon-192.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
  <rect width="192" height="192" rx="24" fill="#1a237e"/>
  <text x="96" y="110" text-anchor="middle" fill="white" font-family="Arial,sans-serif" font-size="48" font-weight="bold">PJAA</text>
</svg>
```

Create `web/public/icons/icon-512.svg` (same as above but 512x512 viewBox):

```svg
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="64" fill="#1a237e"/>
  <text x="256" y="296" text-anchor="middle" fill="white" font-family="Arial,sans-serif" font-size="128" font-weight="bold">PJAA</text>
</svg>
```

Create `web/public/offline.html`:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Offline — PJAA Compliance</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; background: #f9fafb; color: #333; }
    .container { text-align: center; padding: 2rem; }
    h1 { color: #1a237e; font-size: 1.5rem; margin-bottom: 0.5rem; }
    p { color: #666; font-size: 0.9rem; }
    button { margin-top: 1rem; padding: 0.5rem 1.5rem; background: #1a237e; color: white; border: none; border-radius: 0.5rem; cursor: pointer; font-size: 0.9rem; }
  </style>
</head>
<body>
  <div class="container">
    <h1>Tidak ada koneksi internet</h1>
    <p>Periksa koneksi Anda dan coba lagi.</p>
    <button onclick="window.location.reload()">Coba Lagi</button>
  </div>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add web/public/
git commit -m "feat(pwa): add web manifest, SVG icons, and offline fallback page"
```

---

## Task 2: Service Worker

**Files:**
- Create: `web/public/sw.js`

- [ ] **Step 1: Create the service worker**

Create `web/public/sw.js`:

```javascript
const CACHE_NAME = "pjaa-v1";
const STATIC_ASSETS = ["/offline.html"];

// Install: pre-cache offline fallback
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
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

// Push notification handling
self.addEventListener("push", (event) => {
  let data = { title: "PJAA Compliance", body: "Notifikasi baru" };
  try {
    data = event.data.json();
  } catch {
    data.body = event.data?.text() || data.body;
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icons/icon-192.svg",
      badge: "/icons/icon-192.svg",
      tag: data.tag || "default",
      data: { url: data.url || "/scorecard" },
    })
  );
});

// Notification click: open the app
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/scorecard";
  event.waitUntil(
    self.clients.matchAll({ type: "window" }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(url) && "focus" in client) return client.focus();
      }
      return self.clients.openWindow(url);
    })
  );
});
```

- [ ] **Step 2: Commit**

```bash
git add web/public/sw.js
git commit -m "feat(pwa): add service worker with caching and push event handling"
```

---

## Task 3: Service Worker Registration + PWA Metadata

**Files:**
- Create: `web/src/components/shared/sw-register.tsx`
- Modify: `web/src/app/layout.tsx`

- [ ] **Step 1: Create the SW registration client component**

Create `web/src/components/shared/sw-register.tsx`:

```tsx
"use client";

import { useEffect } from "react";

export function ServiceWorkerRegister() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return null;
}
```

- [ ] **Step 2: Update root layout with PWA metadata and SW registration**

Replace `web/src/app/layout.tsx`:

```tsx
import type { Metadata, Viewport } from "next";
import { ServiceWorkerRegister } from "@/components/shared/sw-register";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ancol MoM Compliance System",
  description: "Agentic AI MoM Compliance System — PT Pembangunan Jaya Ancol Tbk",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "PJAA Compliance",
  },
};

export const viewport: Viewport = {
  themeColor: "#1a237e",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <head>
        <link rel="apple-touch-icon" href="/icons/icon-192.svg" />
      </head>
      <body className="antialiased bg-gray-50 text-gray-900">
        {children}
        <ServiceWorkerRegister />
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Verify build compiles**

```bash
cd web && npm run build 2>&1 | tail -5
```

Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add web/src/components/shared/sw-register.tsx web/src/app/layout.tsx
git commit -m "feat(pwa): register service worker and add PWA metadata to root layout"
```

---

## Task 4: Push Subscription Helper

**Files:**
- Create: `web/src/lib/push.ts`

- [ ] **Step 1: Create the push subscription helper module**

Create `web/src/lib/push.ts`:

```typescript
const VAPID_PUBLIC_KEY = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY || "";

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) output[i] = raw.charCodeAt(i);
  return output;
}

export function isPushSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function getPermissionStatus(): NotificationPermission | "unsupported" {
  if (!isPushSupported()) return "unsupported";
  return Notification.permission;
}

export async function subscribeToPush(): Promise<PushSubscription | null> {
  if (!isPushSupported() || !VAPID_PUBLIC_KEY) return null;

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return null;

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
  });

  await fetch("/api/notifications/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscription.toJSON()),
  });

  return subscription;
}

export async function unsubscribeFromPush(): Promise<void> {
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    const endpoint = subscription.endpoint;
    await subscription.unsubscribe();
    await fetch("/api/notifications/unsubscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint }),
    });
  }
}

export async function getCurrentSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}
```

- [ ] **Step 2: Verify build compiles**

```bash
cd web && npm run build 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/push.ts
git commit -m "feat(pwa): add push subscription helper module"
```

---

## Task 5: Enhanced Notification Center with Push Permission

**Files:**
- Modify: `web/src/components/shared/notification-center.tsx`

- [ ] **Step 1: Enhance the notification center**

Replace `web/src/components/shared/notification-center.tsx` to add push permission handling, unread badge based on count, and the "Aktifkan notifikasi" button. Keep the existing bell icon and dropdown pattern. Add a useEffect that listens for service worker messages for real-time push display. Use `isPushSupported()`, `getPermissionStatus()`, and `subscribeToPush()` from `@/lib/push`. Show "Notifikasi diblokir" in red text when permission is `denied`. Show "Aktifkan notifikasi" link when permission is `default`. Mark notifications as read on click.

Interface for notification items:

```typescript
interface NotificationItem {
  id: string;
  title: string;
  body: string;
  timestamp: string;
  url?: string;
  read: boolean;
}
```

Default with 2 mock notifications (same as current: HITL review + report ready). Service worker message listener adds new items to the top of the list.

- [ ] **Step 2: Verify build compiles**

```bash
cd web && npm run build 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/shared/notification-center.tsx
git commit -m "feat(pwa): enhance notification center with push permission handling"
```

---

## Task 6: Backend Push Subscription Endpoints

**Files:**
- Create: `services/api-gateway/src/api_gateway/routers/notifications.py`
- Create: `services/api-gateway/tests/test_notifications.py`
- Modify: `services/api-gateway/src/api_gateway/main.py`

- [ ] **Step 1: Write failing tests**

Create `services/api-gateway/tests/test_notifications.py` with 5 tests:

1. `test_subscribe_stores_subscription` — POST /api/notifications/subscribe with endpoint+keys, assert 200 and subscription stored
2. `test_subscribe_deduplicates_by_endpoint` — subscribe twice with same endpoint, assert only 1 stored
3. `test_unsubscribe_removes_subscription` — pre-populate, unsubscribe, assert removed
4. `test_unsubscribe_nonexistent_is_ok` — unsubscribe non-existent endpoint, assert 200 (idempotent)
5. `test_list_subscriptions` — pre-populate 2, GET /api/notifications/subscriptions, assert total=2

Each test clears `_subscriptions` list before running. Uses `TestClient(app)` pattern from existing tests.

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/test_notifications.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Implement notifications router**

Create `services/api-gateway/src/api_gateway/routers/notifications.py` with:
- `_subscriptions: list[dict]` in-memory store
- `POST /subscribe` — deduplicate by endpoint, store subscription
- `POST /unsubscribe` — remove by endpoint (idempotent)
- `GET /subscriptions` — list all subscriptions with total count

- [ ] **Step 4: Register router in main.py**

Add `from api_gateway.routers.notifications import router as notifications_router` and `app.include_router(notifications_router, prefix="/api")` to `services/api-gateway/src/api_gateway/main.py`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/test_notifications.py -v
```

Expected: 5 tests PASS

- [ ] **Step 6: Run full API gateway suite**

```bash
PYTHONPATH=packages/ancol-common/src:services/api-gateway/src python3 -m pytest services/api-gateway/tests/ -q
```

Expected: 95+ tests pass (90 existing + 5 new)

- [ ] **Step 7: Commit**

```bash
git add services/api-gateway/src/api_gateway/routers/notifications.py services/api-gateway/tests/test_notifications.py services/api-gateway/src/api_gateway/main.py
git commit -m "feat(api): add push notification subscription endpoints"
```

---

## Task 7: Lint + Full Verification

- [ ] **Step 1: Run ruff**

```bash
ruff check packages/ services/ scripts/ corpus/scripts/
ruff format --check packages/ services/ scripts/ corpus/scripts/
```

- [ ] **Step 2: Run all service tests**

```bash
for svc in extraction-agent legal-research-agent comparison-agent reporting-agent api-gateway batch-engine email-ingest regulation-monitor gemini-agent; do
  echo "=== $svc ===" && PYTHONPATH=packages/ancol-common/src:services/$svc/src python3 -m pytest services/$svc/tests/ -q
done
```

Expected: 282+ tests (277 existing + 5 new notification tests)

- [ ] **Step 3: Verify frontend builds**

```bash
cd web && npm run build
```

- [ ] **Step 4: Fix any issues and commit**

---

## Summary

| Task | What it does | Tests added |
|------|-------------|-------------|
| 1 | PWA manifest + SVG icons + offline page | — |
| 2 | Service worker (caching, offline, push events) | — |
| 3 | SW registration component + PWA metadata in layout | — |
| 4 | Push subscription helper (`push.ts`) | — |
| 5 | Enhanced notification center with push permission | — |
| 6 | Backend push subscription endpoints | 5 tests |
| 7 | Lint + full verification | — |

**Total new tests:** 5
**Total files created:** 8
**Total files modified:** 3

Confidence: 97%
Verification passes: 2
[Fixed between passes: replaced dangerouslySetInnerHTML SW registration with a client component (sw-register.tsx) to satisfy security hook]
