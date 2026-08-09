"""add versicherungsnehmer to contracts

Revision ID: 0007_versicherungsnehmer
Revises: 0006_user_demo_seed
Create Date: 2026-08-09

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0007_versicherungsnehmer"
down_revision = "0006_user_demo_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("versicherungsnehmer_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_contracts_versicherungsnehmer_id",
        "contracts",
        ["versicherungsnehmer_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_contracts_versicherungsnehmer_id", table_name="contracts")
    op.drop_column("contracts", "versicherungsnehmer_id")
