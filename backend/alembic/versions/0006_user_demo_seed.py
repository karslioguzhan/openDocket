"""add demo_seed_version to users

Revision ID: 0006_user_demo_seed
Revises: 0005_counterparty_type
Create Date: 2026-08-09

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006_user_demo_seed"
down_revision = "0005_counterparty_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "demo_seed_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "demo_seed_version")
