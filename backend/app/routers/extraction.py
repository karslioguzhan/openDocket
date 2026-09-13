from __future__ import annotations

from functools import partial
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.dependencies import current_active_user
from app.models import User
from app.schemas import ExtractedFileOut, ExtractionOut
from app.services.extraction import EXTRACTABLE_EXTENSIONS, parse_contract_documents
from app.storage import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES

router = APIRouter(prefix="/api/contracts", tags=["extraction"])


@router.post("/extract", response_model=ExtractionOut)
async def extract_contract(
    files: list[UploadFile] = File(...),
    llm_base_url: str | None = Form(default=None),
    llm_api_key: str | None = Form(default=None),
    llm_model: str | None = Form(default=None),
    llm_vision: str | None = Form(default=None),
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

    llm_config = {
        key: value.strip()
        for key, value in (
            ("base_url", llm_base_url),
            ("api_key", llm_api_key),
            ("model", llm_model),
        )
        if value and value.strip()
    }
    use_vision = (llm_vision or "").strip().lower() in {"1", "true", "yes", "on"}
    # OCR and the provider call are blocking; keep them off the event loop.
    parsed = await anyio.to_thread.run_sync(
        partial(
            parse_contract_documents,
            documents,
            llm_config=llm_config or None,
            use_vision=use_vision,
        )
    )
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
