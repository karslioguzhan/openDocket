from __future__ import annotations

from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyBaseAccessTokenTableUUID
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declared_attr, mapped_column

from app.db import Base


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    __tablename__ = "access_tokens"

    @declared_attr
    def user_id(cls):
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("users.id", ondelete="cascade"),
            nullable=False,
        )
