"use client";

import { useEffect, useState } from "react";
import { getAuditEntries } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import type { AuditEntry } from "@/types";

export default function AuditTrailPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAuditEntries(100)
      .then((data) => setEntries(data.entries))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Audit Trail</h1>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 text-left text-xs font-medium text-gray-500 uppercase">
              <th className="px-6 py-3">Waktu</th>
              <th className="px-6 py-3">Aktor</th>
              <th className="px-6 py-3">Aksi</th>
              <th className="px-6 py-3">Resource</th>
              <th className="px-6 py-3">Detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={5} className="px-6 py-12 text-center text-gray-400">Memuat audit trail...</td></tr>
            ) : entries.length === 0 ? (
              <tr><td colSpan={5} className="px-6 py-12 text-center text-gray-400">Tidak ada entri audit</td></tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50">
                  <td className="px-6 py-3 text-xs text-gray-500">{new Date(entry.timestamp).toLocaleString("id-ID")}</td>
                  <td className="px-6 py-3">
                    <span className="text-xs px-2 py-0.5 bg-gray-100 rounded">{entry.actor_type}</span>
                    <span className="text-xs text-gray-600 ml-1">{entry.actor_id}</span>
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-900 font-medium">{entry.action}</td>
                  <td className="px-6 py-3 text-xs text-gray-500">{entry.resource_type}/{entry.resource_id.slice(0, 8)}</td>
                  <td className="px-6 py-3 text-xs text-gray-400">
                    {entry.details ? JSON.stringify(entry.details).slice(0, 80) : "-"}
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
