from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import current_active_user
from app.models import User
from app.schemas import ChatRequest, ChatResponse
from app.services.assistant import (
    AssistantConfigError,
    AssistantProviderError,
    chat,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat_turn(
    payload: ChatRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Answer a user message about app usage and/or their own contracts.

    ``base_url`` / ``api_key`` / ``model`` may override the server-wide AI
    provider (browser-local settings). Only contracts the current user can
    access are included in the prompt context.
    """
    override = {
        key: value
        for key, value in (
            ("base_url", payload.base_url),
            ("api_key", payload.api_key),
            ("model", payload.model),
        )
        if value and value.strip()
    }
    history = [turn.model_dump() for turn in payload.history]

    try:
        result = await chat(
            session,
            user,
            payload.message,
            history=history,
            llm_override=override or None,
        )
    except AssistantConfigError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except AssistantProviderError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    return ChatResponse(**result)
