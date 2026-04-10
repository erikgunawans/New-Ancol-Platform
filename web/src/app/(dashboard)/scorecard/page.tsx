"use client";

import { useEffect, useState } from "react";
import { getDashboardStats, getDashboardTrends } from "@/lib/api";
import { getScoreColor, getScoreGrade, getScoreLabel } from "@/lib/utils";
import type { DashboardStats, TrendPoint } from "@/types";

export default function ScoreboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [trends, setTrends] = useState<TrendPoint[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDashboardStats().then(setStats).catch((e) => setError(e.message));
    getDashboardTrends(6).then((data) => setTrends(data.trends)).catch(() => {});
  }, []);

  if (error) return <ErrorState message={error} />;
  if (!stats) return <LoadingState />;

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard Kepatuhan</h1>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Dokumen" value={stats.total_documents} color="bg-blue-50 text-blue-700" />
        <StatCard label="Menunggu Review" value={stats.pending_review} color="bg-amber-50 text-amber-700" />
        <StatCard label="Selesai" value={stats.completed} color="bg-green-50 text-green-700" />
        <StatCard label="Gagal / Ditolak" value={stats.failed + stats.rejected} color="bg-red-50 text-red-700" />
      </div>

      {/* Scorecard */}
      {stats.avg_composite_score != null && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <h2 className="text-lg font-semibold mb-4">Rata-rata Skor Kepatuhan</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <ScorePill label="Struktural (30%)" score={stats.avg_structural_score ?? 0} />
            <ScorePill label="Substantif (35%)" score={stats.avg_substantive_score ?? 0} />
            <ScorePill label="Regulasi (35%)" score={stats.avg_regulatory_score ?? 0} />
            <ScorePill label="Komposit" score={stats.avg_composite_score} isComposite />
          </div>
        </div>
      )}

      {/* Trend Chart */}
      {trends.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
          <h2 className="text-lg font-semibold mb-4">Tren Skor Kepatuhan (6 Bulan)</h2>
          <div className="flex items-end gap-2 h-40">
            {trends.map((point) => {
              const score = point.avg_composite ?? 0;
              const height = Math.max(score, 5);
              return (
                <div key={point.period} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs font-medium text-gray-700">
                    {score > 0 ? score.toFixed(0) : "—"}
                  </span>
                  <div
                    className={`w-full rounded-t-lg transition-all ${getScoreColor(score)}`}
                    style={{ height: `${height}%` }}
                  />
                  <span className="text-xs text-gray-500">
                    {point.period.slice(5)}
                  </span>
                  <span className="text-xs text-gray-400">
                    {point.document_count} dok
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Status Distribution */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Distribusi Status Dokumen</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Object.entries(stats.documents_by_status).map(([status, count]) => (
            <div key={status} className="p-3 bg-gray-50 rounded-lg">
              <div className="text-xs text-gray-500 uppercase">{status.replace(/_/g, " ")}</div>
              <div className="text-xl font-bold mt-1">{count}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`rounded-xl p-4 ${color}`}>
      <div className="text-sm font-medium">{label}</div>
      <div className="text-3xl font-bold mt-1">{value}</div>
    </div>
  );
}

function ScorePill({ label, score, isComposite }: { label: string; score: number; isComposite?: boolean }) {
  return (
    <div className={`text-center p-4 rounded-xl ${getScoreColor(score)}`}>
      <div className="text-3xl font-bold">{score.toFixed(0)}</div>
      {isComposite && <div className="text-sm font-medium mt-1">{getScoreGrade(score)} — {getScoreLabel(score)}</div>}
      <div className="text-xs mt-1 opacity-75">{label}</div>
    </div>
  );
}

function LoadingState() {
  return <div className="flex items-center justify-center h-64 text-gray-400">Memuat dashboard...</div>;
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-red-700">
      <p className="font-medium">Gagal memuat data</p>
      <p className="text-sm mt-1">{message}</p>
    </div>
  );
}
