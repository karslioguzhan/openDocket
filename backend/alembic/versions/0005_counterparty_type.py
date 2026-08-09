"""add type to counterparties

Revision ID: 0005_counterparty_type
Revises: 0004_user_theme
Create Date: 2026-08-09

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0005_counterparty_type"
down_revision = "0004_user_theme"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "counterparties",
        sa.Column(
            "type",
            sa.Enum(
                "company",
                "person",
                name="counterparty_type",
                native_enum=False,
                length=20,
            ),
            nullable=False,
            server_default="company",
        ),
    )


def downgrade() -> None:
    op.drop_column("counterparties", "type")
