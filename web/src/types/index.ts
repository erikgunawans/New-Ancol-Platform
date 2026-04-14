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
export type UserRole = "corp_secretary" | "internal_auditor" | "komisaris" | "legal_compliance" | "contract_manager" | "business_dev" | "admin";

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

// Contract Lifecycle Management types
export type ContractStatus =
  | "draft" | "pending_review" | "in_review" | "approved" | "executed"
  | "active" | "expiring" | "expired" | "terminated" | "amended" | "failed";

export type ContractType =
  | "nda" | "vendor" | "sale_purchase" | "joint_venture"
  | "land_lease" | "employment" | "sop_board_resolution";

export type RiskLevel = "high" | "medium" | "low";

export type ObligationType =
  | "renewal" | "reporting" | "payment" | "termination_notice"
  | "deliverable" | "compliance_filing";

export type ObligationStatus = "upcoming" | "due_soon" | "overdue" | "fulfilled" | "waived";

export interface ContractSummary {
  id: string;
  title: string;
  contract_number?: string;
  contract_type: ContractType;
  status: ContractStatus;
  effective_date?: string;
  expiry_date?: string;
  total_value?: number;
  currency: string;
  risk_level?: RiskLevel;
  risk_score?: number;
  page_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ContractDetail extends ContractSummary {
  clauses: ContractClauseItem[];
  parties: ContractPartyItem[];
  obligations: ObligationSummary[];
}

export interface ContractClauseItem {
  id: string;
  clause_number: string;
  title: string;
  text: string;
  category?: string;
  risk_level?: RiskLevel;
  risk_reason?: string;
  confidence: number;
}

export interface ContractPartyItem {
  id: string;
  party_name: string;
  party_role: string;
  entity_type: string;
  contact_email?: string;
}

export interface ObligationSummary {
  id: string;
  contract_id: string;
  obligation_type: ObligationType;
  description: string;
  due_date: string;
  recurrence?: string;
  next_due_date?: string;
  responsible_party_name: string;
  responsible_user_id?: string;
  status: ObligationStatus;
  reminder_30d_sent: boolean;
  reminder_14d_sent: boolean;
  reminder_7d_sent: boolean;
  fulfilled_at?: string;
  fulfilled_by?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
}

export interface ContractTemplate {
  id: string;
  name: string;
  contract_type: ContractType;
  version: number;
  description?: string;
  required_clauses?: Record<string, unknown>;
  optional_clauses?: Record<string, unknown>;
  default_terms?: Record<string, unknown>;
  is_active: boolean;
}

export interface ClauseLibraryItem {
  id: string;
  contract_type: ContractType;
  clause_category: string;
  title_id: string;
  title_en?: string;
  text_id: string;
  text_en?: string;
  risk_notes?: string;
  is_mandatory: boolean;
  version: number;
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

// Draft generation types
export interface DraftFormData {
  contract_type: ContractType;
  parties: Array<{
    name: string;
    role: "principal" | "counterparty" | "guarantor";
    entity_type: "internal" | "external" | "related_party";
    contact_email?: string;
  }>;
  key_terms: Record<string, string>;
  clause_overrides?: Array<Record<string, string>>;
  language?: "id" | "en";
}

export interface DraftResult {
  contract_id: string;
  draft_text: string;
  clauses: ContractClauseItem[];
  risk_assessment: Array<Record<string, string>>;
  gcs_draft_uri?: string;
}

export interface DraftPdfResult {
  contract_id: string;
  html: string;
  clauses: ContractClauseItem[];
  risk_assessment: Array<Record<string, string>>;
}
