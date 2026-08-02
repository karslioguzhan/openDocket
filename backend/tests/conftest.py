from __future__ import annotations

import os
import tempfile

os.environ["OPEN_DOCKET_SECRET"] = "test-secret"
os.environ["OPEN_DOCKET_FILE_STORAGE_DIR"] = tempfile.mkdtemp(prefix="opendocket-test-files-")

import httpx
import pytest
import pytest_asyncio
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db as db_module
import app.models  # noqa: F401
from app.auth import UserManager
from app.db import Base
from app.models import User
from app.schemas import UserCreate

TEST_ENGINE = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
)


async def _reset_schema() -> None:
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest_asyncio.fixture(autouse=True)
async def _db():
    await _reset_schema()
    db_module.AsyncSessionLocal = async_sessionmaker(
        TEST_ENGINE, class_=AsyncSession, expire_on_commit=False
    )
    yield


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def make_user():
    async def _make(email: str, password: str = "password123", is_superuser: bool = False) -> User:
        async with db_module.AsyncSessionLocal() as session:
            user_db = SQLAlchemyUserDatabase(session, User)
            manager = UserManager(user_db)
            user = await manager.create(
                UserCreate(
                    email=email,
                    password=password,
                    is_superuser=is_superuser,
                    display_name=email.split("@")[0],
                ),
                safe=False,
            )
            return user

    return _make


@pytest_asyncio.fixture
async def login():
    async def _login(c, email: str, password: str = "password123"):
        resp = await c.post(
            "/api/auth/login",
            data={"username": email, "password": password},
        )
        assert resp.status_code == 204, resp.text
        return resp

    return _login


@pytest_asyncio.fixture
async def owner(make_user, login):
    user = await make_user("owner@example.com")
    return user


@pytest_asyncio.fixture
async def viewer(make_user):
    return await make_user("viewer@example.com")


@pytest_asyncio.fixture
async def admin(make_user):
    return await make_user("admin@example.com", is_superuser=True)
