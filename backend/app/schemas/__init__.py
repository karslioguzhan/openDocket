from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from fastapi_users import schemas as fu_schemas

from app.models import ContractStatus


class UserCreate(fu_schemas.BaseUserCreate):
    display_name: str | None = Field(default=None, max_length=120)


class UserUpdate(fu_schemas.BaseUserUpdate):
    display_name: str | None = Field(default=None, max_length=120)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str | None = None
    is_active: bool
    is_superuser: bool


class UserAdminUpdate(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = None
    password: str | None = Field(default=None, min_length=8)
    is_active: bool | None = None


class UserSelfUpdate(BaseModel):
    display_name: str | None = None
    current_password: str | None = None
    new_password: str | None = Field(default=None, min_length=8)


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class CounterpartyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = None


class CounterpartyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    notes: str | None = None


class CounterpartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: str | None = None
    phone: str | None = None
    notes: str | None = None
    created_at: datetime


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class TagIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class ContractCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    status: ContractStatus = ContractStatus.draft
    counterparty_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list)
    effective_date: date | None = None
    expiry_date: date | None = None
    notice_days: int | None = Field(default=None, ge=0)
    notes: str | None = None
    value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class ContractUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: ContractStatus | None = None
    counterparty_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    tags: list[str] | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    notice_days: int | None = Field(default=None, ge=0)
    notes: str | None = None
    value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)


class ContractFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class ShareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    display_name: str | None = None
    role: str


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: ContractStatus
    role: str
    owner_id: uuid.UUID
    counterparty: CounterpartyOut | None = None
    category: CategoryOut | None = None
    tags: list[str] = []
    effective_date: date | None = None
    expiry_date: date | None = None
    notice_days: int | None = None
    notes: str | None = None
    value: Decimal | None = None
    currency: str | None = None
    files: list[ContractFileOut] = []
    shares: list[ShareOut] = []
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class ShareCreate(BaseModel):
    email: EmailStr


class DashboardOut(BaseModel):
    expiring_soon: list[ContractOut]
    status_counts: dict[str, int]
    category_counts: list[dict[str, object]]
