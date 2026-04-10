"use client";

import { useEffect, useState } from "react";
import { getBatchJobs, pauseBatchJob, resumeBatchJob } from "@/lib/api";
import type { BatchJobSummary, BatchStatus } from "@/types";

const STATUS_COLORS: Record<BatchStatus, string> = {
  queued: "bg-gray-100 text-gray-700",
  running: "bg-blue-100 text-blue-700",
  paused: "bg-amber-100 text-amber-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<BatchStatus, string> = {
  queued: "Antrian",
  running: "Berjalan",
  paused: "Dijeda",
  completed: "Selesai",
  failed: "Gagal",
};

export default function BatchPage() {
  const [jobs, setJobs] = useState<BatchJobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadJobs = () => {
    setLoading(true);
    getBatchJobs(filter || undefined)
      .then((data) => {
        setJobs(data.jobs);
        setTotal(data.total);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const hasActiveJobs = jobs.some((j) =>
    ["queued", "running", "paused"].includes(j.status)
  );

  useEffect(() => {
    loadJobs();
  }, [filter]);

  useEffect(() => {
    if (!hasActiveJobs) return;
    const interval = setInterval(loadJobs, 10000);
    return () => clearInterval(interval);
  }, [hasActiveJobs, filter]);

  const handlePause = async (jobId: string) => {
    await pauseBatchJob(jobId);
    loadJobs();
  };

  const handleResume = async (jobId: string) => {
    await resumeBatchJob(jobId);
    loadJobs();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Batch Processing</h1>
        <div className="text-sm text-gray-500">{total} batch job</div>
      </div>

      {/* Status Filter */}
      <div className="flex gap-2 mb-6">
        {["", "queued", "running", "paused", "completed", "failed"].map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === s
                ? "bg-ancol-500 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {s ? STATUS_LABELS[s as BatchStatus] : "Semua"}
          </button>
        ))}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 text-red-700 text-sm">
          {error}
        </div>
      )}

      {loading && jobs.length === 0 ? (
        <div className="flex items-center justify-center h-40 text-gray-400">
          Memuat batch jobs...
        </div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">Belum ada batch job</p>
          <p className="text-sm mt-1">Buat batch job baru melalui API untuk memproses dokumen historis</p>
        </div>
      ) : (
        <div className="space-y-4">
          {jobs.map((job) => (
            <BatchJobCard
              key={job.id}
              job={job}
              onPause={handlePause}
              onResume={handleResume}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function BatchJobCard({
  job,
  onPause,
  onResume,
}: {
  job: BatchJobSummary;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
}) {
  const remaining = job.total_documents - job.processed_count - job.failed_count;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900">{job.name}</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Dibuat {new Date(job.created_at).toLocaleDateString("id-ID", {
              day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit",
            })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[job.status as BatchStatus]}`}>
            {STATUS_LABELS[job.status as BatchStatus]}
          </span>
          {job.status === "running" && (
            <button
              onClick={() => onPause(job.id)}
              className="px-3 py-1 text-xs bg-amber-50 text-amber-700 rounded-lg hover:bg-amber-100"
            >
              Jeda
            </button>
          )}
          {job.status === "paused" && (
            <button
              onClick={() => onResume(job.id)}
              className="px-3 py-1 text-xs bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100"
            >
              Lanjutkan
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>{job.progress_pct.toFixed(0)}% selesai</span>
          <span>
            {job.processed_count} berhasil / {job.failed_count} gagal / {remaining} tersisa
          </span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
          <div className="h-full flex">
            <div
              className="bg-green-500 transition-all duration-500"
              style={{ width: `${(job.processed_count / Math.max(job.total_documents, 1)) * 100}%` }}
            />
            <div
              className="bg-red-400 transition-all duration-500"
              style={{ width: `${(job.failed_count / Math.max(job.total_documents, 1)) * 100}%` }}
            />
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-3">
        <MiniStat label="Total Dokumen" value={job.total_documents} />
        <MiniStat label="Concurrency" value={job.concurrency} />
        <MiniStat label="Max Retry" value={job.max_retries} />
        <MiniStat label="Prioritas" value={job.priority_order.replace(/_/g, " ")} />
      </div>

      {job.started_at && (
        <div className="mt-3 pt-3 border-t border-gray-100 flex gap-4 text-xs text-gray-500">
          <span>Mulai: {new Date(job.started_at).toLocaleString("id-ID")}</span>
          {job.completed_at && (
            <span>Selesai: {new Date(job.completed_at).toLocaleString("id-ID")}</span>
          )}
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-center">
      <div className="text-lg font-bold text-gray-900">{value}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}
