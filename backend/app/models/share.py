from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, TimestampMixin


class ShareRole(str, enum.Enum):
    viewer = "viewer"


class Share(TimestampMixin, Base):
    __tablename__ = "shares"
    __table_args__ = (UniqueConstraint("contract_id", "user_id", name="uq_shares_contract_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="cascade"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="cascade"), nullable=False, index=True
    )
    role: Mapped[ShareRole] = mapped_column(
        Enum(ShareRole, name="share_role"), nullable=False, default=ShareRole.viewer
    )

    contract: Mapped["Contract"] = relationship("Contract", back_populates="shares")
    user: Mapped["User"] = relationship("User", back_populates="shares")
