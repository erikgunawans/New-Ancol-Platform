"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getHitlQueue } from "@/lib/api";
import type { HitlQueueItem } from "@/types";

const GATE_LABELS: Record<string, string> = {
  hitl_gate_1: "Gate 1 — Ekstraksi",
  hitl_gate_2: "Gate 2 — Regulasi",
  hitl_gate_3: "Gate 3 — Temuan",
  hitl_gate_4: "Gate 4 — Laporan",
};

const GATE_COLORS: Record<string, string> = {
  hitl_gate_1: "bg-blue-100 text-blue-700",
  hitl_gate_2: "bg-purple-100 text-purple-700",
  hitl_gate_3: "bg-amber-100 text-amber-700",
  hitl_gate_4: "bg-green-100 text-green-700",
};

export default function ReviewQueuePage() {
  const [items, setItems] = useState<HitlQueueItem[]>([]);
  const [gateFilter, setGateFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getHitlQueue(gateFilter || undefined)
      .then((data) => setItems(data.items))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [gateFilter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Review HITL</h1>
        <select
          value={gateFilter}
          onChange={(e) => setGateFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">Semua Gate</option>
          <option value="gate_1">Gate 1 — Ekstraksi</option>
          <option value="gate_2">Gate 2 — Regulasi</option>
          <option value="gate_3">Gate 3 — Temuan</option>
          <option value="gate_4">Gate 4 — Laporan</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center text-gray-400 py-12">Memuat antrian review...</div>
      ) : items.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <div className="text-4xl mb-3">✅</div>
          <p className="text-gray-500">Tidak ada dokumen yang menunggu review</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <Link
              key={item.document_id}
              href={`/review/${item.document_id}`}
              className="block bg-white rounded-xl shadow-sm border border-gray-200 p-5 hover:border-ancol-500 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900">{item.filename}</h3>
                  <p className="text-sm text-gray-500 mt-1">
                    {item.meeting_date ? `Rapat: ${item.meeting_date}` : "Tanggal rapat tidak diketahui"}
                  </p>
                </div>
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${GATE_COLORS[item.gate] || "bg-gray-100 text-gray-700"}`}>
                  {GATE_LABELS[item.gate] || item.gate}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
