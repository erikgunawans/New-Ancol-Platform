"use client";

import { useEffect, useState } from "react";
import { getReports } from "@/lib/api";
import { formatDate, getScoreColor } from "@/lib/utils";
import type { ReportSummary } from "@/types";

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getReports()
      .then((data) => setReports(data.reports))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Laporan Kepatuhan</h1>

      {loading ? (
        <div className="text-center text-gray-400 py-12">Memuat laporan...</div>
      ) : reports.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center text-gray-400">
          Belum ada laporan kepatuhan
        </div>
      ) : (
        <div className="space-y-4">
          {reports.map((report) => (
            <div key={report.id} className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-gray-900">{report.filename}</h3>
                  <p className="text-sm text-gray-500 mt-1">{formatDate(report.created_at)}</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className={`text-center px-4 py-2 rounded-lg ${getScoreColor(report.composite_score)}`}>
                    <div className="text-xl font-bold">{report.composite_score.toFixed(0)}</div>
                    <div className="text-xs">Komposit</div>
                  </div>
                  <div className="flex gap-2">
                    {report.pdf_uri && (
                      <a
                        href={`/api/reports/${report.id}/download/pdf`}
                        className="px-3 py-1.5 bg-red-50 text-red-700 rounded-lg text-sm hover:bg-red-100 transition-colors"
                      >
                        PDF
                      </a>
                    )}
                    {report.excel_uri && (
                      <a
                        href={`/api/reports/${report.id}/download/excel`}
                        className="px-3 py-1.5 bg-green-50 text-green-700 rounded-lg text-sm hover:bg-green-100 transition-colors"
                      >
                        Excel
                      </a>
                    )}
                  </div>
                </div>
              </div>

              {/* Score breakdown */}
              <div className="mt-4 grid grid-cols-3 gap-2">
                <div className="text-center p-2 bg-gray-50 rounded-lg">
                  <div className="text-sm font-medium">{report.structural_score.toFixed(0)}</div>
                  <div className="text-xs text-gray-500">Struktural</div>
                </div>
                <div className="text-center p-2 bg-gray-50 rounded-lg">
                  <div className="text-sm font-medium">{report.substantive_score.toFixed(0)}</div>
                  <div className="text-xs text-gray-500">Substantif</div>
                </div>
                <div className="text-center p-2 bg-gray-50 rounded-lg">
                  <div className="text-sm font-medium">{report.regulatory_score.toFixed(0)}</div>
                  <div className="text-xs text-gray-500">Regulasi</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
