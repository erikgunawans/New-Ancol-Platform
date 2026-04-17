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
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
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
            "dewan_pengawas",
            "direksi",
            "admin",
            name="user_role",
        ),
        nullable=False,
    )
    google_identity_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    department: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # MFA
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(String(500))
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    mfa_backup_codes_encrypted: Mapped[str | None] = mapped_column(Text)
    mfa_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Notifications
    phone_number: Mapped[str | None] = mapped_column(String(20))
    notification_channels: Mapped[list | None] = mapped_column(
        JSONB, server_default='["email", "in_app"]'
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_users_role", "role"),
        Index("idx_users_email", "email"),
        Index("idx_users_phone", "phone_number", unique=True),
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
    # BJR additions — drives dual-regime filtering + authority-rank sort
    regulatory_regime: Mapped[str | None] = mapped_column(
        Enum(
            "corporate",
            "regional_finance",
            "listing",
            "internal",
            name="regulatory_regime",
        ),
    )
    layer: Mapped[str | None] = mapped_column(
        Enum("uu", "pp", "pergub_dki", "ojk_bei", "internal", name="regulation_layer"),
    )
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
        Index("idx_regulation_regime", "regulatory_regime"),
        Index("idx_regulation_layer", "layer"),
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
            "nda",
            "vendor",
            "sale_purchase",
            "joint_venture",
            "land_lease",
            "employment",
            "sop_board_resolution",
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
            "nda",
            "vendor",
            "sale_purchase",
            "joint_venture",
            "land_lease",
            "employment",
            "sop_board_resolution",
            name="contract_type",
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "draft",
            "pending_review",
            "in_review",
            "approved",
            "executed",
            "active",
            "expiring",
            "expired",
            "terminated",
            "amended",
            "failed",
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
            "renewal",
            "reporting",
            "payment",
            "termination_notice",
            "deliverable",
            "compliance_filing",
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
            "upcoming",
            "due_soon",
            "overdue",
            "fulfilled",
            "waived",
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
            "nda",
            "vendor",
            "sale_purchase",
            "joint_venture",
            "land_lease",
            "employment",
            "sop_board_resolution",
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


# ══════════════════════════════════════════════════════════════════════════════
# BJR (Business Judgment Rule) — decision-level defensibility layer
# ══════════════════════════════════════════════════════════════════════════════
# 12 new tables implementing the UU PT Pasal 97(5) + PP 23/2022 proof chain.
# StrategicDecision is the root; all other tables link to it as evidence.
# ══════════════════════════════════════════════════════════════════════════════


# ── RKAB / RJPP registries (created first — referenced by StrategicDecision FK) ──


class RKABLineItem(Base):
    """Annual business plan line item. A decision outside approved RKAB voids BJR."""

    __tablename__ = "rkab_line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    activity_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    budget_idr: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    approval_status: Mapped[str] = mapped_column(
        Enum(
            "draft",
            "direksi_approved",
            "dewas_approved",
            "rups_approved",
            "superseded",
            name="rkab_approval_status",
        ),
        nullable=False,
        default="draft",
    )
    rups_approval_date: Mapped[date | None] = mapped_column(Date)
    approved_by_rups_ref: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_rkab_year_code", "fiscal_year", "code", unique=True),
        Index("idx_rkab_year_active", "fiscal_year", "is_active"),
    )


class RJPPTheme(Base):
    """5-year long-term plan theme. Strategic decisions align to an RJPP theme."""

    __tablename__ = "rjpp_themes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_end_year: Mapped[int] = mapped_column(Integer, nullable=False)
    theme_name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_metrics: Mapped[dict | None] = mapped_column(JSONB)
    approval_ref: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_rjpp_period", "period_start_year", "period_end_year"),)


# ── StrategicDecision (BJR root entity) ──


class StrategicDecision(Base):
    """Root BJR entity — a business initiative that aggregates evidence.

    Corresponds to a 'strategic business decision' under UU PT Pasal 97(5).
    One Decision = 1 RKAB line + 1 Feasibility Study + 1 Due Diligence +
    N MoMs + N Contracts + post-decision monitoring reports.
    """

    __tablename__ = "strategic_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    initiative_type: Mapped[str] = mapped_column(
        Enum(
            "investment",
            "partnership",
            "capex",
            "divestment",
            "major_contract",
            "rups_item",
            "organizational_change",
            name="initiative_type",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "ideation",
            "dd_in_progress",
            "fs_in_progress",
            "rkab_verified",
            "board_proposed",
            "organ_approval_pending",
            "approved",
            "executing",
            "monitoring",
            "bjr_gate_5",
            "bjr_locked",
            "archived",
            "rejected",
            "cancelled",
            name="decision_status",
        ),
        nullable=False,
        default="ideation",
    )
    rkab_line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rkab_line_items.id"))
    rjpp_theme_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rjpp_themes.id"))
    business_owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    legal_owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    value_idr: Mapped[float | None] = mapped_column(Numeric(15, 2))
    # Scoring
    bjr_readiness_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    corporate_compliance_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    regional_compliance_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    # Gate 5 lock state
    is_bjr_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by_komisaris_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    locked_by_legal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    gcs_passport_uri: Mapped[str | None] = mapped_column(String(1000))
    # Retroactive vs proactive source flag
    source: Mapped[str] = mapped_column(String(50), default="proactive", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_decisions_status", "status"),
        Index("idx_decisions_initiative_type", "initiative_type"),
        Index("idx_decisions_business_owner", "business_owner_id"),
        Index("idx_decisions_rkab", "rkab_line_id"),
        Index("idx_decisions_locked", "is_bjr_locked"),
    )


# ── BJR Checklist (16 items per decision) ──


class BJRChecklistItemRecord(Base):
    """One of 16 BJR proof items per decision. `item_code` is a stable contract."""

    __tablename__ = "bjr_checklists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategic_decisions.id", ondelete="CASCADE"), nullable=False
    )
    phase: Mapped[str] = mapped_column(
        Enum("pre_decision", "decision", "post_decision", name="checklist_phase"),
        nullable=False,
    )
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "not_started",
            "in_progress",
            "satisfied",
            "waived",
            "flagged",
            name="checklist_status",
        ),
        nullable=False,
        default="not_started",
    )
    ai_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2))
    evidence_refs: Mapped[list | None] = mapped_column(JSONB)
    regulation_basis: Mapped[list | None] = mapped_column(ARRAY(String(100)))
    remediation_note: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_checklist_decision_item", "decision_id", "item_code", unique=True),
        Index("idx_checklist_status", "status"),
    )


# ── Decision Evidence (polymorphic join) ──


class DecisionEvidenceRecord(Base):
    """Polymorphic link between a StrategicDecision and its evidence artifacts."""

    __tablename__ = "decision_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategic_decisions.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(
        Enum(
            "mom",
            "contract",
            "dd_report",
            "fs_report",
            "spi_report",
            "audit_committee_report",
            "ojk_disclosure",
            "organ_approval",
            "rkab_line",
            "rjpp_theme",
            name="evidence_type",
        ),
        nullable=False,
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(
        Enum(
            "authorizes",
            "documents",
            "supports",
            "monitors",
            "discloses",
            name="evidence_relationship",
        ),
        nullable=False,
        default="documents",
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_evidence_decision", "decision_id"),
        Index("idx_evidence_polymorphic", "evidence_type", "evidence_id"),
        Index(
            "idx_evidence_unique_link",
            "decision_id",
            "evidence_type",
            "evidence_id",
            "relationship_type",
            unique=True,
        ),
    )


# ── Gate 5 dual-approval (separate from hitl_decisions — decision-scoped) ──


class BJRGate5Decision(Base):
    """Gate 5 = final BJR sign-off. Requires dual approval: Komisaris + Legal.

    Distinct from HitlDecisionRecord because Gate 5 is decision-scoped, not
    document-scoped, and uses dual-approver columns rather than two rows.
    """

    __tablename__ = "bjr_gate5_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategic_decisions.id"), nullable=False
    )
    # Komisaris half
    approver_komisaris_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    komisaris_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    komisaris_decision: Mapped[str | None] = mapped_column(String(20))  # approved | rejected
    komisaris_notes: Mapped[str | None] = mapped_column(Text)
    # Legal half
    approver_legal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    legal_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legal_decision: Mapped[str | None] = mapped_column(String(20))  # approved | rejected
    legal_notes: Mapped[str | None] = mapped_column(Text)
    # Final state
    final_decision: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", name="gate5_final_decision"),
        nullable=False,
        default="pending",
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_sla_breached: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # One Gate 5 per decision — prevents duplicate rows under concurrent half-approvals.
        Index("idx_gate5_decision", "decision_id", unique=True),
        Index("idx_gate5_final", "final_decision"),
    )


# ── BJR Artifacts: Due Diligence, Feasibility Study, SPI, Audit Committee,
#    Material Disclosure, Organ Approval ──


class DueDiligenceReport(Base):
    """Due Diligence report — BJR pre-decision evidence (PD-01-DD)."""

    __tablename__ = "due_diligence_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategic_decisions.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    findings: Mapped[dict | None] = mapped_column(JSONB)
    risk_rating: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "critical", name="dd_risk_rating"),
        nullable=False,
    )
    gcs_uri: Mapped[str | None] = mapped_column(String(1000))
    prepared_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by_legal: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    review_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_dd_decision", "decision_id"),)


class FeasibilityStudyReport(Base):
    """Feasibility Study — BJR pre-decision evidence (PD-02-FS)."""

    __tablename__ = "feasibility_study_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategic_decisions.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    financial_projections: Mapped[dict | None] = mapped_column(JSONB)
    rjpp_alignment_theme_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rjpp_themes.id"))
    assumptions: Mapped[dict | None] = mapped_column(JSONB)
    gcs_uri: Mapped[str | None] = mapped_column(String(1000))
    prepared_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by_finance: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    review_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_fs_decision", "decision_id"),)


class SPIReport(Base):
    """Sistem Pengendalian Internal (Internal Control) report — POST-13-SPI evidence."""

    __tablename__ = "spi_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    report_type: Mapped[str] = mapped_column(
        Enum("routine", "incident", "special_audit", "follow_up", name="spi_report_type"),
        nullable=False,
    )
    findings: Mapped[dict | None] = mapped_column(JSONB)
    related_decision_ids: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    gcs_uri: Mapped[str | None] = mapped_column(String(1000))
    submitted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    sent_to_direksi_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_to_audit_committee_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_to_dewas_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_spi_period", "period_start", "period_end"),
        Index("idx_spi_related_decisions", "related_decision_ids", postgresql_using="gin"),
    )


class AuditCommitteeReport(Base):
    """Komite Audit meeting report — POST-14-AUDITCOM evidence."""

    __tablename__ = "audit_committee_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    agenda_items: Mapped[list | None] = mapped_column(JSONB)
    decisions_reviewed: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    findings: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text)
    gcs_uri: Mapped[str | None] = mapped_column(String(1000))
    secretary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_auditcom_meeting_date", "meeting_date"),
        Index("idx_auditcom_decisions", "decisions_reviewed", postgresql_using="gin"),
    )


class MaterialDisclosure(Base):
    """OJK/BEI material disclosure log — D-11-DISCLOSE evidence."""

    __tablename__ = "material_disclosures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    disclosure_type: Mapped[str] = mapped_column(String(200), nullable=False)
    decision_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategic_decisions.id"))
    ojk_filing_ref: Mapped[str | None] = mapped_column(String(200))
    idx_filing_ref: Mapped[str | None] = mapped_column(String(200))
    submission_date: Mapped[date] = mapped_column(Date, nullable=False)
    deadline_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_on_time: Mapped[bool] = mapped_column(Boolean, nullable=False)
    gcs_uri: Mapped[str | None] = mapped_column(String(1000))
    filed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_disclosure_decision", "decision_id"),
        Index("idx_disclosure_ontime", "is_on_time"),
    )


class OrganApproval(Base):
    """Komisaris / Dewan Pengawas / RUPS approval record — D-10-ORGAN evidence."""

    __tablename__ = "organ_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_type: Mapped[str] = mapped_column(
        Enum("komisaris", "dewas", "rups", name="organ_approval_type"),
        nullable=False,
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategic_decisions.id"), nullable=False
    )
    approver_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    approval_date: Mapped[date] = mapped_column(Date, nullable=False)
    conditions_text: Mapped[str | None] = mapped_column(Text)
    meeting_reference: Mapped[str | None] = mapped_column(String(500))
    gcs_uri: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_organ_approval_decision", "decision_id"),
        Index("idx_organ_approval_type", "approval_type"),
    )
