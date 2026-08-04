"""predefined categories

Revision ID: 0002_predefined_categories
Revises: 0001_initial
Create Date: 2026-08-04

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import context, op

revision = "0002_predefined_categories"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

NAME_TO_KEY = {
    "kfz-haftpflicht": "kfz_haftpflicht",
    "kfz_haftpflicht": "kfz_haftpflicht",
    "kfz haftpflicht": "kfz_haftpflicht",
    "kfz-teilkasko": "kfz_teilkasko",
    "kfz-teilkaskoversicherung": "kfz_teilkasko",
    "kfz-vollkasko": "kfz_vollkasko",
    "kfz-vollkaskoversicherung": "kfz_vollkasko",
    "kfz-schutzbrief": "kfz_schutzbrief",
    "autoschutz": "kfz_schutzbrief",
    "motorradversicherung": "motorrad",
    "motorrad": "motorrad",
    "fahrradversicherung": "fahrrad",
    "e-bike-versicherung": "fahrrad",
    "privathaftpflicht": "privathaftpflicht",
    "privathaftpflichtversicherung": "privathaftpflicht",
    "private haftpflicht": "privathaftpflicht",
    "tierhalterhaftpflicht": "tierhalterhaftpflicht",
    "haustierhaftpflicht": "tierhalterhaftpflicht",
    "haus-und-grundbesitzerhaftpflicht": "haus_haftpflicht",
    "haus & grundbesitzerhaftpflicht": "haus_haftpflicht",
    "berufshaftpflicht": "berufshaftpflicht",
    "gesetzliche krankenversicherung": "gesetzliche_kv",
    "gkv": "gesetzliche_kv",
    "private krankenversicherung": "private_kv",
    "pkv": "private_kv",
    "krankenzusatzversicherung": "kv_zusatz",
    "krankenzusatz": "kv_zusatz",
    "zahnzusatzversicherung": "zahnzusatz",
    "zahnzusatz": "zahnzusatz",
    "pflegezusatzversicherung": "pflegezusatz",
    "pflegezusatz": "pflegezusatz",
    "risikolebensversicherung": "risikoleben",
    "risikoleben": "risikoleben",
    "rentenversicherung": "rentenversicherung",
    "kapitallebensversicherung": "rentenversicherung",
    "private altersvorsorge": "altersvorsorge",
    "riester": "altersvorsorge",
    "ruprup": "altersvorsorge",
    "ruerup": "altersvorsorge",
    "berufsunfaehigkeitsversicherung": "berufsunfaehigkeit",
    "berufsunfähigkeitsversicherung": "berufsunfaehigkeit",
    "bu-versicherung": "berufsunfaehigkeit",
    "unfallversicherung": "unfall",
    "private unfallversicherung": "unfall",
    "kinderunfallversicherung": "kinderunfall",
    "insassenunfallversicherung": "insassenunfall",
    "wohngebaeudeversicherung": "wohngebaeude",
    "wohngebäudeversicherung": "wohngebaeude",
    "hausratversicherung": "hausrat",
    "hausrat": "hausrat",
    "elementarschadenversicherung": "elementar",
    "elementar": "elementar",
    "glasversicherung": "glas",
    "rechtsschutzversicherung": "rechtsschutz_privat",
    "privatrechtsschutz": "rechtsschutz_privat",
    "verkehrsrechtsschutz": "rechtsschutz_verkehr",
    "mietrechtsschutz": "rechtsschutz_miet_arbeit",
    "arbeitsrechtsschutz": "rechtsschutz_miet_arbeit",
    "mietvertrag": "mietvertrag",
    "mobilfunk": "mobilfunk_internet",
    "internet": "mobilfunk_internet",
    "strom": "energie",
    "gas": "energie",
    "kredit": "kredit",
    "darlehen": "kredit",
    "mitgliedschaft": "mitgliedschaft",
    "abo": "mitgliedschaft",
    "garantie": "garantie_wartung",
    "wartung": "garantie_wartung",
    "sonstiges": "sonstiges",
    "sonstige": "sonstiges",
}


def _normalize(name: str) -> str:
    return " ".join(name.strip().lower().split())


def upgrade() -> None:
    op.add_column("contracts", sa.Column("category", sa.String(length=40), nullable=True))

    if not context.get_context().as_sql:
        conn = op.get_bind()
        rows = conn.execute(sa.text("SELECT id, name FROM categories")).mappings().all()
        for row in rows:
            key = NAME_TO_KEY.get(_normalize(row["name"]))
            if key is not None:
                conn.execute(
                    sa.text(
                        "UPDATE contracts SET category = :key "
                        "WHERE category_id = :legacy_id AND category IS NULL"
                    ),
                    {"key": key, "legacy_id": str(row["id"])},
                )

    op.execute(
        "ALTER TABLE contracts DROP CONSTRAINT IF EXISTS contracts_category_id_fkey"
    )
    op.drop_column("contracts", "category_id")
    op.drop_table("categories")


def downgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("owner_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "contracts",
        sa.Column(
            "category_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="set null"),
            nullable=True,
        ),
    )
    op.drop_column("contracts", "category")
