from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.dependencies import CONTRACT_LOAD_OPTIONS, accessible_contracts_query, current_active_user
from app.models import Category, Contract, User
from app.schemas import ContractOut, DashboardOut
from app.services.serializers import contract_to_out

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
async def dashboard(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    accessible = accessible_contracts_query(user)
    today = date.today()

    expiring_stmt = (
        accessible.where(
            Contract.expiry_date.is_not(None),
            Contract.expiry_date >= today,
            Contract.expiry_date <= today + timedelta(days=90),
        )
        .order_by(Contract.expiry_date.asc())
        .options(*CONTRACT_LOAD_OPTIONS)
    )
    expiring = (await session.execute(expiring_stmt)).scalars().unique().all()

    accessible_ids = accessible.with_only_columns(Contract.id).scalar_subquery()

    status_counts = dict(
        (await session.execute(
            select(Contract.status, func.count(Contract.id)).where(
                Contract.id.in_(accessible_ids)
            ).group_by(Contract.status)
        )).all()
    )

    category_rows = (
        await session.execute(
            select(Category.name, func.count(Contract.id))
            .join(Contract, Contract.category_id == Category.id)
            .where(Contract.id.in_(accessible_ids))
            .group_by(Category.name)
            .order_by(func.count(Contract.id).desc())
        )
    ).all()

    return DashboardOut(
        expiring_soon=[_serialize(c, user.id) for c in expiring],
        status_counts={k.value: v for k, v in status_counts.items()},
        category_counts=[{"name": name, "count": count} for name, count in category_rows],
    )


def _serialize(contract: Contract, user_id) -> ContractOut:
    contract._role = "owner" if contract.owner_id == user_id else "viewer"
    return contract_to_out(contract)
