"use client";

import { NotificationCenter } from "./notification-center";

export function Header() {
  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-800">
          Sistem Kepatuhan Risalah Rapat
        </h2>
      </div>
      <div className="flex items-center gap-4">
        <NotificationCenter />
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-ancol-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
            CS
          </div>
          <span className="text-sm text-gray-600">Corp Secretary</span>
        </div>
      </div>
    </header>
  );
}
