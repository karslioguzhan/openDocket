from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import current_active_user
from app.models import CATEGORY_GROUPS, ContractCategory, Tag, User
from app.schemas import CategoryMeta, TagIn, TagOut

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/categories", response_model=list[CategoryMeta])
async def list_categories(
    user: User = Depends(current_active_user),
):
    return [
        CategoryMeta(key=cat.value, group=CATEGORY_GROUPS[cat])
        for cat in ContractCategory
    ]


@router.get("/tags", response_model=list[TagOut])
async def list_tags(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(Tag).where(Tag.owner_id == user.id).order_by(Tag.name))
    ).scalars().all()
    return [TagOut.model_validate(t) for t in rows]


@router.post("/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: TagIn,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    existing = await session.scalar(
        select(Tag).where(Tag.owner_id == user.id, Tag.name == payload.name)
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tag already exists.")
    tag = Tag(owner_id=user.id, name=payload.name)
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return TagOut.model_validate(tag)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    tag = await session.get(Tag, tag_id)
    if tag is None or tag.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found.")
    await session.delete(tag)
    await session.commit()
