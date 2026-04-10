// Shared TypeScript types mirroring Python Pydantic schemas

export type DocumentStatus =
  | "pending" | "processing_ocr" | "ocr_complete" | "extracting"
  | "hitl_gate_1" | "researching" | "hitl_gate_2" | "comparing"
  | "hitl_gate_3" | "reporting" | "hitl_gate_4" | "complete"
  | "failed" | "rejected";

export type DocumentFormat = "pdf" | "scan" | "word" | "image";
export type MomType = "regular" | "circular" | "extraordinary";
export type Severity = "critical" | "high" | "medium" | "low";
export type HitlGate = "gate_1" | "gate_2" | "gate_3" | "gate_4";
export type HitlDecision = "approved" | "rejected" | "modified";
export type UserRole = "corp_secretary" | "internal_auditor" | "komisaris" | "legal_compliance" | "admin";

export interface DocumentSummary {
  id: string;
  filename: string;
  format: DocumentFormat;
  status: DocumentStatus;
  mom_type?: string;
  meeting_date?: string;
  page_count?: number;
  ocr_confidence?: number;
  created_at: string;
  updated_at: string;
}

export interface HitlQueueItem {
  document_id: string;
  filename: string;
  gate: string;
  status: string;
  meeting_date?: string;
}

export interface HitlReviewDetail {
  document_id: string;
  gate: string;
  ai_output: Record<string, unknown>;
  deviation_flags?: unknown[];
  red_flags?: Record<string, unknown>;
  scorecard?: {
    structural: number;
    substantive: number;
    regulatory: number;
    composite: number;
  };
}

export interface ReportSummary {
  id: string;
  document_id: string;
  filename: string;
  structural_score: number;
  substantive_score: number;
  regulatory_score: number;
  composite_score: number;
  is_approved: boolean;
  pdf_uri?: string;
  excel_uri?: string;
  created_at: string;
}

export interface DashboardStats {
  total_documents: number;
  pending_review: number;
  completed: number;
  failed: number;
  rejected: number;
  avg_composite_score?: number;
  avg_structural_score?: number;
  avg_substantive_score?: number;
  avg_regulatory_score?: number;
  documents_by_status: Record<string, number>;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  department?: string;
  is_active: boolean;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  actor_type: string;
  actor_id: string;
  action: string;
  resource_type: string;
  resource_id: string;
  details?: Record<string, unknown>;
}

// Batch processing types
export type BatchStatus = "queued" | "running" | "paused" | "completed" | "failed";
export type BatchItemStatus = "pending" | "processing" | "completed" | "failed" | "retrying";

export interface BatchJobSummary {
  id: string;
  name: string;
  status: BatchStatus;
  concurrency: number;
  max_retries: number;
  priority_order: string;
  total_documents: number;
  processed_count: number;
  failed_count: number;
  progress_pct: number;
  started_at?: string;
  completed_at?: string;
  estimated_completion?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface BatchItemSummary {
  id: string;
  batch_job_id: string;
  document_id: string;
  filename: string;
  status: BatchItemStatus;
  retry_count: number;
  last_error?: string;
  started_at?: string;
  completed_at?: string;
}

export interface BatchJobDetail {
  job: BatchJobSummary;
  items: BatchItemSummary[];
  status_counts: Record<string, number>;
}

// Analytics types
export interface TrendPoint {
  period: string;
  avg_composite?: number;
  document_count: number;
}

export interface ScoreTrendPoint {
  period: string;
  avg_structural?: number;
  avg_substantive?: number;
  avg_regulatory?: number;
  avg_composite?: number;
  document_count: number;
}
