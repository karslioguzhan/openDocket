from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi_users import exceptions
from fastapi_users.manager import BaseUserManager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import current_active_user, get_user_manager
from app.db import get_session
from app.dependencies import current_superuser
from app.models import User
from app.schemas import ChangePassword, UserAdminUpdate, UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(current_active_user)):
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_me(
    request: Request,
    payload: UserAdminUpdate,
    user: User = Depends(current_active_user),
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    if payload.password is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Use /api/users/me/change-password to change your own password.",
        )
    update = UserUpdate(**payload.model_dump(exclude_unset=True))
    user = await user_manager.update(update, user, safe=True, request=request)
    return UserRead.model_validate(user)


@router.post("/me/change-password", response_model=UserRead)
async def change_own_password(
    request: Request,
    payload: ChangePassword,
    user: User = Depends(current_active_user),
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    if not user_manager.verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    update = UserUpdate(password=payload.new_password)
    user = await user_manager.update(update, user, safe=True, request=request)
    return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead])
async def list_users(
    admin: User = Depends(current_superuser),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(select(User).order_by(User.created_at))).scalars().all()
    return [UserRead.model_validate(u) for u in rows]


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    payload: UserCreate,
    admin: User = Depends(current_superuser),
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    try:
        new_user = await user_manager.create(payload, safe=False, request=request)
    except exceptions.UserAlreadyExists:
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists.")
    return UserRead.model_validate(new_user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    request: Request,
    payload: UserAdminUpdate,
    admin: User = Depends(current_superuser),
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    try:
        target = await user_manager.get(user_id)
    except exceptions.UserNotExists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if target.id == admin.id and payload.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot disable your own account.")
    update = UserUpdate(**payload.model_dump(exclude_unset=True))
    target = await user_manager.update(update, target, safe=False, request=request)
    return UserRead.model_validate(target)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(current_superuser),
    user_manager: BaseUserManager = Depends(get_user_manager),
):
    try:
        target = await user_manager.get(user_id)
    except exceptions.UserNotExists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    if target.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot delete your own account.")
    if target.is_superuser:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete a superuser account.")
    await user_manager.delete(target, request=request)
