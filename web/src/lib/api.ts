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

// Contracts
export const getContracts = (status?: string, contractType?: string, limit = 50) =>
  fetchApi<{ contracts: import("@/types").ContractSummary[]; total: number }>(
    `/api/contracts?limit=${limit}${status ? `&status=${status}` : ""}${contractType ? `&contract_type=${contractType}` : ""}`
  );

export const getContract = (id: string) =>
  fetchApi<import("@/types").ContractSummary>(`/api/contracts/${id}`);

export async function createContract(file: File, title: string, contractType = "vendor", contractNumber?: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", title);
  formData.append("contract_type", contractType);
  if (contractNumber) formData.append("contract_number", contractNumber);

  const res = await fetch(`${API_BASE}/api/contracts`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export const updateContract = (id: string, body: Record<string, unknown>) =>
  fetchApi<import("@/types").ContractSummary>(`/api/contracts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const transitionContractStatus = (id: string, newStatus: string) =>
  fetchApi<{ contract_id: string; new_status: string }>(
    `/api/contracts/${id}/status`,
    { method: "POST", body: JSON.stringify({ new_status: newStatus }) }
  );

export const getContractClauses = (id: string) =>
  fetchApi<{ contract_id: string; clauses: import("@/types").ContractClauseItem[] }>(
    `/api/contracts/${id}/clauses`
  );

export const getContractRisk = (id: string) =>
  fetchApi<{ contract_id: string; risk_level: string; risk_score: number | null }>(
    `/api/contracts/${id}/risk`
  );

// Obligations
export const getObligations = (contractId?: string, status?: string, limit = 50) =>
  fetchApi<{ obligations: import("@/types").ObligationSummary[]; total: number }>(
    `/api/obligations?limit=${limit}${contractId ? `&contract_id=${contractId}` : ""}${status ? `&status=${status}` : ""}`
  );

export const getUpcomingObligations = (days = 30) =>
  fetchApi<{ upcoming: import("@/types").ObligationSummary[]; total: number }>(
    `/api/obligations/upcoming?days=${days}`
  );

export const fulfillObligation = (id: string, fulfilledBy: string, evidenceUri?: string) =>
  fetchApi<{ obligation_id: string; status: string }>(
    `/api/obligations/${id}/fulfill`,
    { method: "POST", body: JSON.stringify({ fulfilled_by: fulfilledBy, evidence_gcs_uri: evidenceUri }) }
  );

// Drafting
export const getDraftTemplates = (contractType?: string) =>
  fetchApi<{ templates: import("@/types").ContractTemplate[]; total: number }>(
    `/api/drafting/templates${contractType ? `?contract_type=${contractType}` : ""}`
  );

export const getClauseLibrary = (contractType?: string, category?: string) =>
  fetchApi<{ clauses: import("@/types").ClauseLibraryItem[]; total: number }>(
    `/api/drafting/clause-library?${contractType ? `contract_type=${contractType}&` : ""}${category ? `category=${category}` : ""}`
  );

// Analytics
export const getScoreTrends = (months = 12) =>
  fetchApi<{ trends: import("@/types").ScoreTrendPoint[]; period_type: string }>(
    `/api/analytics/trends?months=${months}`
  );

export const getDashboardTrends = (months = 6) =>
  fetchApi<{ trends: import("@/types").TrendPoint[] }>(
    `/api/dashboard/stats/trends?months=${months}`
  );
