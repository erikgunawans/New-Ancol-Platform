"use client";

import { useEffect, useState } from "react";
import { getHitlQueue, getContracts } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { HitlQueueItem, ContractSummary } from "@/types";

export default function ApprovePage() {
  const [hitlItems, setHitlItems] = useState<HitlQueueItem[]>([]);
  const [pendingContracts, setPendingContracts] = useState<ContractSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getHitlQueue().catch(() => ({ items: [], total: 0 })),
      getContracts("pending_review").catch(() => ({ contracts: [], total: 0 })),
    ])
      .then(([hitl, contracts]) => {
        setHitlItems(hitl.items);
        setPendingContracts(contracts.contracts);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-gray-400">Memuat item persetujuan...</p>
      </div>
    );
  }

  const totalItems = hitlItems.length + pendingContracts.length;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Persetujuan</h1>
      <p className="text-sm text-gray-500 mb-6">
        {totalItems} item menunggu persetujuan Anda
      </p>

      {totalItems === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
          <p className="text-gray-400 text-lg">Tidak ada item untuk disetujui</p>
          <p className="text-gray-300 text-sm mt-1">Semua sudah terselesaikan</p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* MoM HITL items */}
          {hitlItems.map((item) => (
            <div
              key={`hitl-${item.document_id}`}
              className="bg-white rounded-xl shadow-sm border border-gray-200 p-5"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                      MoM
                    </span>
                    <span className="text-xs text-gray-500">
                      {item.gate.replace("gate_", "Gate ")}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-gray-900">{item.filename}</p>
                  {item.meeting_date && (
                    <p className="text-xs text-gray-500 mt-1">
                      Rapat: {formatDate(item.meeting_date)}
                    </p>
                  )}
                </div>
                <a
                  href={`/review/${item.document_id}`}
                  className="px-4 py-2 bg-ancol-500 text-white text-sm font-medium rounded-lg hover:bg-ancol-600 transition-colors"
                >
                  Review
                </a>
              </div>
            </div>
          ))}

          {/* Contract review items */}
          {pendingContracts.map((c) => (
            <div
              key={`contract-${c.id}`}
              className="bg-white rounded-xl shadow-sm border border-gray-200 p-5"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">
                      Kontrak
                    </span>
                    <span className="text-xs text-gray-500">
                      {c.contract_type.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-gray-900">{c.title}</p>
                  {c.total_value && (
                    <p className="text-xs text-gray-500 mt-1">
                      Nilai: {c.currency} {c.total_value.toLocaleString("id-ID")}
                    </p>
                  )}
                </div>
                <a
                  href={`/contracts/${c.id}`}
                  className="px-4 py-2 bg-ancol-500 text-white text-sm font-medium rounded-lg hover:bg-ancol-600 transition-colors"
                >
                  Review
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
