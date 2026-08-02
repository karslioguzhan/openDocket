from __future__ import annotations

import io
import json
import uuid
import zipfile
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.dependencies import CONTRACT_LOAD_OPTIONS, current_active_user
from app.models import Contract, User
from app.storage import storage_dir

router = APIRouter(prefix="/api/export", tags=["export"])


def _iso(dt) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    if isinstance(dt, date):
        return dt.isoformat()
    return str(dt)


@router.get("")
async def export_all(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    contracts = (
        await session.execute(
            select(Contract)
            .options(*CONTRACT_LOAD_OPTIONS)
            .where(Contract.owner_id == user.id, Contract.deleted_at.is_(None))
        )
    ).scalars().unique().all()

    manifest = []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for contract in contracts:
            entry = {
                "id": str(contract.id),
                "title": contract.title,
                "status": contract.status.value,
                "effective_date": _iso(contract.effective_date),
                "expiry_date": _iso(contract.expiry_date),
                "notice_days": contract.notice_days,
                "notes": contract.notes,
                "value": str(contract.value) if contract.value is not None else None,
                "currency": contract.currency,
                "created_at": _iso(contract.created_at),
                "updated_at": _iso(contract.updated_at),
                "counterparty": (
                    {
                        "name": contract.counterparty.name,
                        "email": contract.counterparty.email,
                        "phone": contract.counterparty.phone,
                        "notes": contract.counterparty.notes,
                    }
                    if contract.counterparty
                    else None
                ),
                "category": contract.category.name if contract.category else None,
                "tags": [t.name for t in contract.tags],
                "files": [
                    {
                        "stored_name": f.stored_name,
                        "original_name": f.original_name,
                        "mime_type": f.mime_type,
                        "size_bytes": f.size_bytes,
                    }
                    for f in contract.files
                ],
            }
            manifest.append(entry)
            for f in contract.files:
                path = storage_dir() / f.stored_name
                if path.exists():
                    zf.write(path, arcname=f"files/{f.stored_name}")

        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "app": "openDocket",
                    "version": 1,
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "contracts": manifest,
                },
                indent=2,
            ),
        )

    buf.seek(0)
    filename = f"opendocket-export-{date.today().isoformat()}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
