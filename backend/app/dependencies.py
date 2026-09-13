from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import current_active_user, current_superuser
from app.db import get_session
from app.models import Contract, Share, User

CONTRACT_LOAD_OPTIONS = (
    selectinload(Contract.files),
    selectinload(Contract.shares).selectinload(Share.user),
    selectinload(Contract.tags),
    selectinload(Contract.counterparty),
    selectinload(Contract.versicherungsnehmer),
)


def accessible_contracts_query(user: User, include_deleted: bool = False):
    stmt = select(Contract).where(
        or_(
            Contract.owner_id == user.id,
            Contract.id.in_(select(Share.contract_id).where(Share.user_id == user.id)),
        )
    )
    if not include_deleted:
        stmt = stmt.where(Contract.deleted_at.is_(None))
    return stmt


async def get_accessible_contract(
    contract_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Contract:
    contract = (
        await session.execute(
            select(Contract)
            .options(*CONTRACT_LOAD_OPTIONS)
            .where(Contract.id == contract_id, Contract.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    if not (contract.owner_id == user.id or await _is_viewer(session, contract.id, user.id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    contract._role = "owner" if contract.owner_id == user.id else "viewer"
    return contract


async def _load_owned_contract(
    session: AsyncSession,
    contract_id: uuid.UUID,
    user: User,
    include_deleted: bool,
) -> Contract:
    stmt = select(Contract).options(*CONTRACT_LOAD_OPTIONS).where(Contract.id == contract_id)
    if not include_deleted:
        stmt = stmt.where(Contract.deleted_at.is_(None))
    contract = (await session.execute(stmt)).scalar_one_or_none()
    if contract is None or contract.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    contract._role = "owner"
    return contract


async def get_owned_contract(
    contract_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Contract:
    """Owner-only access to a live contract (trashed contracts are excluded)."""
    return await _load_owned_contract(session, contract_id, user, include_deleted=False)


async def get_owned_contract_any_state(
    contract_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Contract:
    """Owner-only access to a contract even while it sits in the trash."""
    return await _load_owned_contract(session, contract_id, user, include_deleted=True)


async def _is_viewer(session: AsyncSession, contract_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return bool(
        await session.scalar(
            select(Share.id).where(
                Share.contract_id == contract_id, Share.user_id == user_id
            )
        )
    )


__all__ = [
    "current_active_user",
    "current_superuser",
    "get_session",
    "accessible_contracts_query",
    "get_accessible_contract",
    "get_owned_contract",
    "get_owned_contract_any_state",
]
