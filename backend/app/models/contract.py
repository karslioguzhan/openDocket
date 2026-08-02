from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Date,
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


contract_tags = Table(
    "contract_tags",
    Base.metadata,
    Column("contract_id", ForeignKey("contracts.id", ondelete="cascade"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="cascade"), primary_key=True),
)


class Contract(TimestampMixin, Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[ContractStatus] = mapped_column(
        Enum(ContractStatus, name="contract_status"), nullable=False, default=ContractStatus.draft
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )
    counterparty_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("counterparties.id", ondelete="set null"), nullable=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="set null"), nullable=True
    )

    effective_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(Date, nullable=True, index=True)
    notice_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True, index=True)

    owner: Mapped["User"] = relationship("User", back_populates="contracts")
    counterparty: Mapped["Counterparty | None"] = relationship("Counterparty", back_populates="contracts")
    category: Mapped["Category | None"] = relationship("Category", back_populates="contracts")
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


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_categories_owner_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )

    owner: Mapped["User"] = relationship("User", back_populates="categories")
    contracts: Mapped[list["Contract"]] = relationship("Contract", back_populates="category")


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
