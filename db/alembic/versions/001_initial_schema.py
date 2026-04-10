"""Initial schema: 15 tables, all enums, indexes, and constraints.

Revision ID: 001
Revises: None
Create Date: 2026-04-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Enum types ──

user_role = sa.Enum(
    "corp_secretary", "internal_auditor", "komisaris", "legal_compliance", "admin",
    name="user_role",
)
mom_type = sa.Enum("regular", "circular", "extraordinary", name="mom_type")
document_format = sa.Enum("pdf", "scan", "word", "image", name="document_format")
document_status = sa.Enum(
    "pending", "processing_ocr", "ocr_complete", "extracting",
    "hitl_gate_1", "researching", "hitl_gate_2", "comparing",
    "hitl_gate_3", "reporting", "hitl_gate_4", "complete", "failed", "rejected",
    name="document_status",
)
hitl_gate = sa.Enum("gate_1", "gate_2", "gate_3", "gate_4", name="hitl_gate")
hitl_decision = sa.Enum("approved", "rejected", "modified", name="hitl_decision")
notification_channel = sa.Enum("email", "in_app", name="notification_channel")
notification_status = sa.Enum("pending", "sent", "failed", "read", name="notification_status")
batch_status = sa.Enum("queued", "running", "paused", "completed", "failed", name="batch_status")
batch_item_status = sa.Enum(
    "pending", "processing", "completed", "failed", "retrying", name="batch_item_status"
)


def upgrade() -> None:
    # Create all enum types
    user_role.create(op.get_bind(), checkfirst=True)
    mom_type.create(op.get_bind(), checkfirst=True)
    document_format.create(op.get_bind(), checkfirst=True)
    document_status.create(op.get_bind(), checkfirst=True)
    hitl_gate.create(op.get_bind(), checkfirst=True)
    hitl_decision.create(op.get_bind(), checkfirst=True)
    notification_channel.create(op.get_bind(), checkfirst=True)
    notification_status.create(op.get_bind(), checkfirst=True)
    batch_status.create(op.get_bind(), checkfirst=True)
    batch_item_status.create(op.get_bind(), checkfirst=True)

    # ── users ──
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("google_identity_id", sa.String(255), unique=True),
        sa.Column("department", sa.String(255)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("manager_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_users_role", "users", ["role"])
    op.create_index("idx_users_email", "users", ["email"])

    # ── mom_templates ──
    op.create_table(
        "mom_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("mom_type", mom_type, nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_until", sa.Date),
        sa.Column("required_sections", JSONB, nullable=False),
        sa.Column("quorum_rules", JSONB, nullable=False),
        sa.Column("signature_rules", JSONB, nullable=False),
        sa.Column("field_definitions", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_templates_date", "mom_templates", ["effective_from", "effective_until"])

    # ── batch_jobs ── (created before documents due to FK)
    op.create_table(
        "batch_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", batch_status, nullable=False, server_default=sa.text("'queued'")),
        sa.Column("concurrency", sa.Integer, nullable=False, server_default=sa.text("10")),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default=sa.text("3")),
        sa.Column("priority_order", sa.String(50), nullable=False, server_default=sa.text("'newest_first'")),
        sa.Column("total_documents", sa.Integer, nullable=False),
        sa.Column("processed_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("estimated_completion", sa.DateTime(timezone=True)),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── documents ──
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("format", document_format, nullable=False),
        sa.Column("file_size_bytes", sa.Integer, nullable=False),
        sa.Column("gcs_raw_uri", sa.String(1000), nullable=False),
        sa.Column("gcs_processed_uri", sa.String(1000)),
        sa.Column("status", document_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("mom_type", sa.String(50)),
        sa.Column("meeting_date", sa.Date),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("mom_templates.id")),
        sa.Column("ocr_confidence", sa.Numeric(5, 2)),
        sa.Column("page_count", sa.Integer),
        sa.Column("is_confidential", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("batch_job_id", UUID(as_uuid=True), sa.ForeignKey("batch_jobs.id")),
        sa.Column("error_message", sa.Text),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_documents_status", "documents", ["status"])
    op.create_index("idx_documents_meeting_date", "documents", ["meeting_date"])
    op.create_index("idx_documents_uploaded_by", "documents", ["uploaded_by"])
    op.create_index("idx_documents_batch", "documents", ["batch_job_id"])

    # ── extractions (Agent 1) ──
    op.create_table(
        "extractions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("structured_mom", JSONB, nullable=False),
        sa.Column("attendees", JSONB, nullable=False),
        sa.Column("resolutions", JSONB, nullable=False),
        sa.Column("performance_data", JSONB),
        sa.Column("structural_score", sa.Numeric(5, 2)),
        sa.Column("field_confidence", JSONB, nullable=False),
        sa.Column("deviation_flags", JSONB),
        sa.Column("low_confidence_fields", JSONB),
        sa.Column("processing_time_ms", sa.Integer),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_extractions_document", "extractions", ["document_id"])

    # ── regulatory_contexts (Agent 2) ──
    op.create_table(
        "regulatory_contexts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("extraction_id", UUID(as_uuid=True), sa.ForeignKey("extractions.id"), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("regulatory_mapping", JSONB, nullable=False),
        sa.Column("overlap_flags", JSONB),
        sa.Column("conflict_flags", JSONB),
        sa.Column("corpus_freshness", JSONB, nullable=False),
        sa.Column("processing_time_ms", sa.Integer),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_reg_contexts_document", "regulatory_contexts", ["document_id"])

    # ── compliance_findings (Agent 3) ──
    op.create_table(
        "compliance_findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("regulatory_context_id", UUID(as_uuid=True), sa.ForeignKey("regulatory_contexts.id"), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("findings", JSONB, nullable=False),
        sa.Column("red_flags", JSONB),
        sa.Column("consistency_report", JSONB),
        sa.Column("substantive_score", sa.Numeric(5, 2)),
        sa.Column("regulatory_score", sa.Numeric(5, 2)),
        sa.Column("processing_time_ms", sa.Integer),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_findings_document", "compliance_findings", ["document_id"])

    # ── reports (Agent 4) ──
    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("findings_id", UUID(as_uuid=True), sa.ForeignKey("compliance_findings.id"), nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("structural_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("substantive_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("regulatory_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("composite_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("score_weights", JSONB, nullable=False),
        sa.Column("corrective_suggestions", JSONB, nullable=False),
        sa.Column("gcs_pdf_uri", sa.String(1000)),
        sa.Column("gcs_excel_uri", sa.String(1000)),
        sa.Column("report_data", JSONB, nullable=False),
        sa.Column("is_approved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("approved_by_audit", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("approved_by_corpsec", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("is_visible_to_komisaris", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("processing_time_ms", sa.Integer),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_reports_document", "reports", ["document_id"])
    op.create_index("idx_reports_approved", "reports", ["is_approved"])

    # ── hitl_decisions ──
    op.create_table(
        "hitl_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("gate", hitl_gate, nullable=False),
        sa.Column("reviewed_entity_type", sa.String(50), nullable=False),
        sa.Column("reviewed_entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("decision", hitl_decision, nullable=False),
        sa.Column("reviewer_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewer_role", sa.String(50), nullable=False),
        sa.Column("original_data", JSONB),
        sa.Column("modified_data", JSONB),
        sa.Column("modification_summary", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("internal_notes", sa.Text),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_sla_breached", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("escalated_to", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("escalated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_hitl_document", "hitl_decisions", ["document_id"])
    op.create_index("idx_hitl_gate", "hitl_decisions", ["gate"])
    op.create_index("idx_hitl_reviewer", "hitl_decisions", ["reviewer_id"])

    # ── audit_trail (immutable, append-only) ──
    op.create_table(
        "audit_trail",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor_type", sa.String(50), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("actor_role", sa.String(50)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=False),
        sa.Column("details", JSONB),
        sa.Column("ip_address", INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("model_used", sa.String(100)),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("processing_time_ms", sa.Integer),
    )
    op.create_index("idx_audit_timestamp", "audit_trail", ["timestamp"])
    op.create_index("idx_audit_resource", "audit_trail", ["resource_type", "resource_id"])
    op.create_index("idx_audit_actor", "audit_trail", ["actor_id"])

    # ── notifications ──
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("recipient_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", notification_channel, nullable=False),
        sa.Column("status", notification_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("action_url", sa.String(1000)),
        sa.Column("related_document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("related_gate", sa.String(20)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("is_escalation", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("original_notification_id", UUID(as_uuid=True), sa.ForeignKey("notifications.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_notifications_recipient", "notifications", ["recipient_id"])
    op.create_index("idx_notifications_status", "notifications", ["status"])

    # ── batch_items ──
    op.create_table(
        "batch_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("batch_job_id", UUID(as_uuid=True), sa.ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("status", batch_item_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_batch_items_job", "batch_items", ["batch_job_id"])
    op.create_index("idx_batch_items_status", "batch_items", ["status"])

    # ── regulation_index ──
    op.create_table(
        "regulation_index",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("regulation_id", sa.String(100), unique=True, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("expiry_date", sa.Date),
        sa.Column("grace_period_end", sa.Date),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("chunk_count", sa.Integer, nullable=False),
        sa.Column("vertex_ai_datastore_id", sa.String(255)),
        sa.Column("gcs_source_uri", sa.String(1000)),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_regulation_effective", "regulation_index", ["effective_date", "expiry_date"])
    op.create_index("idx_regulation_domain", "regulation_index", ["domain"])

    # ── related_party_entities ──
    op.create_table(
        "related_party_entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_name", sa.String(500), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("relationship_description", sa.Text),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_until", sa.Date),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── conflict_precedences ──
    op.create_table(
        "conflict_precedences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("regulation_a_id", sa.String(100), nullable=False),
        sa.Column("regulation_b_id", sa.String(100), nullable=False),
        sa.Column("prevailing_regulation", sa.String(100), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("decided_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("conflict_precedences")
    op.drop_table("related_party_entities")
    op.drop_table("regulation_index")
    op.drop_table("batch_items")
    op.drop_table("notifications")
    op.drop_table("audit_trail")
    op.drop_table("hitl_decisions")
    op.drop_table("reports")
    op.drop_table("compliance_findings")
    op.drop_table("regulatory_contexts")
    op.drop_table("extractions")
    op.drop_table("documents")
    op.drop_table("batch_jobs")
    op.drop_table("mom_templates")
    op.drop_table("users")

    # Drop enum types
    batch_item_status.drop(op.get_bind(), checkfirst=True)
    batch_status.drop(op.get_bind(), checkfirst=True)
    notification_status.drop(op.get_bind(), checkfirst=True)
    notification_channel.drop(op.get_bind(), checkfirst=True)
    hitl_decision.drop(op.get_bind(), checkfirst=True)
    hitl_gate.drop(op.get_bind(), checkfirst=True)
    document_status.drop(op.get_bind(), checkfirst=True)
    document_format.drop(op.get_bind(), checkfirst=True)
    mom_type.drop(op.get_bind(), checkfirst=True)
    user_role.drop(op.get_bind(), checkfirst=True)
