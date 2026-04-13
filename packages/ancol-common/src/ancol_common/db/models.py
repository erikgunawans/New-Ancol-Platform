"""SQLAlchemy 2.0 ORM models for all database tables."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Users ──


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum(
            "corp_secretary",
            "internal_auditor",
            "komisaris",
            "legal_compliance",
            "contract_manager",
            "business_dev",
            "admin",
            name="user_role",
        ),
        nullable=False,
    )
    google_identity_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    department: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_users_role", "role"),
        Index("idx_users_email", "email"),
    )


# ── MoM Templates ──


class MomTemplate(Base):
    __tablename__ = "mom_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    mom_type: Mapped[str] = mapped_column(
        Enum("regular", "circular", "extraordinary", name="mom_type"), nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date)
    required_sections: Mapped[dict] = mapped_column(JSONB, nullable=False)
    quorum_rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    signature_rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    field_definitions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_templates_date", "effective_from", "effective_until"),)


# ── Documents ──


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(
        Enum("pdf", "scan", "word", "image", name="document_format"), nullable=False
    )
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    gcs_raw_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    gcs_processed_uri: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "processing_ocr",
            "ocr_complete",
            "extracting",
            "hitl_gate_1",
            "researching",
            "hitl_gate_2",
            "comparing",
            "hitl_gate_3",
            "reporting",
            "hitl_gate_4",
            "complete",
            "failed",
            "rejected",
            name="document_status",
        ),
        nullable=False,
        default="pending",
    )
    mom_type: Mapped[str | None] = mapped_column(String(50))
    meeting_date: Mapped[date | None] = mapped_column(Date)
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mom_templates.id"))
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    page_count: Mapped[int | None] = mapped_column(Integer)
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    batch_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("batch_jobs.id"))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    extractions: Mapped[list[Extraction]] = relationship(back_populates="document")

    __table_args__ = (
        Index("idx_documents_status", "status"),
        Index("idx_documents_meeting_date", "meeting_date"),
        Index("idx_documents_uploaded_by", "uploaded_by"),
        Index("idx_documents_batch", "batch_job_id"),
    )


# ── Extractions (Agent 1 output) ──


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    agent_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    structured_mom: Mapped[dict] = mapped_column(JSONB, nullable=False)
    attendees: Mapped[dict] = mapped_column(JSONB, nullable=False)
    resolutions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    performance_data: Mapped[dict | None] = mapped_column(JSONB)
    structural_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    field_confidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    deviation_flags: Mapped[dict | None] = mapped_column(JSONB)
    low_confidence_fields: Mapped[dict | None] = mapped_column(JSONB)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="extractions")

    __table_args__ = (Index("idx_extractions_document", "document_id"),)


# ── Regulatory Contexts (Agent 2 output) ──


class RegulatoryContext(Base):
    __tablename__ = "regulatory_contexts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    extraction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extractions.id"), nullable=False)
    agent_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    regulatory_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False)
    overlap_flags: Mapped[dict | None] = mapped_column(JSONB)
    conflict_flags: Mapped[dict | None] = mapped_column(JSONB)
    corpus_freshness: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_reg_contexts_document", "document_id"),)


# ── Compliance Findings (Agent 3 output) ──


class ComplianceFindingRecord(Base):
    __tablename__ = "compliance_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    regulatory_context_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("regulatory_contexts.id"), nullable=False
    )
    agent_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    findings: Mapped[dict] = mapped_column(JSONB, nullable=False)
    red_flags: Mapped[dict | None] = mapped_column(JSONB)
    consistency_report: Mapped[dict | None] = mapped_column(JSONB)
    substantive_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    regulatory_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_findings_document", "document_id"),)


# ── Reports (Agent 4 output) ──


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    findings_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("compliance_findings.id"), nullable=False
    )
    agent_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_used: Mapped[str] = mapped_column(String(100), nullable=False)
    structural_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    substantive_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    regulatory_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    composite_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    score_weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    corrective_suggestions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    gcs_pdf_uri: Mapped[str | None] = mapped_column(String(1000))
    gcs_excel_uri: Mapped[str | None] = mapped_column(String(1000))
    report_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by_audit: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_by_corpsec: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_visible_to_komisaris: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_reports_document", "document_id"),
        Index("idx_reports_approved", "is_approved"),
    )


# ── HITL Decisions ──


class HitlDecisionRecord(Base):
    __tablename__ = "hitl_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    gate: Mapped[str] = mapped_column(
        Enum("gate_1", "gate_2", "gate_3", "gate_4", name="hitl_gate"), nullable=False
    )
    reviewed_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reviewed_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    decision: Mapped[str] = mapped_column(
        Enum("approved", "rejected", "modified", name="hitl_decision"), nullable=False
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(50), nullable=False)
    original_data: Mapped[dict | None] = mapped_column(JSONB)
    modified_data: Mapped[dict | None] = mapped_column(JSONB)
    modification_summary: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sla_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_sla_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalated_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_hitl_document", "document_id"),
        Index("idx_hitl_gate", "gate"),
        Index("idx_hitl_reviewer", "reviewer_id"),
    )


# ── Audit Trail (immutable, append-only) ──


class AuditTrailRecord(Base):
    __tablename__ = "audit_trail"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str | None] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(100))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_actor", "actor_id"),
    )


# ── Notifications ──


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel: Mapped[str] = mapped_column(
        Enum("email", "in_app", "whatsapp", "push", name="notification_channel"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum("pending", "sent", "failed", "read", name="notification_status"),
        nullable=False,
        default="pending",
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    action_url: Mapped[str | None] = mapped_column(String(1000))
    related_document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id"))
    related_gate: Mapped[str | None] = mapped_column(String(20))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    is_escalation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    original_notification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("notifications.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_notifications_recipient", "recipient_id"),
        Index("idx_notifications_status", "status"),
    )


# ── Batch Jobs ──


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("queued", "running", "paused", "completed", "failed", name="batch_status"),
        nullable=False,
        default="queued",
    )
    concurrency: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    priority_order: Mapped[str] = mapped_column(String(50), default="newest_first", nullable=False)
    total_documents: Mapped[int] = mapped_column(Integer, nullable=False)
    processed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    estimated_completion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BatchItem(Base):
    __tablename__ = "batch_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed", "retrying", name="batch_item_status"),
        nullable=False,
        default="pending",
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_batch_items_job", "batch_job_id"),
        Index("idx_batch_items_status", "status"),
    )


# ── Regulatory Corpus Metadata ──


class RegulationIndex(Base):
    __tablename__ = "regulation_index"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    regulation_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    grace_period_end: Mapped[date | None] = mapped_column(Date)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    vertex_ai_datastore_id: Mapped[str | None] = mapped_column(String(255))
    gcs_source_uri: Mapped[str | None] = mapped_column(String(1000))
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_regulation_effective", "effective_date", "expiry_date"),
        Index("idx_regulation_domain", "domain"),
    )


# ── Related Party Entities ──


class RelatedPartyEntity(Base):
    __tablename__ = "related_party_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_name: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    relationship_description: Mapped[str | None] = mapped_column(Text)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Conflict Precedences ──


class ConflictPrecedence(Base):
    __tablename__ = "conflict_precedences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    regulation_a_id: Mapped[str] = mapped_column(String(100), nullable=False)
    regulation_b_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prevailing_regulation: Mapped[str] = mapped_column(String(100), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Contract Lifecycle Management ──


class ContractTemplate(Base):
    __tablename__ = "contract_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_type: Mapped[str] = mapped_column(
        Enum(
            "nda", "vendor", "sale_purchase", "joint_venture",
            "land_lease", "employment", "sop_board_resolution",
            name="contract_type",
        ),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    required_clauses: Mapped[dict | None] = mapped_column(JSONB)
    optional_clauses: Mapped[dict | None] = mapped_column(JSONB)
    default_terms: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        Index("idx_contracts_status", "status"),
        Index("idx_contracts_type", "contract_type"),
        Index("idx_contracts_expiry", "expiry_date"),
        Index("idx_contracts_uploaded_by", "uploaded_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    contract_number: Mapped[str | None] = mapped_column(String(100), unique=True)
    contract_type: Mapped[str] = mapped_column(
        Enum(
            "nda", "vendor", "sale_purchase", "joint_venture",
            "land_lease", "employment", "sop_board_resolution",
            name="contract_type",
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "draft", "pending_review", "in_review", "approved", "executed",
            "active", "expiring", "expired", "terminated", "amended", "failed",
            name="contract_status",
        ),
        nullable=False,
        default="draft",
    )
    gcs_raw_uri: Mapped[str | None] = mapped_column(String(1000))
    gcs_processed_uri: Mapped[str | None] = mapped_column(String(1000))
    gcs_draft_uri: Mapped[str | None] = mapped_column(String(1000))
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    total_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str] = mapped_column(String(3), default="IDR", nullable=False)
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_level: Mapped[str | None] = mapped_column(
        Enum("high", "medium", "low", name="risk_level", create_type=False),
    )
    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    extraction_data: Mapped[dict | None] = mapped_column(JSONB)
    template_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contract_templates.id"))
    parent_contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    error_message: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    clauses: Mapped[list[ContractClauseRecord]] = relationship(back_populates="contract")
    parties: Mapped[list[ContractPartyRecord]] = relationship(back_populates="contract")
    obligations: Mapped[list[ObligationRecord]] = relationship(back_populates="contract")


class ContractClauseRecord(Base):
    __tablename__ = "contract_clauses"
    __table_args__ = (Index("idx_clauses_contract", "contract_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    clause_number: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    risk_level: Mapped[str | None] = mapped_column(
        Enum("high", "medium", "low", name="risk_level", create_type=False),
    )
    risk_reason: Mapped[str | None] = mapped_column(Text)
    is_from_library: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    library_clause_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clause_library.id"))
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contract: Mapped[Contract] = relationship(back_populates="clauses")


class ContractPartyRecord(Base):
    __tablename__ = "contract_parties"
    __table_args__ = (Index("idx_parties_contract", "contract_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    party_name: Mapped[str] = mapped_column(String(500), nullable=False)
    party_role: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    related_party_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("related_party_entities.id")
    )
    contact_email: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    contract: Mapped[Contract] = relationship(back_populates="parties")


class ObligationRecord(Base):
    __tablename__ = "obligations"
    __table_args__ = (
        Index("idx_obligations_contract", "contract_id"),
        Index("idx_obligations_due_date", "due_date"),
        Index("idx_obligations_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    obligation_type: Mapped[str] = mapped_column(
        Enum(
            "renewal", "reporting", "payment", "termination_notice",
            "deliverable", "compliance_filing",
            name="obligation_type",
        ),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    recurrence: Mapped[str | None] = mapped_column(String(50))
    next_due_date: Mapped[date | None] = mapped_column(Date)
    responsible_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    responsible_party_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "upcoming", "due_soon", "overdue", "fulfilled", "waived",
            name="obligation_status",
        ),
        nullable=False,
        default="upcoming",
    )
    reminder_30d_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_14d_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reminder_7d_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evidence_gcs_uri: Mapped[str | None] = mapped_column(String(1000))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    contract: Mapped[Contract] = relationship(back_populates="obligations")


class ClauseLibrary(Base):
    __tablename__ = "clause_library"
    __table_args__ = (Index("idx_clause_lib_type_category", "contract_type", "clause_category"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_type: Mapped[str] = mapped_column(
        Enum(
            "nda", "vendor", "sale_purchase", "joint_venture",
            "land_lease", "employment", "sop_board_resolution",
            name="contract_type",
            create_type=False,
        ),
        nullable=False,
    )
    clause_category: Mapped[str] = mapped_column(String(100), nullable=False)
    title_id: Mapped[str] = mapped_column(String(500), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(500))
    text_id: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str | None] = mapped_column(Text)
    risk_notes: Mapped[str | None] = mapped_column(Text)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
