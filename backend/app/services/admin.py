from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.auth import UserManager
from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models import Contract, User
from app.schemas import UserCreate
from app.storage import storage_dir


async def ensure_admin() -> None:
    settings = get_settings()
    if not (settings.admin_email and settings.admin_password):
        return
    async with AsyncSessionLocal() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(user_db)
        existing = await user_db.get_by_email(settings.admin_email.lower())
        if existing is not None:
            return
        await manager.create(
            UserCreate(
                email=settings.admin_email,
                password=settings.admin_password,
                is_superuser=settings.admin_is_superuser,
                display_name="Admin",
            ),
            safe=False,
        )


async def _purge_once() -> int:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.trash_purge_days)
    async with AsyncSessionLocal() as session:
        contracts = (
            await session.execute(
                select(Contract)
                .options(selectinload(Contract.files))
                .where(Contract.deleted_at.is_not(None), Contract.deleted_at < cutoff)
            )
        ).scalars().all()
        for contract in contracts:
            for record in contract.files:
                path = storage_dir() / record.stored_name
                if path.exists():
                    path.unlink()
            await session.delete(contract)
        await session.commit()
        return len(contracts)


async def purge_trash() -> None:
    settings = get_settings()
    while True:
        try:
            count = await _purge_once()
            if count:
                print(f"Purged {count} contract(s) from trash.")
        except Exception as exc:  # pragma: no cover
            print(f"Trash purge failed: {exc}")
        await asyncio.sleep(24 * 60 * 60)
