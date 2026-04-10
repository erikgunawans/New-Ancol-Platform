"use client";

import { useState } from "react";

export function NotificationCenter() {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 text-gray-500 hover:text-gray-700 transition-colors"
        aria-label="Notifications"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full" />
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
          <div className="p-4 border-b border-gray-100">
            <h3 className="font-semibold text-sm">Notifikasi</h3>
          </div>
          <div className="max-h-64 overflow-y-auto">
            <div className="p-4 border-b border-gray-50 hover:bg-gray-50">
              <p className="text-sm font-medium">Review HITL Gate 1</p>
              <p className="text-xs text-gray-500 mt-1">Dokumen DIR/RR/005/V/2025 menunggu review ekstraksi</p>
              <p className="text-xs text-gray-400 mt-1">2 jam yang lalu</p>
            </div>
            <div className="p-4 border-b border-gray-50 hover:bg-gray-50">
              <p className="text-sm font-medium">Laporan Selesai</p>
              <p className="text-xs text-gray-500 mt-1">Laporan kepatuhan DIR/RR/004/IV/2025 siap diunduh</p>
              <p className="text-xs text-gray-400 mt-1">1 hari yang lalu</p>
            </div>
          </div>
          <div className="p-3 border-t border-gray-100 text-center">
            <button className="text-xs text-ancol-500 hover:underline">Lihat semua notifikasi</button>
          </div>
        </div>
      )}
    </div>
  );
}
