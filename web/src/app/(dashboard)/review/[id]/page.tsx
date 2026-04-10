"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getHitlReview, submitHitlDecision } from "@/lib/api";
import { getScoreColor, getSeverityColor } from "@/lib/utils";
import type { HitlReviewDetail } from "@/types";

export default function ReviewDetailPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params.id as string;

  const [review, setReview] = useState<HitlReviewDetail | null>(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHitlReview(documentId).then(setReview).catch((e) => setError(e.message));
  }, [documentId]);

  const handleDecision = async (decision: "approved" | "rejected") => {
    setSubmitting(true);
    try {
      await submitHitlDecision(documentId, {
        decision,
        reviewer_id: "a0000000-0000-0000-0000-000000000001",
        reviewer_role: "corp_secretary",
        notes: notes || undefined,
      });
      router.push("/review");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setSubmitting(false);
    }
  };

  if (error) return <div className="bg-red-50 p-6 rounded-xl text-red-700">{error}</div>;
  if (!review) return <div className="text-center text-gray-400 py-12">Memuat data review...</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Review Detail</h1>
          <p className="text-sm text-gray-500 mt-1">Dokumen: {documentId}</p>
        </div>
        <span className="px-3 py-1 bg-amber-100 text-amber-700 rounded-full text-sm font-medium">
          {review.gate.replace(/_/g, " ").toUpperCase()}
        </span>
      </div>

      {/* Scorecard (Gate 4) */}
      {review.scorecard && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Scorecard Kepatuhan</h2>
          <div className="grid grid-cols-4 gap-4">
            {[
              { label: "Struktural", score: review.scorecard.structural },
              { label: "Substantif", score: review.scorecard.substantive },
              { label: "Regulasi", score: review.scorecard.regulatory },
              { label: "Komposit", score: review.scorecard.composite },
            ].map((s) => (
              <div key={s.label} className={`text-center p-4 rounded-xl ${getScoreColor(s.score)}`}>
                <div className="text-2xl font-bold">{s.score.toFixed(0)}</div>
                <div className="text-xs mt-1">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Red Flags (Gate 3) */}
      {review.red_flags && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3">
            Red Flags ({(review.red_flags as Record<string, unknown>).total_count as number || 0})
          </h2>
          {((review.red_flags as Record<string, unknown>).flags as Array<Record<string, string>> || []).map((flag, i) => (
            <div key={i} className="p-3 bg-red-50 rounded-lg mb-2 border-l-4 border-red-500">
              <span className="text-sm font-medium text-red-700">{flag.type}</span>
              <p className="text-sm text-red-600 mt-1">{flag.description}</p>
            </div>
          ))}
        </div>
      )}

      {/* AI Output */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <h2 className="text-lg font-semibold mb-3">Output AI</h2>
        <pre className="bg-gray-50 p-4 rounded-lg text-xs overflow-auto max-h-96">
          {JSON.stringify(review.ai_output, null, 2)}
        </pre>
      </div>

      {/* Deviation Flags */}
      {review.deviation_flags && review.deviation_flags.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
          <h2 className="text-lg font-semibold mb-3">Deviation Flags</h2>
          {review.deviation_flags.map((flag: any, i: number) => (
            <div key={i} className={`p-3 rounded-lg mb-2 ${getSeverityColor(flag.severity || "medium")}`}>
              <span className="text-sm font-medium">[{(flag.severity || "medium").toUpperCase()}]</span>
              <span className="text-sm ml-2">{flag.description || flag.field}</span>
            </div>
          ))}
        </div>
      )}

      {/* Decision Form */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Keputusan Review</h2>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Catatan reviewer (opsional)..."
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4 h-24 resize-none"
        />
        <div className="flex gap-3">
          <button
            onClick={() => handleDecision("approved")}
            disabled={submitting}
            className="flex-1 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {submitting ? "Memproses..." : "Approve"}
          </button>
          <button
            onClick={() => handleDecision("rejected")}
            disabled={submitting}
            className="flex-1 py-3 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}
