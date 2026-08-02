from fastapi import APIRouter

from app.auth import auth_backend, fastapi_users

router = APIRouter(prefix="/api/auth", tags=["auth"])

router.include_router(fastapi_users.get_auth_router(auth_backend))
