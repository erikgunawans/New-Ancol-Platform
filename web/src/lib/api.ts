const API_BASE = process.env.API_BASE_URL || "http://localhost:8080";

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const error = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${error}`);
  }

  return res.json();
}

// Documents
export const getDocuments = (status?: string, limit = 50) =>
  fetchApi<{ documents: import("@/types").DocumentSummary[]; total: number }>(
    `/api/documents?limit=${limit}${status ? `&status=${status}` : ""}`
  );

export const getDocument = (id: string) =>
  fetchApi<import("@/types").DocumentSummary>(`/api/documents/${id}`);

export async function uploadDocument(file: File, momType = "regular", meetingDate?: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mom_type", momType);
  if (meetingDate) formData.append("meeting_date", meetingDate);

  const res = await fetch(`${API_BASE}/api/documents/upload`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

// HITL
export const getHitlQueue = (gate?: string) =>
  fetchApi<{ items: import("@/types").HitlQueueItem[]; total: number }>(
    `/api/hitl/queue${gate ? `?gate=${gate}` : ""}`
  );

export const getHitlReview = (documentId: string) =>
  fetchApi<import("@/types").HitlReviewDetail>(`/api/hitl/review/${documentId}`);

export const submitHitlDecision = (documentId: string, body: {
  decision: string;
  reviewer_id: string;
  reviewer_role: string;
  notes?: string;
  modified_data?: Record<string, unknown>;
}) =>
  fetchApi<{ decision_id: string; next_status: string }>(
    `/api/hitl/decide/${documentId}`,
    { method: "POST", body: JSON.stringify(body) }
  );

// Reports
export const getReports = (approvedOnly = false) =>
  fetchApi<{ reports: import("@/types").ReportSummary[]; total: number }>(
    `/api/reports?approved_only=${approvedOnly}`
  );

export const getReport = (id: string) =>
  fetchApi<Record<string, unknown>>(`/api/reports/${id}`);

// Dashboard
export const getDashboardStats = () =>
  fetchApi<import("@/types").DashboardStats>("/api/dashboard/stats");

// Users
export const getUsers = (role?: string) =>
  fetchApi<{ users: import("@/types").User[]; total: number }>(
    `/api/users${role ? `?role=${role}` : ""}`
  );

// Audit
export const getAuditEntries = (limit = 100) =>
  fetchApi<{ entries: import("@/types").AuditEntry[]; total: number }>(
    `/api/audit?limit=${limit}`
  );

// Batch
export const getBatchJobs = (status?: string) =>
  fetchApi<{ jobs: import("@/types").BatchJobSummary[]; total: number }>(
    `/api/batch${status ? `?status=${status}` : ""}`
  );

export const getBatchJob = (id: string) =>
  fetchApi<import("@/types").BatchJobDetail>(`/api/batch/${id}`);

export const createBatchJob = (body: {
  name: string;
  document_ids: string[];
  concurrency?: number;
  max_retries?: number;
  priority_order?: string;
}) =>
  fetchApi<import("@/types").BatchJobSummary>("/api/batch", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const pauseBatchJob = (id: string) =>
  fetchApi<{ status: string }>(`/api/batch/${id}/pause`, { method: "POST" });

export const resumeBatchJob = (id: string) =>
  fetchApi<{ status: string }>(`/api/batch/${id}/resume`, { method: "POST" });

// Analytics
export const getScoreTrends = (months = 12) =>
  fetchApi<{ trends: import("@/types").ScoreTrendPoint[]; period_type: string }>(
    `/api/analytics/trends?months=${months}`
  );

export const getDashboardTrends = (months = 6) =>
  fetchApi<{ trends: import("@/types").TrendPoint[] }>(
    `/api/dashboard/stats/trends?months=${months}`
  );
