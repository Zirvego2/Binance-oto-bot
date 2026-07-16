"""admin_profiles tablosu

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("admin_id", sa.String(length=36), nullable=False),
        sa.Column("binance_api_key_enc", sa.Text(), nullable=True),
        sa.Column("binance_api_secret_enc", sa.Text(), nullable=True),
        sa.Column("telegram_bot_token_enc", sa.Text(), nullable=True),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        sa.Column("telegram_notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("openai_api_key_enc", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admin_id"),
    )
    op.create_index("ix_admin_profiles_admin_id", "admin_profiles", ["admin_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_profiles_admin_id", table_name="admin_profiles")
    op.drop_table("admin_profiles")
