"""Add CLM tables: contracts, clauses, parties, obligations, clause_library, contract_templates.

Revision ID: 002
Revises: 001
Create Date: 2026-04-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── New enum types ──

contract_type = sa.Enum(
    "nda", "vendor", "sale_purchase", "joint_venture",
    "land_lease", "employment", "sop_board_resolution",
    name="contract_type",
)
contract_status = sa.Enum(
    "draft", "pending_review", "in_review", "approved", "executed",
    "active", "expiring", "expired", "terminated", "amended", "failed",
    name="contract_status",
)
risk_level = sa.Enum("high", "medium", "low", name="risk_level")
obligation_type = sa.Enum(
    "renewal", "reporting", "payment", "termination_notice",
    "deliverable", "compliance_filing",
    name="obligation_type",
)
obligation_status = sa.Enum(
    "upcoming", "due_soon", "overdue", "fulfilled", "waived",
    name="obligation_status",
)


def upgrade() -> None:
    # ── Extend existing enums (non-reversible in PostgreSQL) ──
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'contract_manager'")
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'business_dev'")
    op.execute("ALTER TYPE notification_channel ADD VALUE IF NOT EXISTS 'whatsapp'")
    op.execute("ALTER TYPE notification_channel ADD VALUE IF NOT EXISTS 'push'")

    # ── Create new enum types ──
    contract_type.create(op.get_bind(), checkfirst=True)
    contract_status.create(op.get_bind(), checkfirst=True)
    risk_level.create(op.get_bind(), checkfirst=True)
    obligation_type.create(op.get_bind(), checkfirst=True)
    obligation_status.create(op.get_bind(), checkfirst=True)

    # ── contract_templates (must exist before contracts FK) ──
    op.create_table(
        "contract_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contract_type", contract_type, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("description", sa.Text),
        sa.Column("required_clauses", JSONB),
        sa.Column("optional_clauses", JSONB),
        sa.Column("default_terms", JSONB),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── clause_library (must exist before contract_clauses FK) ──
    op.create_table(
        "clause_library",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("contract_type", contract_type, nullable=False),
        sa.Column("clause_category", sa.String(100), nullable=False),
        sa.Column("title_id", sa.String(500), nullable=False),
        sa.Column("title_en", sa.String(500)),
        sa.Column("text_id", sa.Text, nullable=False),
        sa.Column("text_en", sa.Text),
        sa.Column("risk_notes", sa.Text),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_clause_lib_type_category", "clause_library", ["contract_type", "clause_category"])

    # ── contracts ──
    op.create_table(
        "contracts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("contract_number", sa.String(100), unique=True),
        sa.Column("contract_type", contract_type, nullable=False),
        sa.Column("status", contract_status, nullable=False, server_default="draft"),
        sa.Column("gcs_raw_uri", sa.String(1000)),
        sa.Column("gcs_processed_uri", sa.String(1000)),
        sa.Column("gcs_draft_uri", sa.String(1000)),
        sa.Column("effective_date", sa.Date),
        sa.Column("expiry_date", sa.Date),
        sa.Column("total_value", sa.Numeric(15, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="IDR"),
        sa.Column("is_confidential", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("risk_level", risk_level),
        sa.Column("risk_score", sa.Numeric(5, 2)),
        sa.Column("extraction_data", JSONB),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("contract_templates.id")),
        sa.Column("parent_contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id")),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("error_message", sa.Text),
        sa.Column("page_count", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_contracts_status", "contracts", ["status"])
    op.create_index("idx_contracts_type", "contracts", ["contract_type"])
    op.create_index("idx_contracts_expiry", "contracts", ["expiry_date"])
    op.create_index("idx_contracts_uploaded_by", "contracts", ["uploaded_by"])

    # ── contract_clauses ──
    op.create_table(
        "contract_clauses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("clause_number", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("category", sa.String(100)),
        sa.Column("risk_level", risk_level),
        sa.Column("risk_reason", sa.Text),
        sa.Column("is_from_library", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("library_clause_id", UUID(as_uuid=True), sa.ForeignKey("clause_library.id")),
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_clauses_contract", "contract_clauses", ["contract_id"])

    # ── contract_parties ──
    op.create_table(
        "contract_parties",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("party_name", sa.String(500), nullable=False),
        sa.Column("party_role", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("related_party_entity_id", UUID(as_uuid=True), sa.ForeignKey("related_party_entities.id")),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_parties_contract", "contract_parties", ["contract_id"])

    # ── obligations ──
    op.create_table(
        "obligations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("contract_id", UUID(as_uuid=True), sa.ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("obligation_type", obligation_type, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("recurrence", sa.String(50)),
        sa.Column("next_due_date", sa.Date),
        sa.Column("responsible_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("responsible_party_name", sa.String(255), nullable=False),
        sa.Column("status", obligation_status, nullable=False, server_default="upcoming"),
        sa.Column("reminder_30d_sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reminder_14d_sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reminder_7d_sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("evidence_gcs_uri", sa.String(1000)),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True)),
        sa.Column("fulfilled_by", UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_obligations_contract", "obligations", ["contract_id"])
    op.create_index("idx_obligations_due_date", "obligations", ["due_date"])
    op.create_index("idx_obligations_status", "obligations", ["status"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("obligations")
    op.drop_table("contract_parties")
    op.drop_table("contract_clauses")
    op.drop_table("contracts")
    op.drop_table("clause_library")
    op.drop_table("contract_templates")

    # Drop new enum types
    obligation_status.drop(op.get_bind(), checkfirst=True)
    obligation_type.drop(op.get_bind(), checkfirst=True)
    risk_level.drop(op.get_bind(), checkfirst=True)
    contract_status.drop(op.get_bind(), checkfirst=True)
    contract_type.drop(op.get_bind(), checkfirst=True)

    # NOTE: Cannot remove values from user_role or notification_channel enums
    # in PostgreSQL. The values 'contract_manager', 'business_dev', 'whatsapp',
    # 'push' will remain in the enum types after downgrade. This is a known
    # PostgreSQL limitation. To fully revert, recreate the enum types.
