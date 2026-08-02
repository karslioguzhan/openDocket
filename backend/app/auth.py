from __future__ import annotations

import uuid
from typing import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin, models
from fastapi_users.authentication import AuthenticationBackend, CookieTransport
from fastapi_users.authentication.strategy.db import DatabaseStrategy
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import AccessToken, User

USER_READ_FIELDS = {"id", "email", "display_name", "is_active", "is_superuser"}


async def get_user_db(session: AsyncSession = Depends(get_session)):
    yield SQLAlchemyUserDatabase(session, User)


async def get_access_token_db(
    session: AsyncSession = Depends(get_session),
):
    yield SQLAlchemyAccessTokenDatabase(session, AccessToken)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = get_settings().secret

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        valid, _ = self.password_helper.verify_and_update(plain_password, hashed_password)
        return valid

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        print(f"User {user.id} has registered.")

    async def on_after_login(
        self, user: User, request: Request | None = None, response=None
    ) -> None:
        print(f"User {user.id} has logged in.")


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


def _build_cookie_transport():
    settings = get_settings()
    return CookieTransport(
        cookie_name="opendocket_session",
        cookie_max_age=settings.session_lifetime_seconds,
        cookie_secure=settings.cookie_secure,
        cookie_httponly=True,
        cookie_samesite="lax",
    )


def _build_strategy(
    access_token_db: SQLAlchemyAccessTokenDatabase = Depends(get_access_token_db),
):
    return DatabaseStrategy(access_token_db, lifetime_seconds=get_settings().session_lifetime_seconds)


auth_backend = AuthenticationBackend(
    name="cookie",
    transport=_build_cookie_transport(),
    get_strategy=_build_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
