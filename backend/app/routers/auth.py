from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi_users.authentication.strategy import Strategy
from fastapi_users.manager import BaseUserManager

from app.auth import auth_backend, fastapi_users, get_user_manager
from app.config import get_settings
from app.services.demo import DEMO_EMAIL, DEMO_PASSWORD, ensure_demo

router = APIRouter(prefix="/api/auth", tags=["auth"])

router.include_router(fastapi_users.get_auth_router(auth_backend))


class _Credentials:
    username = DEMO_EMAIL
    password = DEMO_PASSWORD


@router.post("/demo-login")
async def demo_login(
    request: Request,
    user_manager: BaseUserManager = Depends(get_user_manager),
    strategy: Strategy = Depends(auth_backend.get_strategy),
):
    if not get_settings().enable_demo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo login is disabled.")
    await ensure_demo()
    user = await user_manager.authenticate(_Credentials())
    if user is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Demo account could not be created."
        )
    response = await auth_backend.login(strategy, user)
    await user_manager.on_after_login(user, request, response)
    return response
