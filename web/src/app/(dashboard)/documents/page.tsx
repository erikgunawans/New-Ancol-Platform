"use client";

import { useEffect, useState } from "react";
import { getDocuments } from "@/lib/api";
import { formatDate, getStatusColor } from "@/lib/utils";
import type { DocumentSummary } from "@/types";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getDocuments(filter || undefined)
      .then((data) => setDocuments(data.documents))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [filter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Dokumen</h1>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
        >
          <option value="">Semua Status</option>
          <option value="pending">Pending</option>
          <option value="processing_ocr">OCR Processing</option>
          <option value="hitl_gate_1">HITL Gate 1</option>
          <option value="hitl_gate_2">HITL Gate 2</option>
          <option value="hitl_gate_3">HITL Gate 3</option>
          <option value="hitl_gate_4">HITL Gate 4</option>
          <option value="complete">Selesai</option>
          <option value="failed">Gagal</option>
          <option value="rejected">Ditolak</option>
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
              <th className="px-6 py-3">Nama File</th>
              <th className="px-6 py-3">Format</th>
              <th className="px-6 py-3">Tanggal Rapat</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3">OCR</th>
              <th className="px-6 py-3">Diupload</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={6} className="px-6 py-12 text-center text-gray-400">Memuat...</td></tr>
            ) : documents.length === 0 ? (
              <tr><td colSpan={6} className="px-6 py-12 text-center text-gray-400">Tidak ada dokumen</td></tr>
            ) : (
              documents.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">{doc.filename}</td>
                  <td className="px-6 py-4 text-sm text-gray-500 uppercase">{doc.format}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{doc.meeting_date || "-"}</td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(doc.status)}`}>
                      {doc.status.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {doc.ocr_confidence != null ? `${(doc.ocr_confidence * 100).toFixed(0)}%` : "-"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">{formatDate(doc.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
