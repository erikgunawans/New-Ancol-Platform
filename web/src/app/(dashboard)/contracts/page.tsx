"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getContracts } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ContractSummary } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  draft: "Draf",
  pending_review: "Menunggu Review",
  in_review: "Dalam Review",
  approved: "Disetujui",
  executed: "Ditandatangani",
  active: "Aktif",
  expiring: "Akan Berakhir",
  expired: "Berakhir",
  terminated: "Dibatalkan",
  amended: "Diamandemen",
  failed: "Gagal",
};

const STATUS_COLORS: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  pending_review: "bg-yellow-100 text-yellow-700",
  in_review: "bg-blue-100 text-blue-700",
  approved: "bg-green-100 text-green-700",
  executed: "bg-green-100 text-green-700",
  active: "bg-emerald-100 text-emerald-700",
  expiring: "bg-orange-100 text-orange-700",
  expired: "bg-red-100 text-red-700",
  terminated: "bg-red-100 text-red-700",
  amended: "bg-purple-100 text-purple-700",
  failed: "bg-red-100 text-red-700",
};

const TYPE_LABELS: Record<string, string> = {
  nda: "NDA",
  vendor: "Vendor",
  sale_purchase: "Jual Beli",
  joint_venture: "Joint Venture",
  land_lease: "Sewa Tanah",
  employment: "Ketenagakerjaan",
  sop_board_resolution: "SOP/SK Direksi",
};

const RISK_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-green-100 text-green-700",
};

export default function ContractsPage() {
  const router = useRouter();
  const [contracts, setContracts] = useState<ContractSummary[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getContracts(statusFilter || undefined, typeFilter || undefined)
      .then((data) => setContracts(data.contracts))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [statusFilter, typeFilter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Kontrak</h1>
        <div className="flex gap-3">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Semua Tipe</option>
            {Object.entries(TYPE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Semua Status</option>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
              <th className="px-6 py-3">Judul</th>
              <th className="px-6 py-3">Nomor</th>
              <th className="px-6 py-3">Tipe</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3">Risiko</th>
              <th className="px-6 py-3">Berlaku</th>
              <th className="px-6 py-3">Berakhir</th>
              <th className="px-6 py-3">Nilai</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan={8} className="px-6 py-12 text-center text-gray-400">
                  Memuat kontrak...
                </td>
              </tr>
            ) : contracts.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-6 py-12 text-center text-gray-400">
                  Belum ada kontrak
                </td>
              </tr>
            ) : (
              contracts.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => router.push(`/contracts/${c.id}`)}>
                  <td className="px-6 py-4 text-sm font-medium text-gray-900 max-w-xs truncate">
                    {c.title}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {c.contract_number || "-"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {TYPE_LABELS[c.contract_type] || c.contract_type}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[c.status] || "bg-gray-100 text-gray-700"}`}>
                      {STATUS_LABELS[c.status] || c.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    {c.risk_level ? (
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${RISK_COLORS[c.risk_level]}`}>
                        {c.risk_level.toUpperCase()}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {c.effective_date ? formatDate(c.effective_date) : "-"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {c.expiry_date ? formatDate(c.expiry_date) : "-"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {c.total_value
                      ? `${c.currency} ${c.total_value.toLocaleString("id-ID")}`
                      : "-"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
