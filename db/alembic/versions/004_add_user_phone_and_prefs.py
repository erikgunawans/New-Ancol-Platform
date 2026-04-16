"""Add phone_number and notification_channels to users table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone_number", sa.String(20), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "notification_channels",
            JSONB,
            nullable=True,
            server_default=sa.text("'[\"email\", \"in_app\"]'::jsonb"),
        ),
    )
    op.create_index("idx_users_phone", "users", ["phone_number"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_users_phone", table_name="users")
    op.drop_column("users", "notification_channels")
    op.drop_column("users", "phone_number")
