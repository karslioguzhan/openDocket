from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.dependencies import current_active_user
from app.models import User
from app.schemas import ExtractedFileOut, ExtractionOut
from app.services.extraction import EXTRACTABLE_EXTENSIONS, parse_contract_documents
from app.storage import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES

router = APIRouter(prefix="/api/contracts", tags=["extraction"])


@router.post("/extract", response_model=ExtractionOut)
async def extract_contract(
    files: list[UploadFile] = File(...),
    user: User = Depends(current_active_user),
):
    """OCR / parse PDF or image uploads and return candidate contract fields."""
    if not files:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No files uploaded.")

    documents: list[tuple[str, bytes]] = []
    for f in files:
        suffix = Path(f.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS or suffix not in EXTRACTABLE_EXTENSIONS:
            raise HTTPException(
                status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                f"Unsupported file type '{suffix or 'unknown'}'. "
                f"Supported for scanning: {', '.join(sorted(EXTRACTABLE_EXTENSIONS))}",
            )
        contents = await f.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File exceeds the 25 MB limit.")
        documents.append((f.filename or "file", contents))

    parsed = parse_contract_documents(documents)
    if not parsed:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No readable text found in the uploaded document(s).",
        )

    return ExtractionOut(
        **parsed,
        files=[
            ExtractedFileOut(
                original_name=name[:255],
                mime_type=ALLOWED_EXTENSIONS[Path(name).suffix.lower()],
                size_bytes=len(data),
            )
            for name, data in documents
        ],
    )
