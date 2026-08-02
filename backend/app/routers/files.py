from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import current_active_user, get_accessible_contract, get_owned_contract
from app.models import Contract, ContractFile, User
from app.schemas import ContractFileOut
from app.storage import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, storage_dir

router = APIRouter(prefix="/api", tags=["files"])


@router.post(
    "/contracts/{contract_id}/files",
    response_model=ContractFileOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    contract_id: uuid.UUID,
    file: UploadFile,
    contract: Contract = Depends(get_owned_contract),
    session: AsyncSession = Depends(get_session),
):
    original = Path(file.filename or "file")
    suffix = original.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "File exceeds the 25 MB limit.",
        )
    stored = f"{uuid.uuid4().hex}{suffix}"
    (storage_dir() / stored).write_bytes(contents)
    record = ContractFile(
        contract_id=contract.id,
        original_name=original.name[:255],
        stored_name=stored,
        mime_type=ALLOWED_EXTENSIONS[suffix],
        size_bytes=len(contents),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return ContractFileOut.model_validate(record)


@router.get("/contracts/{contract_id}/files/{file_id}")
async def download_file(
    contract_id: uuid.UUID,
    file_id: uuid.UUID,
    contract: Contract = Depends(get_accessible_contract),
    session: AsyncSession = Depends(get_session),
):
    record = await session.scalar(
        select(ContractFile).where(ContractFile.id == file_id, ContractFile.contract_id == contract.id)
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    path = storage_dir() / record.stored_name
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File missing on disk.")
    return FileResponse(
        path,
        media_type=record.mime_type,
        filename=record.original_name,
        content_disposition_type="attachment",
    )


@router.delete(
    "/contracts/{contract_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    contract_id: uuid.UUID,
    file_id: uuid.UUID,
    contract: Contract = Depends(get_owned_contract),
    session: AsyncSession = Depends(get_session),
):
    record = await session.scalar(
        select(ContractFile).where(ContractFile.id == file_id, ContractFile.contract_id == contract.id)
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found.")
    path = storage_dir() / record.stored_name
    if path.exists():
        path.unlink()
    await session.delete(record)
    await session.commit()
