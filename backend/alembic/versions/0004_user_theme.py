"""add theme to users

Revision ID: 0004_user_theme
Revises: 0003_versicherungsnummer
Create Date: 2026-08-09

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004_user_theme"
down_revision = "0003_versicherungsnummer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("theme", sa.String(length=10), nullable=False, server_default="light"),
    )


def downgrade() -> None:
    op.drop_column("users", "theme")
