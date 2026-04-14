"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getContract, getContractClauses, getContractRisk, getObligations } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { ContractSummary, ContractClauseItem, ObligationSummary } from "@/types";

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

const OBLIGATION_STATUS_LABELS: Record<string, string> = {
  upcoming: "Akan Datang",
  due_soon: "Segera Jatuh Tempo",
  overdue: "Terlambat",
  fulfilled: "Terpenuhi",
  waived: "Dikesampingkan",
};

const OBLIGATION_STATUS_COLORS: Record<string, string> = {
  upcoming: "bg-blue-100 text-blue-700",
  due_soon: "bg-orange-100 text-orange-700",
  overdue: "bg-red-100 text-red-700",
  fulfilled: "bg-green-100 text-green-700",
  waived: "bg-gray-100 text-gray-600",
};

const OBLIGATION_TYPE_LABELS: Record<string, string> = {
  renewal: "Perpanjangan",
  reporting: "Pelaporan",
  payment: "Pembayaran",
  termination_notice: "Notifikasi Pemutusan",
  deliverable: "Deliverable",
  compliance_filing: "Filing Kepatuhan",
};

type Tab = "clauses" | "obligations" | "risk";

export default function ContractDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [contract, setContract] = useState<ContractSummary | null>(null);
  const [clauses, setClauses] = useState<ContractClauseItem[]>([]);
  const [obligations, setObligations] = useState<ObligationSummary[]>([]);
  const [risk, setRisk] = useState<{ risk_level: string; risk_score: number | null } | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("clauses");

  useEffect(() => {
    if (!id) return;

    setLoading(true);
    Promise.all([
      getContract(id),
      getContractClauses(id).catch(() => ({ clauses: [] as ContractClauseItem[] })),
      getObligations(id).catch(() => ({ obligations: [] as ObligationSummary[] })),
      getContractRisk(id).catch(() => null),
    ])
      .then(([contractData, clausesData, obligationsData, riskData]) => {
        setContract(contractData);
        setClauses(clausesData.clauses);
        setObligations(obligationsData.obligations);
        setRisk(riskData);
      })
      .catch(() => {
        setNotFound(true);
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-ancol-500 mx-auto mb-4" />
          <p className="text-gray-400">Memuat detail kontrak...</p>
        </div>
      </div>
    );
  }

  if (notFound || !contract) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <p className="text-lg font-semibold text-gray-700 mb-2">Kontrak tidak ditemukan</p>
          <p className="text-sm text-gray-400 mb-4">ID: {id}</p>
          <button
            onClick={() => router.push("/contracts")}
            className="text-ancol-600 hover:text-ancol-700 text-sm font-medium"
          >
            &larr; Kembali ke Daftar Kontrak
          </button>
        </div>
      </div>
    );
  }

  const highRiskClauses = clauses.filter(
    (c) => c.risk_level === "high" || c.risk_level === "medium"
  );

  return (
    <div>
      {/* Breadcrumb */}
      <nav className="flex items-center text-sm text-gray-500 mb-4">
        <button
          onClick={() => router.push("/contracts")}
          className="hover:text-ancol-600"
        >
          Kontrak
        </button>
        <span className="mx-2">/</span>
        <span className="text-gray-900 font-medium truncate max-w-xs">
          {contract.title}
        </span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{contract.title}</h1>
          <div className="flex items-center gap-3 mt-2">
            {contract.contract_number && (
              <span className="text-sm text-gray-500">
                {contract.contract_number}
              </span>
            )}
            <span className="text-sm text-gray-500">
              {TYPE_LABELS[contract.contract_type] || contract.contract_type}
            </span>
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[contract.status] || "bg-gray-100 text-gray-700"}`}
            >
              {STATUS_LABELS[contract.status] || contract.status}
            </span>
          </div>
        </div>
      </div>

      {/* Metadata Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <p className="text-xs font-medium text-gray-500 uppercase">Berlaku</p>
          <p className="text-lg font-semibold text-gray-900 mt-1">
            {contract.effective_date ? formatDate(contract.effective_date) : "-"}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <p className="text-xs font-medium text-gray-500 uppercase">Berakhir</p>
          <p className="text-lg font-semibold text-gray-900 mt-1">
            {contract.expiry_date ? formatDate(contract.expiry_date) : "-"}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <p className="text-xs font-medium text-gray-500 uppercase">Nilai Kontrak</p>
          <p className="text-lg font-semibold text-gray-900 mt-1">
            {contract.total_value
              ? `${contract.currency} ${contract.total_value.toLocaleString("id-ID")}`
              : "-"}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
          <p className="text-xs font-medium text-gray-500 uppercase">Risiko</p>
          <div className="mt-1 flex items-center gap-2">
            {risk?.risk_level ? (
              <>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${RISK_COLORS[risk.risk_level] || "bg-gray-100 text-gray-700"}`}
                >
                  {risk.risk_level.toUpperCase()}
                </span>
                {risk.risk_score !== null && (
                  <span className="text-sm text-gray-500">
                    ({risk.risk_score}%)
                  </span>
                )}
              </>
            ) : contract.risk_level ? (
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${RISK_COLORS[contract.risk_level] || "bg-gray-100 text-gray-700"}`}
              >
                {contract.risk_level.toUpperCase()}
              </span>
            ) : (
              <span className="text-lg font-semibold text-gray-900">-</span>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex gap-6">
          {([
            { key: "clauses" as Tab, label: "Klausul", count: clauses.length },
            { key: "obligations" as Tab, label: "Kewajiban", count: obligations.length },
            { key: "risk" as Tab, label: "Analisis Risiko", count: highRiskClauses.length },
          ]).map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? "border-ancol-500 text-ancol-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.label}
              <span className="ml-1.5 text-xs text-gray-400">({tab.count})</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === "clauses" && (
        <div className="space-y-4">
          {clauses.length === 0 ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-400">
              Belum ada klausul yang diekstrak
            </div>
          ) : (
            clauses.map((clause) => (
              <div
                key={clause.id}
                className="bg-white rounded-xl shadow-sm border border-gray-200 p-5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-mono text-gray-400">
                      {clause.clause_number}
                    </span>
                    <h3 className="text-sm font-semibold text-gray-900">
                      {clause.title}
                    </h3>
                    {clause.category && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
                        {clause.category}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 ml-4 shrink-0">
                    {clause.risk_level && (
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${RISK_COLORS[clause.risk_level] || "bg-gray-100 text-gray-700"}`}
                      >
                        {clause.risk_level.toUpperCase()}
                      </span>
                    )}
                    <span className="text-xs text-gray-400">
                      {Math.round(clause.confidence * 100)}%
                    </span>
                  </div>
                </div>
                <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {clause.text}
                </p>
                {clause.risk_reason && (
                  <p className="mt-3 text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
                    {clause.risk_reason}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === "obligations" && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          {obligations.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              Belum ada kewajiban untuk kontrak ini
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
                  <th className="px-6 py-3">Tipe</th>
                  <th className="px-6 py-3">Deskripsi</th>
                  <th className="px-6 py-3">Jatuh Tempo</th>
                  <th className="px-6 py-3">Penanggung Jawab</th>
                  <th className="px-6 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {obligations.map((o) => (
                  <tr key={o.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {OBLIGATION_TYPE_LABELS[o.obligation_type] || o.obligation_type}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 max-w-sm">
                      {o.description}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 whitespace-nowrap">
                      {formatDate(o.due_date)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {o.responsible_party_name}
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${OBLIGATION_STATUS_COLORS[o.status] || "bg-gray-100 text-gray-700"}`}
                      >
                        {OBLIGATION_STATUS_LABELS[o.status] || o.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {activeTab === "risk" && (
        <div className="space-y-6">
          {/* Risk Overview */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Ringkasan Risiko</h3>
            <div className="flex items-center gap-6">
              {risk?.risk_score !== null && risk?.risk_score !== undefined ? (
                <div className="text-center">
                  <p className="text-4xl font-bold text-gray-900">{risk.risk_score}%</p>
                  <p className="text-xs text-gray-500 mt-1">Skor Risiko</p>
                </div>
              ) : (
                <div className="text-center">
                  <p className="text-4xl font-bold text-gray-300">-</p>
                  <p className="text-xs text-gray-500 mt-1">Skor Risiko</p>
                </div>
              )}
              <div>
                {(risk?.risk_level || contract.risk_level) && (
                  <span
                    className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${RISK_COLORS[risk?.risk_level || contract.risk_level || ""] || "bg-gray-100 text-gray-700"}`}
                  >
                    {(risk?.risk_level || contract.risk_level || "").toUpperCase()}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* High/Medium Risk Clauses */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              Klausul Risiko Sedang &amp; Tinggi ({highRiskClauses.length})
            </h3>
            {highRiskClauses.length === 0 ? (
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-400">
                Tidak ada klausul dengan risiko sedang atau tinggi
              </div>
            ) : (
              <div className="space-y-3">
                {highRiskClauses.map((clause) => (
                  <div
                    key={clause.id}
                    className="bg-white rounded-xl shadow-sm border border-gray-200 p-4"
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-xs font-mono text-gray-400">
                        {clause.clause_number}
                      </span>
                      <span className="text-sm font-medium text-gray-900">
                        {clause.title}
                      </span>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${RISK_COLORS[clause.risk_level || ""] || "bg-gray-100 text-gray-700"}`}
                      >
                        {(clause.risk_level || "").toUpperCase()}
                      </span>
                    </div>
                    {clause.risk_reason && (
                      <p className="text-sm text-gray-600">{clause.risk_reason}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
