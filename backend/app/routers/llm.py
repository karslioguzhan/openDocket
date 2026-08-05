from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends

from app.dependencies import current_active_user
from app.models import User
from app.schemas import LLMTestOut, LLMTestRequest
from app.services.extraction import call_chat_completion

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.post("/test", response_model=LLMTestOut)
async def test_llm(
    payload: LLMTestRequest,
    user: User = Depends(current_active_user),
):
    """Send a tiny chat completion to validate an OpenAI-compatible endpoint."""
    try:
        response = call_chat_completion(
            payload.base_url,
            payload.api_key,
            payload.model,
            "You are a connection test. Reply with exactly: OK",
            "ping",
            timeout=30,
        )
    except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
        return LLMTestOut(ok=False, error=str(exc) or exc.__class__.__name__)

    return LLMTestOut(ok=True, response=(response or "").strip()[:200])
