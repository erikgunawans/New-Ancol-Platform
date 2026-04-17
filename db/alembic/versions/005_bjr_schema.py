"""Add BJR (Business Judgment Rule) orchestration layer.

Creates 12 new tables for StrategicDecision + BJR checklist + artifacts
(DD, FS, SPI, AuditCom, Material Disclosure, Organ Approval) + RKAB/RJPP
registries + Gate 5 dual-approval records. Adds regulatory_regime + layer
columns to regulation_index for dual-regime compliance scoring. Adds 2 new
user roles: dewan_pengawas, direksi.

Revision ID: 005
Revises: 004
Create Date: 2026-04-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── New enum types ──

regulatory_regime = sa.Enum(
    "corporate", "regional_finance", "listing", "internal", name="regulatory_regime"
)
regulation_layer = sa.Enum("uu", "pp", "pergub_dki", "ojk_bei", "internal", name="regulation_layer")

initiative_type = sa.Enum(
    "investment",
    "partnership",
    "capex",
    "divestment",
    "major_contract",
    "rups_item",
    "organizational_change",
    name="initiative_type",
)
decision_status = sa.Enum(
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
)
rkab_approval_status = sa.Enum(
    "draft",
    "direksi_approved",
    "dewas_approved",
    "rups_approved",
    "superseded",
    name="rkab_approval_status",
)
checklist_phase = sa.Enum(
    "pre_decision", "decision", "post_decision", name="checklist_phase"
)
checklist_status = sa.Enum(
    "not_started", "in_progress", "satisfied", "waived", "flagged", name="checklist_status"
)
evidence_type = sa.Enum(
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
)
evidence_relationship = sa.Enum(
    "authorizes", "documents", "supports", "monitors", "discloses", name="evidence_relationship"
)
gate5_final_decision = sa.Enum(
    "pending", "approved", "rejected", name="gate5_final_decision"
)
dd_risk_rating = sa.Enum("low", "medium", "high", "critical", name="dd_risk_rating")
spi_report_type = sa.Enum(
    "routine", "incident", "special_audit", "follow_up", name="spi_report_type"
)
organ_approval_type = sa.Enum("komisaris", "dewas", "rups", name="organ_approval_type")


def upgrade() -> None:
    # ── Extend user_role enum (non-reversible — PostgreSQL limitation) ──
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'dewan_pengawas'")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'direksi'")

    # ── Create new enum types ──
    for e in (
        regulatory_regime,
        regulation_layer,
        initiative_type,
        decision_status,
        rkab_approval_status,
        checklist_phase,
        checklist_status,
        evidence_type,
        evidence_relationship,
        gate5_final_decision,
        dd_risk_rating,
        spi_report_type,
        organ_approval_type,
    ):
        e.create(op.get_bind(), checkfirst=True)

    # ── Extend regulation_index with regime + layer ──
    op.add_column("regulation_index", sa.Column("regulatory_regime", regulatory_regime))
    op.add_column("regulation_index", sa.Column("layer", regulation_layer))
    op.create_index("idx_regulation_regime", "regulation_index", ["regulatory_regime"])
    op.create_index("idx_regulation_layer", "regulation_index", ["layer"])

    # ── RKAB line items (must exist before strategic_decisions FK) ──
    op.create_table(
        "rkab_line_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("fiscal_year", sa.Integer, nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("activity_name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("budget_idr", sa.Numeric(15, 2), nullable=False),
        sa.Column("approval_status", rkab_approval_status, nullable=False, server_default="draft"),
        sa.Column("rups_approval_date", sa.Date),
        sa.Column("approved_by_rups_ref", sa.String(500)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("effective_from", sa.Date),
        sa.Column("effective_until", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_rkab_year_code", "rkab_line_items", ["fiscal_year", "code"], unique=True)
    op.create_index("idx_rkab_year_active", "rkab_line_items", ["fiscal_year", "is_active"])

    # ── RJPP themes ──
    op.create_table(
        "rjpp_themes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("period_start_year", sa.Integer, nullable=False),
        sa.Column("period_end_year", sa.Integer, nullable=False),
        sa.Column("theme_name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("target_metrics", JSONB),
        sa.Column("approval_ref", sa.String(500)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_rjpp_period", "rjpp_themes", ["period_start_year", "period_end_year"])

    # ── Strategic decisions (root entity) ──
    op.create_table(
        "strategic_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("initiative_type", initiative_type, nullable=False),
        sa.Column("status", decision_status, nullable=False, server_default="ideation"),
        sa.Column("rkab_line_id", UUID(as_uuid=True), sa.ForeignKey("rkab_line_items.id")),
        sa.Column("rjpp_theme_id", UUID(as_uuid=True), sa.ForeignKey("rjpp_themes.id")),
        sa.Column("business_owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("legal_owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("value_idr", sa.Numeric(15, 2)),
        sa.Column("bjr_readiness_score", sa.Numeric(5, 2)),
        sa.Column("corporate_compliance_score", sa.Numeric(5, 2)),
        sa.Column("regional_compliance_score", sa.Numeric(5, 2)),
        sa.Column("is_bjr_locked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("locked_by_komisaris_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("locked_by_legal_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("gcs_passport_uri", sa.String(1000)),
        sa.Column("source", sa.String(50), nullable=False, server_default="proactive"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_decisions_status", "strategic_decisions", ["status"])
    op.create_index("idx_decisions_initiative_type", "strategic_decisions", ["initiative_type"])
    op.create_index("idx_decisions_business_owner", "strategic_decisions", ["business_owner_id"])
    op.create_index("idx_decisions_rkab", "strategic_decisions", ["rkab_line_id"])
    op.create_index("idx_decisions_locked", "strategic_decisions", ["is_bjr_locked"])

    # ── BJR Checklist (16 items per decision) ──
    op.create_table(
        "bjr_checklists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("decision_id", UUID(as_uuid=True), sa.ForeignKey("strategic_decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase", checklist_phase, nullable=False),
        sa.Column("item_code", sa.String(50), nullable=False),
        sa.Column("status", checklist_status, nullable=False, server_default="not_started"),
        sa.Column("ai_confidence", sa.Numeric(3, 2)),
        sa.Column("evidence_refs", JSONB),
        sa.Column("regulation_basis", ARRAY(sa.String(100))),
        sa.Column("remediation_note", sa.Text),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_checked_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_checklist_decision_item", "bjr_checklists", ["decision_id", "item_code"], unique=True
    )
    op.create_index("idx_checklist_status", "bjr_checklists", ["status"])

    # ── Decision evidence (polymorphic join) ──
    op.create_table(
        "decision_evidence",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("decision_id", UUID(as_uuid=True), sa.ForeignKey("strategic_decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_type", evidence_type, nullable=False),
        sa.Column("evidence_id", UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", evidence_relationship, nullable=False, server_default="documents"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_evidence_decision", "decision_evidence", ["decision_id"])
    op.create_index("idx_evidence_polymorphic", "decision_evidence", ["evidence_type", "evidence_id"])
    op.create_index(
        "idx_evidence_unique_link",
        "decision_evidence",
        ["decision_id", "evidence_type", "evidence_id", "relationship_type"],
        unique=True,
    )

    # ── Gate 5 dual-approval decisions ──
    op.create_table(
        "bjr_gate5_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("decision_id", UUID(as_uuid=True), sa.ForeignKey("strategic_decisions.id"), nullable=False),
        sa.Column("approver_komisaris_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("komisaris_decided_at", sa.DateTime(timezone=True)),
        sa.Column("komisaris_decision", sa.String(20)),
        sa.Column("komisaris_notes", sa.Text),
        sa.Column("approver_legal_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("legal_decided_at", sa.DateTime(timezone=True)),
        sa.Column("legal_decision", sa.String(20)),
        sa.Column("legal_notes", sa.Text),
        sa.Column("final_decision", gate5_final_decision, nullable=False, server_default="pending"),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_sla_breached", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_gate5_decision", "bjr_gate5_decisions", ["decision_id"])
    op.create_index("idx_gate5_final", "bjr_gate5_decisions", ["final_decision"])

    # ── Due Diligence reports ──
    op.create_table(
        "due_diligence_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("decision_id", UUID(as_uuid=True), sa.ForeignKey("strategic_decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("findings", JSONB),
        sa.Column("risk_rating", dd_risk_rating, nullable=False),
        sa.Column("gcs_uri", sa.String(1000)),
        sa.Column("prepared_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by_legal", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("review_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_dd_decision", "due_diligence_reports", ["decision_id"])

    # ── Feasibility Study reports ──
    op.create_table(
        "feasibility_study_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("decision_id", UUID(as_uuid=True), sa.ForeignKey("strategic_decisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("financial_projections", JSONB),
        sa.Column("rjpp_alignment_theme_id", UUID(as_uuid=True), sa.ForeignKey("rjpp_themes.id")),
        sa.Column("assumptions", JSONB),
        sa.Column("gcs_uri", sa.String(1000)),
        sa.Column("prepared_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by_finance", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("review_date", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_fs_decision", "feasibility_study_reports", ["decision_id"])

    # ── SPI (Sistem Pengendalian Internal) reports ──
    op.create_table(
        "spi_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("report_type", spi_report_type, nullable=False),
        sa.Column("findings", JSONB),
        sa.Column("related_decision_ids", ARRAY(UUID(as_uuid=True))),
        sa.Column("gcs_uri", sa.String(1000)),
        sa.Column("submitted_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sent_to_direksi_at", sa.DateTime(timezone=True)),
        sa.Column("sent_to_audit_committee_at", sa.DateTime(timezone=True)),
        sa.Column("sent_to_dewas_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_spi_period", "spi_reports", ["period_start", "period_end"])
    op.create_index(
        "idx_spi_related_decisions",
        "spi_reports",
        ["related_decision_ids"],
        postgresql_using="gin",
    )

    # ── Audit Committee reports ──
    op.create_table(
        "audit_committee_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_date", sa.Date, nullable=False),
        sa.Column("agenda_items", JSONB),
        sa.Column("decisions_reviewed", ARRAY(UUID(as_uuid=True))),
        sa.Column("findings", sa.Text),
        sa.Column("recommendations", sa.Text),
        sa.Column("gcs_uri", sa.String(1000)),
        sa.Column("secretary_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_auditcom_meeting_date", "audit_committee_reports", ["meeting_date"])
    op.create_index(
        "idx_auditcom_decisions",
        "audit_committee_reports",
        ["decisions_reviewed"],
        postgresql_using="gin",
    )

    # ── Material disclosures (OJK/BEI) ──
    op.create_table(
        "material_disclosures",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("disclosure_type", sa.String(200), nullable=False),
        sa.Column("decision_id", UUID(as_uuid=True), sa.ForeignKey("strategic_decisions.id")),
        sa.Column("ojk_filing_ref", sa.String(200)),
        sa.Column("idx_filing_ref", sa.String(200)),
        sa.Column("submission_date", sa.Date, nullable=False),
        sa.Column("deadline_date", sa.Date, nullable=False),
        sa.Column("is_on_time", sa.Boolean, nullable=False),
        sa.Column("gcs_uri", sa.String(1000)),
        sa.Column("filed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_disclosure_decision", "material_disclosures", ["decision_id"])
    op.create_index("idx_disclosure_ontime", "material_disclosures", ["is_on_time"])

    # ── Organ approvals (Komisaris / Dewas / RUPS) ──
    op.create_table(
        "organ_approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("approval_type", organ_approval_type, nullable=False),
        sa.Column("decision_id", UUID(as_uuid=True), sa.ForeignKey("strategic_decisions.id"), nullable=False),
        sa.Column("approver_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approval_date", sa.Date, nullable=False),
        sa.Column("conditions_text", sa.Text),
        sa.Column("meeting_reference", sa.String(500)),
        sa.Column("gcs_uri", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_organ_approval_decision", "organ_approvals", ["decision_id"])
    op.create_index("idx_organ_approval_type", "organ_approvals", ["approval_type"])


def downgrade() -> None:
    # Drop tables in reverse FK dependency order
    op.drop_table("organ_approvals")
    op.drop_table("material_disclosures")
    op.drop_table("audit_committee_reports")
    op.drop_table("spi_reports")
    op.drop_table("feasibility_study_reports")
    op.drop_table("due_diligence_reports")
    op.drop_table("bjr_gate5_decisions")
    op.drop_table("decision_evidence")
    op.drop_table("bjr_checklists")
    op.drop_table("strategic_decisions")
    op.drop_table("rjpp_themes")
    op.drop_table("rkab_line_items")

    # Remove columns added to regulation_index
    op.drop_index("idx_regulation_layer", table_name="regulation_index")
    op.drop_index("idx_regulation_regime", table_name="regulation_index")
    op.drop_column("regulation_index", "layer")
    op.drop_column("regulation_index", "regulatory_regime")

    # Drop new enum types
    for e in (
        organ_approval_type,
        spi_report_type,
        dd_risk_rating,
        gate5_final_decision,
        evidence_relationship,
        evidence_type,
        checklist_status,
        checklist_phase,
        rkab_approval_status,
        decision_status,
        initiative_type,
        regulation_layer,
        regulatory_regime,
    ):
        e.drop(op.get_bind(), checkfirst=True)

    # NOTE: user_role enum values 'dewan_pengawas' + 'direksi' cannot be
    # removed (PostgreSQL limitation on ALTER TYPE ... DROP VALUE). They
    # remain in the enum type after downgrade — harmless as long as no users
    # reference them.
