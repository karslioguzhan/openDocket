from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db import Base, AsyncSessionLocal, engine
from app.models import Contract, User
from app.routers import (
    auth,
    contracts,
    counterparties,
    dashboard,
    export,
    extraction,
    files,
    llm,
    meta,
    users,
)
from app.schemas import UserCreate
from app.services.admin import ensure_admin, purge_trash

CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    await ensure_admin()
    purge_task = asyncio.create_task(purge_trash())
    yield
    purge_task.cancel()


app = FastAPI(title="openDocket", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def csrf_origin_check(request: Request, call_next):
    if request.method not in CSRF_SAFE_METHODS:
        origin = request.headers.get("origin")
        if origin:
            host = request.headers.get("host")
            if host:
                scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
                expected = f"{scheme}://{host}"
            else:
                expected = f"{request.url.scheme}://{request.url.netloc}"
            if origin.rstrip("/") != expected:
                return JSONResponse(
                    status_code=403, content={"detail": "CSRF origin check failed."}
                )
    return await call_next(request)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(contracts.router)
app.include_router(counterparties.router)
app.include_router(meta.router)
app.include_router(extraction.router)
app.include_router(llm.router)
app.include_router(files.router)
app.include_router(dashboard.router)
app.include_router(export.router)
