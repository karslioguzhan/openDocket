from __future__ import annotations

import enum
import secrets
import string
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    Column,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin, utcnow
from datetime import datetime


class ContractStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    expired = "expired"
    terminated = "terminated"


class ContractCategory(str, enum.Enum):
    kfz_haftpflicht = "kfz_haftpflicht"
    kfz_teilkasko = "kfz_teilkasko"
    kfz_vollkasko = "kfz_vollkasko"
    kfz_schutzbrief = "kfz_schutzbrief"
    motorrad = "motorrad"
    fahrrad = "fahrrad"
    privathaftpflicht = "privathaftpflicht"
    tierhalterhaftpflicht = "tierhalterhaftpflicht"
    haus_haftpflicht = "haus_haftpflicht"
    berufshaftpflicht = "berufshaftpflicht"
    gesetzliche_kv = "gesetzliche_kv"
    private_kv = "private_kv"
    kv_zusatz = "kv_zusatz"
    zahnzusatz = "zahnzusatz"
    pflegezusatz = "pflegezusatz"
    risikoleben = "risikoleben"
    rentenversicherung = "rentenversicherung"
    altersvorsorge = "altersvorsorge"
    berufsunfaehigkeit = "berufsunfaehigkeit"
    unfall = "unfall"
    kinderunfall = "kinderunfall"
    insassenunfall = "insassenunfall"
    wohngebaeude = "wohngebaeude"
    hausrat = "hausrat"
    elementar = "elementar"
    glas = "glas"
    rechtsschutz_privat = "rechtsschutz_privat"
    rechtsschutz_verkehr = "rechtsschutz_verkehr"
    rechtsschutz_miet_arbeit = "rechtsschutz_miet_arbeit"
    mietvertrag = "mietvertrag"
    mobilfunk_internet = "mobilfunk_internet"
    energie = "energie"
    kredit = "kredit"
    mitgliedschaft = "mitgliedschaft"
    garantie_wartung = "garantie_wartung"
    sonstiges = "sonstiges"


CATEGORY_GROUPS: dict[ContractCategory, str] = {
    ContractCategory.kfz_haftpflicht: "kfz",
    ContractCategory.kfz_teilkasko: "kfz",
    ContractCategory.kfz_vollkasko: "kfz",
    ContractCategory.kfz_schutzbrief: "kfz",
    ContractCategory.motorrad: "kfz",
    ContractCategory.fahrrad: "kfz",
    ContractCategory.privathaftpflicht: "haftpflicht",
    ContractCategory.tierhalterhaftpflicht: "haftpflicht",
    ContractCategory.haus_haftpflicht: "haftpflicht",
    ContractCategory.berufshaftpflicht: "haftpflicht",
    ContractCategory.gesetzliche_kv: "kranken",
    ContractCategory.private_kv: "kranken",
    ContractCategory.kv_zusatz: "kranken",
    ContractCategory.zahnzusatz: "kranken",
    ContractCategory.pflegezusatz: "kranken",
    ContractCategory.risikoleben: "vorsorge",
    ContractCategory.rentenversicherung: "vorsorge",
    ContractCategory.altersvorsorge: "vorsorge",
    ContractCategory.berufsunfaehigkeit: "vorsorge",
    ContractCategory.unfall: "unfall",
    ContractCategory.kinderunfall: "unfall",
    ContractCategory.insassenunfall: "unfall",
    ContractCategory.wohngebaeude: "sach",
    ContractCategory.hausrat: "sach",
    ContractCategory.elementar: "sach",
    ContractCategory.glas: "sach",
    ContractCategory.rechtsschutz_privat: "rechtsschutz",
    ContractCategory.rechtsschutz_verkehr: "rechtsschutz",
    ContractCategory.rechtsschutz_miet_arbeit: "rechtsschutz",
    ContractCategory.mietvertrag: "sonstige",
    ContractCategory.mobilfunk_internet: "sonstige",
    ContractCategory.energie: "sonstige",
    ContractCategory.kredit: "sonstige",
    ContractCategory.mitgliedschaft: "sonstige",
    ContractCategory.garantie_wartung: "sonstige",
    ContractCategory.sonstiges: "sonstige",
}


contract_tags = Table(
    "contract_tags",
    Base.metadata,
    Column("contract_id", ForeignKey("contracts.id", ondelete="cascade"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="cascade"), primary_key=True),
)


_VN_ALPHABET = string.ascii_uppercase + string.digits
_VN_AMBIGUOUS = {"0", "1", "O", "I", "L"}
_VN_CHARS = "".join(c for c in _VN_ALPHABET if c not in _VN_AMBIGUOUS)


def generate_versicherungsnummer() -> str:
    """Return a human-friendly, collision-resistant insurance number like VN-7K2M4XQ9."""
    return "VN-" + "".join(secrets.choice(_VN_CHARS) for _ in range(8))


class Contract(TimestampMixin, Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[ContractStatus] = mapped_column(
        Enum(ContractStatus, name="contract_status"), nullable=False, default=ContractStatus.draft
    )
    versicherungsnummer: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True, default=generate_versicherungsnummer
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )
    counterparty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparties.id", ondelete="set null"), nullable=True
    )
    category: Mapped[ContractCategory | None] = mapped_column(
        Enum(ContractCategory, name="contract_category", native_enum=False, length=40),
        nullable=True,
        index=True,
    )

    effective_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(Date, nullable=True, index=True)
    notice_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    owner: Mapped["User"] = relationship("User", back_populates="contracts")
    counterparty: Mapped["Counterparty | None"] = relationship("Counterparty", back_populates="contracts")
    tags: Mapped[list["Tag"]] = relationship("Tag", secondary=contract_tags, back_populates="contracts")
    files: Mapped[list["ContractFile"]] = relationship(
        "ContractFile", back_populates="contract", cascade="all, delete-orphan"
    )
    shares: Mapped[list["Share"]] = relationship(
        "Share", back_populates="contract", cascade="all, delete-orphan"
    )


class Counterparty(TimestampMixin, Base):
    __tablename__ = "counterparties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )

    owner: Mapped["User"] = relationship("User", back_populates="counterparties")
    contracts: Mapped[list["Contract"]] = relationship("Contract", back_populates="counterparty")


class Tag(TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_tags_owner_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )

    owner: Mapped["User"] = relationship("User", back_populates="tags")
    contracts: Mapped[list["Contract"]] = relationship(
        "Contract", secondary=contract_tags, back_populates="tags"
    )
