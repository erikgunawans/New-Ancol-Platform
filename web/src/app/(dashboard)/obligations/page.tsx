"use client";

import { useEffect, useState } from "react";
import { getObligations, getUpcomingObligations } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ObligationSummary } from "@/types";

const STATUS_LABELS: Record<string, string> = {
  upcoming: "Akan Datang",
  due_soon: "Segera Jatuh Tempo",
  overdue: "Terlambat",
  fulfilled: "Terpenuhi",
  waived: "Dikesampingkan",
};

const STATUS_COLORS: Record<string, string> = {
  upcoming: "bg-blue-100 text-blue-700",
  due_soon: "bg-orange-100 text-orange-700",
  overdue: "bg-red-100 text-red-700",
  fulfilled: "bg-green-100 text-green-700",
  waived: "bg-gray-100 text-gray-600",
};

const TYPE_LABELS: Record<string, string> = {
  renewal: "Perpanjangan",
  reporting: "Pelaporan",
  payment: "Pembayaran",
  termination_notice: "Notifikasi Pemutusan",
  deliverable: "Deliverable",
  compliance_filing: "Filing Kepatuhan",
};

export default function ObligationsPage() {
  const [obligations, setObligations] = useState<ObligationSummary[]>([]);
  const [view, setView] = useState<"all" | "upcoming">("upcoming");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    if (view === "upcoming") {
      getUpcomingObligations(30)
        .then((data) => setObligations(data.upcoming))
        .catch(() => {})
        .finally(() => setLoading(false));
    } else {
      getObligations(undefined, statusFilter || undefined)
        .then((data) => setObligations(data.obligations))
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  }, [view, statusFilter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Kewajiban Kontrak</h1>
        <div className="flex gap-3">
          <div className="inline-flex rounded-lg border border-gray-300 overflow-hidden">
            <button
              onClick={() => setView("upcoming")}
              className={`px-4 py-2 text-sm ${view === "upcoming" ? "bg-ancol-500 text-white" : "bg-white text-gray-700"}`}
            >
              Akan Datang
            </button>
            <button
              onClick={() => setView("all")}
              className={`px-4 py-2 text-sm ${view === "all" ? "bg-ancol-500 text-white" : "bg-white text-gray-700"}`}
            >
              Semua
            </button>
          </div>
          {view === "all" && (
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
          )}
        </div>
      </div>

      <div className="space-y-3">
        {loading ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-400">
            Memuat kewajiban...
          </div>
        ) : obligations.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-400">
            Tidak ada kewajiban {view === "upcoming" ? "dalam 30 hari ke depan" : ""}
          </div>
        ) : (
          obligations.map((o) => (
            <div
              key={o.id}
              className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[o.status] || "bg-gray-100"}`}>
                      {STATUS_LABELS[o.status] || o.status}
                    </span>
                    <span className="text-xs text-gray-500">
                      {TYPE_LABELS[o.obligation_type] || o.obligation_type}
                    </span>
                    {o.recurrence && (
                      <span className="text-xs text-gray-400">
                        ({o.recurrence})
                      </span>
                    )}
                  </div>
                  <p className="text-sm font-medium text-gray-900">{o.description}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Penanggung jawab: {o.responsible_party_name}
                  </p>
                </div>
                <div className="text-right ml-4">
                  <p className={`text-sm font-semibold ${o.status === "overdue" ? "text-red-600" : "text-gray-700"}`}>
                    {formatDate(o.due_date)}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">Jatuh tempo</p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
