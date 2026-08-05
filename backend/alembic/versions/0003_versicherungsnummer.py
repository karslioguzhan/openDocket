"""add versicherungsnummer to contracts

Revision ID: 0003_versicherungsnummer
Revises: 0002_predefined_categories
Create Date: 2026-08-05

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0003_versicherungsnummer"
down_revision = "0002_predefined_categories"
branch_labels = None
depends_on = None

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _generate() -> str:
    import secrets

    return "VN-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


def upgrade() -> None:
    op.add_column(
        "contracts",
        sa.Column("versicherungsnummer", sa.String(length=40), nullable=True),
    )
    if not context.get_context().as_sql:
        conn = op.get_bind()
        rows = conn.execute(sa.text("SELECT id FROM contracts")).mappings().all()
        for row in rows:
            conn.execute(
                sa.text(
                    "UPDATE contracts SET versicherungsnummer = :vn "
                    "WHERE id = :id AND versicherungsnummer IS NULL"
                ),
                {"vn": _generate(), "id": str(row["id"])},
            )
    op.alter_column("contracts", "versicherungsnummer", nullable=False)
    op.create_index(
        "ix_contracts_versicherungsnummer", "contracts", ["versicherungsnummer"]
    )


def downgrade() -> None:
    op.drop_index("ix_contracts_versicherungsnummer", table_name="contracts")
    op.drop_column("contracts", "versicherungsnummer")
