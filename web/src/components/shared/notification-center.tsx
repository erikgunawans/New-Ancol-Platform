"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getPermissionStatus,
  isPushSupported,
  subscribeToPush,
} from "@/lib/push";

interface NotificationItem {
  id: string;
  title: string;
  body: string;
  timestamp: string;
  url?: string;
  read: boolean;
}

const INITIAL_NOTIFICATIONS: NotificationItem[] = [
  {
    id: "1",
    title: "Review HITL Gate 1",
    body: "Dokumen DIR/RR/005/V/2025 menunggu review ekstraksi",
    timestamp: "2 jam yang lalu",
    url: "/documents",
    read: false,
  },
  {
    id: "2",
    title: "Laporan Selesai",
    body: "Laporan kepatuhan DIR/RR/004/IV/2025 siap diunduh",
    timestamp: "1 hari yang lalu",
    url: "/reports",
    read: false,
  },
];

export function NotificationCenter() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>(
    process.env.NODE_ENV === "development" ? INITIAL_NOTIFICATIONS : []
  );
  const [pushStatus, setPushStatus] = useState<string>("unsupported");

  // Initialise permission status on mount (client-only)
  useEffect(() => {
    setPushStatus(getPermissionStatus());
  }, []);

  // Listen for real-time push notifications from the service worker
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
      return;
    }

    function handleMessage(event: MessageEvent) {
      if (event.data?.type === "push-notification") {
        const { title, body, url } = event.data;
        const newNotification: NotificationItem = {
          id: crypto.randomUUID(),
          title: title ?? "Notifikasi baru",
          body: body ?? "",
          timestamp: "Baru saja",
          url,
          read: false,
        };
        setNotifications((prev) => [newNotification, ...prev]);
      }
    }

    navigator.serviceWorker.addEventListener("message", handleMessage);
    return () => {
      navigator.serviceWorker.removeEventListener("message", handleMessage);
    };
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  function handleNotificationClick(id: string, url?: string) {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
    if (url) {
      router.push(url);
    }
    setOpen(false);
  }

  async function handleEnablePush() {
    await subscribeToPush();
    setPushStatus(getPermissionStatus());
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 text-gray-500 hover:text-gray-700 transition-colors"
        aria-label="Notifications"
      >
        <svg
          className="w-5 h-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
          <div className="p-4 border-b border-gray-100 flex items-center justify-between">
            <h3 className="font-semibold text-sm">Notifikasi</h3>
            {isPushSupported() && pushStatus === "default" && (
              <button
                onClick={handleEnablePush}
                className="text-xs text-ancol-500 hover:underline"
              >
                Aktifkan notifikasi
              </button>
            )}
            {pushStatus === "denied" && (
              <span className="text-xs text-red-500">Notifikasi diblokir</span>
            )}
          </div>

          <div className="max-h-64 overflow-y-auto">
            {notifications.map((n) => (
              <button
                key={n.id}
                onClick={() => handleNotificationClick(n.id, n.url)}
                className={`w-full text-left p-4 border-b border-gray-50 hover:bg-gray-50 transition-colors ${
                  n.read ? "opacity-60" : ""
                }`}
              >
                <p className="text-sm font-medium">{n.title}</p>
                <p className="text-xs text-gray-500 mt-1">{n.body}</p>
                <p className="text-xs text-gray-400 mt-1">{n.timestamp}</p>
              </button>
            ))}
          </div>

          <div className="p-3 border-t border-gray-100 text-center">
            <button className="text-xs text-ancol-500 hover:underline">
              Lihat semua notifikasi
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
