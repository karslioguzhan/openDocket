from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.dependencies import current_active_user
from app.models import Contract, Counterparty, User
from app.schemas import CounterpartyIn, CounterpartyOut, CounterpartyUpdate

router = APIRouter(prefix="/api/counterparties", tags=["counterparties"])


@router.get("", response_model=list[CounterpartyOut])
async def list_counterparties(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(Counterparty).where(Counterparty.owner_id == user.id).order_by(Counterparty.name)
        )
    ).scalars().all()
    return [CounterpartyOut.model_validate(c) for c in rows]


@router.post("", response_model=CounterpartyOut, status_code=status.HTTP_201_CREATED)
async def create_counterparty(
    payload: CounterpartyIn,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    cp = Counterparty(owner_id=user.id, **payload.model_dump())
    session.add(cp)
    await session.commit()
    await session.refresh(cp)
    return CounterpartyOut.model_validate(cp)


@router.get("/{counterparty_id}", response_model=CounterpartyOut)
async def get_counterparty(
    counterparty_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    cp = await session.get(Counterparty, counterparty_id)
    if cp is None or cp.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Counterparty not found.")
    return CounterpartyOut.model_validate(cp)


@router.patch("/{counterparty_id}", response_model=CounterpartyOut)
async def update_counterparty(
    counterparty_id: uuid.UUID,
    payload: CounterpartyUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    cp = await session.get(Counterparty, counterparty_id)
    if cp is None or cp.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Counterparty not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cp, field, value)
    await session.commit()
    await session.refresh(cp)
    return CounterpartyOut.model_validate(cp)


@router.delete("/{counterparty_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_counterparty(
    counterparty_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    cp = await session.get(Counterparty, counterparty_id)
    if cp is None or cp.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Counterparty not found.")
    ref_count = await session.scalar(
        select(func.count(Contract.id)).where(Contract.counterparty_id == cp.id)
    )
    if ref_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Counterparty is referenced by contracts; unlink it first.",
        )
    await session.delete(cp)
    await session.commit()
