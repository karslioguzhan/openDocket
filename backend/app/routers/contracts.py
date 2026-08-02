from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.dependencies import (
    CONTRACT_LOAD_OPTIONS,
    accessible_contracts_query,
    current_active_user,
    get_accessible_contract,
    get_owned_contract,
)
from app.models import Category, Contract, ContractStatus, Counterparty, Share, Tag, User, contract_tags
from app.schemas import (
    ContractCreate,
    ContractOut,
    ContractUpdate,
    ShareCreate,
    ShareOut,
)
from app.services.serializers import contract_to_out

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


async def _resolve_tags(session: AsyncSession, user: User, names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    for name in set(n.strip() for n in names if n.strip()):
        tag = await session.scalar(
            select(Tag).where(Tag.owner_id == user.id, Tag.name == name)
        )
        if tag is None:
            tag = Tag(owner_id=user.id, name=name)
            session.add(tag)
            await session.flush()
        tags.append(tag)
    return tags


async def _validate_refs(session: AsyncSession, user: User, counterparty_id, category_id):
    if counterparty_id is not None:
        cp = await session.get(Counterparty, counterparty_id)
        if cp is None or cp.owner_id != user.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown counterparty.")
    if category_id is not None:
        cat = await session.get(Category, category_id)
        if cat is None or cat.owner_id != user.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown category.")


@router.get("", response_model=list[ContractOut])
async def list_contracts(
    status_filter: ContractStatus | None = Query(default=None, alias="status"),
    category_id: uuid.UUID | None = None,
    counterparty_id: uuid.UUID | None = None,
    tag: str | None = None,
    search: str | None = None,
    expiring_days: int | None = Query(default=None, ge=1, le=365),
    trashed: bool = False,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = accessible_contracts_query(user, include_deleted=trashed)
    if trashed:
        stmt = stmt.where(Contract.owner_id == user.id)
    stmt = (
        stmt.options(*CONTRACT_LOAD_OPTIONS)
        .outerjoin(Counterparty, Contract.counterparty_id == Counterparty.id)
        .outerjoin(Category, Contract.category_id == Category.id)
    )

    if status_filter is not None:
        stmt = stmt.where(Contract.status == status_filter)
    if category_id is not None:
        stmt = stmt.where(Contract.category_id == category_id)
    if counterparty_id is not None:
        stmt = stmt.where(Contract.counterparty_id == counterparty_id)
    if tag:
        stmt = stmt.where(
            Contract.id.in_(
                select(contract_tags.c.contract_id).join(
                    Tag, Tag.id == contract_tags.c.tag_id
                ).where(Tag.owner_id == user.id, Tag.name == tag)
            )
        )
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Contract.title.ilike(like),
                Contract.notes.ilike(like),
                Counterparty.name.ilike(like),
                Category.name.ilike(like),
                Contract.id.in_(
                    select(contract_tags.c.contract_id).join(
                        Tag, Tag.id == contract_tags.c.tag_id
                    ).where(Tag.owner_id == user.id, Tag.name.ilike(like))
                ),
            )
        )
    today = date.today()
    if expiring_days is not None:
        stmt = stmt.where(
            and_(
                Contract.expiry_date.is_not(None),
                Contract.expiry_date >= today,
                Contract.expiry_date <= today + timedelta(days=expiring_days),
            )
        )
    stmt = stmt.order_by(Contract.expiry_date.asc().nulls_last(), Contract.title.asc())

    contracts = (await session.execute(stmt)).scalars().unique().all()
    for c in contracts:
        c._role = "owner" if c.owner_id == user.id else "viewer"
    return [contract_to_out(c) for c in contracts]


@router.post("", response_model=ContractOut, status_code=status.HTTP_201_CREATED)
async def create_contract(
    payload: ContractCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    await _validate_refs(session, user, payload.counterparty_id, payload.category_id)
    contract = Contract(
        owner_id=user.id,
        title=payload.title,
        status=payload.status,
        counterparty_id=payload.counterparty_id,
        category_id=payload.category_id,
        effective_date=payload.effective_date,
        expiry_date=payload.expiry_date,
        notice_days=payload.notice_days,
        notes=payload.notes,
        value=payload.value,
        currency=payload.currency,
    )
    if payload.tags:
        contract.tags = await _resolve_tags(session, user, payload.tags)
    session.add(contract)
    await session.commit()
    await session.refresh(contract, attribute_names=["files", "shares", "tags", "counterparty", "category"])
    contract._role = "owner"
    return contract_to_out(contract)


@router.get("/{contract_id}", response_model=ContractOut)
async def get_contract(
    contract: Contract = Depends(get_accessible_contract),
):
    return contract_to_out(contract)


@router.patch("/{contract_id}", response_model=ContractOut)
async def update_contract(
    payload: ContractUpdate,
    contract: Contract = Depends(get_owned_contract),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    data = payload.model_dump(exclude_unset=True)
    if "counterparty_id" in data or "category_id" in data:
        await _validate_refs(session, user, data.get("counterparty_id"), data.get("category_id"))
    if "tags" in data:
        contract.tags = await _resolve_tags(session, user, data.pop("tags") or [])
    for field, value in data.items():
        setattr(contract, field, value)
    await session.commit()
    await session.refresh(contract, attribute_names=["files", "shares", "tags", "counterparty", "category"])
    contract._role = "owner"
    return contract_to_out(contract)


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract: Contract = Depends(get_owned_contract),
    session: AsyncSession = Depends(get_session),
):
    from app.db import utcnow

    contract.deleted_at = utcnow()
    await session.commit()


@router.post("/{contract_id}/restore", response_model=ContractOut)
async def restore_contract(
    contract: Contract = Depends(get_owned_contract),
    session: AsyncSession = Depends(get_session),
):
    contract.deleted_at = None
    await session.commit()
    contract._role = "owner"
    return contract_to_out(contract)


@router.post("/{contract_id}/duplicate", response_model=ContractOut, status_code=status.HTTP_201_CREATED)
async def duplicate_contract(
    contract: Contract = Depends(get_owned_contract),
    session: AsyncSession = Depends(get_session),
):
    copy = Contract(
        owner_id=contract.owner_id,
        title=f"{contract.title} (copy)",
        status=ContractStatus.draft,
        counterparty_id=contract.counterparty_id,
        category_id=contract.category_id,
        effective_date=contract.effective_date,
        expiry_date=contract.expiry_date,
        notice_days=contract.notice_days,
        notes=contract.notes,
        value=contract.value,
        currency=contract.currency,
    )
    copy.tags = list(contract.tags)
    session.add(copy)
    await session.commit()
    await session.refresh(copy, attribute_names=["files", "shares", "tags", "counterparty", "category"])
    copy._role = "owner"
    return contract_to_out(copy)


@router.post("/{contract_id}/shares", response_model=ShareOut, status_code=status.HTTP_201_CREATED)
async def add_share(
    payload: ShareCreate,
    contract: Contract = Depends(get_owned_contract),
    session: AsyncSession = Depends(get_session),
):
    from app.models import User as UserModel

    target = await session.scalar(
        select(UserModel).where(UserModel.email == payload.email.lower())
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email.")
    if target.id == contract.owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot share a contract with yourself.")
    existing = await session.scalar(
        select(Share).where(Share.contract_id == contract.id, Share.user_id == target.id)
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Contract already shared with this user.")
    share = Share(contract_id=contract.id, user_id=target.id)
    session.add(share)
    await session.commit()
    return ShareOut(
        id=share.id,
        user_id=target.id,
        email=target.email,
        display_name=target.display_name,
        role=share.role.value,
    )


@router.delete("/{contract_id}/shares/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_share(
    user_id: uuid.UUID,
    contract: Contract = Depends(get_owned_contract),
    session: AsyncSession = Depends(get_session),
):
    share = await session.scalar(
        select(Share).where(Share.contract_id == contract.id, Share.user_id == user_id)
    )
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Share not found.")
    await session.delete(share)
    await session.commit()
