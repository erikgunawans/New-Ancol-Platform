"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/scorecard", label: "Dashboard", icon: "📊" },
  { href: "/upload", label: "Upload MoM", icon: "📤" },
  { href: "/documents", label: "Dokumen", icon: "📄" },
  { href: "/review", label: "Review HITL", icon: "✅" },
  { href: "/reports", label: "Laporan", icon: "📑" },
  { href: "/batch", label: "Batch Proses", icon: "📦" },
  { href: "/regulations", label: "Regulasi", icon: "⚖️" },
  { href: "/audit-trail", label: "Audit Trail", icon: "🔍" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-ancol-500 text-white min-h-screen flex flex-col">
      <div className="p-6 border-b border-ancol-600">
        <h1 className="text-lg font-bold">PJAA Compliance</h1>
        <p className="text-xs text-ancol-100 mt-1">MoM Audit System</p>
      </div>

      <nav className="flex-1 py-4">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-6 py-3 text-sm transition-colors",
                isActive
                  ? "bg-ancol-600 text-white font-medium"
                  : "text-ancol-100 hover:bg-ancol-600 hover:text-white"
              )}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-ancol-600 text-xs text-ancol-100">
        PT Pembangunan Jaya Ancol Tbk
      </div>
    </aside>
  );
}
