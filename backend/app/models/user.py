from __future__ import annotations

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin


class User(SQLAlchemyBaseUserTableUUID, TimestampMixin, Base):
    __tablename__ = "users"

    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    contracts: Mapped[list["Contract"]] = relationship(
        "Contract",
        back_populates="owner",
        foreign_keys="Contract.owner_id",
        passive_deletes=True,
    )
    counterparties: Mapped[list["Counterparty"]] = relationship(
        "Counterparty", back_populates="owner", passive_deletes=True
    )
    tags: Mapped[list["Tag"]] = relationship("Tag", back_populates="owner", passive_deletes=True)
    shares: Mapped[list["Share"]] = relationship("Share", back_populates="user", passive_deletes=True)
