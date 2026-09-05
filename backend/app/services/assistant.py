"""AI chat assistant: answers questions about openDocket usage and the
user's own contracts, grounded in data the requesting user can access.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import CONTRACT_LOAD_OPTIONS, accessible_contracts_query
from app.models import Contract, User
from app.services.extraction import _extract_llm_error, call_chat_completion

# Cap how much contract data is included in a prompt so requests stay cheap.
MAX_CONTEXT_CONTRACTS = 200
MAX_CONTEXT_CHARS = 24000
MAX_HISTORY_TURNS = 40
CHAT_TIMEOUT = 120


class AssistantConfigError(Exception):
    """No usable AI provider is configured (server env or request override)."""


class AssistantProviderError(Exception):
    """The configured AI provider could not fulfil the request."""


USAGE_GUIDE = """\
openDocket is a self-hostable personal contract manager. Use this guide to answer
questions about how the application works.

Accounts and access
- The first admin account is bootstrapped from server environment variables
  (ADMIN_EMAIL / ADMIN_PASSWORD). There is no open registration: admins invite
  other users from the Admin page.
- Each user sees only their own contracts plus contracts others explicitly
  shared with them. Shared users have role "viewer" (read-only); owners have
  full control. A one-click demo account with sample contracts may be shown on
  the login screen.

Dashboard
- Shows totals, contracts expiring within the next 90 days, counts by status
  and counts by category.

Contracts
- A contract stores: title, status (draft / active / expired / terminated),
  counterparty, optional policyholder (Versicherungsnehmer), an insurance /
  contract number (Versicherungsnummer, auto-generated if empty), a category,
  tags, effective date, expiry/renewal date, notice period in days, notes, an
  optional value and currency, and attached files.
- Contracts can be created manually or via scan-to-contract: upload PDF(s),
  images or text files and openDocket runs OCR plus heuristics (and optionally
  an AI model) to prefill the fields; the user reviews and corrects before
  saving. The uploaded files stay attached to the contract.
- Renewing a contract = duplicating it and updating the dates.
- Contracts can be searched by title, notes, counterparty, tags or category,
  and filtered by status, category group, tags or an expiring window.

Counterparties and policyholders
- Counterparties are the companies/organisations the user has contracts with
  (e.g. the insurer, landlord or provider); policyholders (Versicherungsnehmer)
  are people. Both are reusable entities with their own overview pages.

Files, sharing and lifecycle
- A contract can carry multiple files (PDF, images, documents; up to 25 MB),
  served only to users who can access the contract.
- The owner can share a contract with other users by email address. Viewers
  cannot edit, delete or trash shared contracts.
- Moving a contract to trash is a soft delete: it can be restored, and trash is
  purged automatically after 30 days. Trash is only visible to the owner.

AI provider
- Configured server-wide via LLM_BASE_URL / LLM_API_KEY / LLM_MODEL, or per
  browser in Settings (stored locally in the browser, never on the server).
  The same provider powers scan-to-contract autofill and this assistant.

Settings & Admin
- Settings: pick an OpenAI-compatible provider (OpenCode Zen, OpenCode Go,
  OpenAI, OpenRouter, Groq, DeepSeek, a local Ollama / LM Studio endpoint, or a
  custom endpoint), model, API key and whether document images may be sent.
- Admin (superusers only): invite, disable/enable, reset passwords of and
  delete users. Admins cannot view other users' contracts.
"""


def _normalize_history(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    """Sanitize and cap the prior conversation.

    Keeps only user/assistant turns with non-empty content, collapses repeated
    roles, drops a stray leading assistant or trailing user turn, and bounds the
    total length.
    """
    cleaned: list[dict[str, str]] = []
    for turn in history or []:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1]["content"] = content
        else:
            cleaned.append({"role": role, "content": content})
    if cleaned and cleaned[0]["role"] == "assistant":
        cleaned.pop(0)
    if cleaned and cleaned[-1]["role"] == "user":
        cleaned.pop()
    return cleaned[-MAX_HISTORY_TURNS:]


def _resolve_llm(override: dict[str, str | None] | None) -> tuple[str, str | None, str, str]:
    """Resolve (base_url, api_key, model, source) for a chat request.

    Values given in the request override the server-side defaults. ``source``
    is "user" when the request supplied any override, otherwise "server".
    When a user picks their own endpoint/model but sends no key, the server's
    key is intentionally withheld so it is never forwarded to a third party.
    """
    settings = get_settings()
    override = override or {}
    base_url = (override.get("base_url") or settings.llm_base_url or "").strip()
    model = (override.get("model") or settings.llm_model or "").strip()
    if not base_url or not model:
        raise AssistantConfigError(
            "No AI provider is configured. Add one in Settings or set "
            "LLM_BASE_URL and LLM_MODEL on the server."
        )
    user_key = (override.get("api_key") or "").strip()
    if user_key:
        api_key = user_key
    elif override.get("base_url") or override.get("model"):
        api_key = None
    else:
        api_key = (settings.llm_api_key or "").strip() or None
    supplied = any(override.get(key) for key in ("base_url", "api_key", "model"))
    return base_url, api_key, model, "user" if supplied else "server"


def _contract_digest(contract: Contract) -> str:
    """Render one contract as a single compact, readable line."""
    status = contract.status.value if contract.status is not None else "?"
    parts = [f'"{contract.title}"', f"status={status}"]
    if contract.category is not None:
        parts.append(f"category={contract.category.value}")
    if contract.counterparty is not None:
        parts.append(f"counterparty={contract.counterparty.name}")
    if contract.versicherungsnehmer is not None:
        parts.append(f"policyholder={contract.versicherungsnehmer.name}")
    if contract.versicherungsnummer:
        parts.append(f"number={contract.versicherungsnummer}")
    if contract.effective_date is not None:
        parts.append(f"effective={contract.effective_date.isoformat()}")
    if contract.expiry_date is not None:
        parts.append(f"expiry={contract.expiry_date.isoformat()}")
    if contract.notice_days is not None:
        parts.append(f"notice_days={contract.notice_days}")
    if contract.value is not None:
        currency = contract.currency or ""
        parts.append(f"value={contract.value} {currency}".rstrip())
    if contract.tags:
        parts.append("tags=" + ",".join(sorted(tag.name for tag in contract.tags)))
    line = " | ".join(parts)
    if contract.notes:
        note = " ".join(contract.notes.split())[:300]
        line += f" | notes={note}"
    return line[:1000]


async def collect_contract_context(session: AsyncSession, user: User) -> dict[str, Any]:
    """Load the contracts the user can access and render them for the prompt."""
    base = accessible_contracts_query(user)
    total = await session.scalar(
        select(func.count()).select_from(base.subquery())
    )
    total = int(total or 0)

    stmt = (
        accessible_contracts_query(user)
        .options(*CONTRACT_LOAD_OPTIONS)
        .order_by(Contract.updated_at.desc())
        .limit(MAX_CONTEXT_CONTRACTS)
    )
    rows = (await session.execute(stmt)).scalars().unique().all()

    lines: list[str] = []
    used = 0
    truncated = False
    for contract in rows:
        line = _contract_digest(contract)
        if used + len(line) + 1 > MAX_CONTEXT_CHARS:
            truncated = True
            break
        lines.append(line)
        used += len(line) + 1

    if len(rows) == MAX_CONTEXT_CONTRACTS or total > len(lines):
        truncated = True

    return {
        "total": total,
        "shown": len(lines),
        "truncated": truncated,
        "lines": "\n".join(lines),
    }


def build_system_prompt(context: dict[str, Any], today_iso: str) -> str:
    """Assemble the system prompt: role + usage guide + user's contract data."""
    shown = context["shown"]
    total = context["total"]
    if total == 0:
        contract_block = "The user currently has no contracts in openDocket."
    else:
        suffix = (
            f" (the list is truncated to the most recently updated {shown})"
            if context["truncated"] and shown < total
            else ""
        )
        contract_block = (
            f"The user has access to {total} contract(s){suffix}:\n"
            f"{context['lines']}"
        )

    return f"""\
You are the assistant built into openDocket, a self-hostable personal contract
manager. You help the user in two ways: explain how to use openDocket, and
answer questions about their own contracts.

## How to use openDocket
{USAGE_GUIDE}

## The user's contracts (read-only)
{contract_block}

## Rules
- Today's date is {today_iso}. Use it to reason about expiry, renewal or notice
  periods (e.g. how many days are left).
- Answer questions about contracts strictly from the list above. If the needed
  contract or detail is not listed, say you cannot find it in their contracts -
  never invent contracts, dates, amounts or parties.
- The list contains only contracts the user can access (owned or shared).
- You have read-only access: you cannot create, edit, delete or share anything.
- Give concise, practical answers. Use the user's language - reply in the same
  language the user writes in.
- When you reference a contract, use its exact title as listed above.
- Never claim the user has data outside the list above, and never repeat
  contracts the user does not have access to."""


async def chat(
    session: AsyncSession,
    user: User,
    message: str,
    history: list[dict[str, str]] | None = None,
    llm_override: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Run one assistant turn against the configured AI provider.

    Returns fields matching ``ChatResponse``. Raises ``AssistantConfigError``
    when no provider is available and ``AssistantProviderError`` when the
    provider call fails.
    """
    base_url, api_key, model, source = _resolve_llm(llm_override)
    context = await collect_contract_context(session, user)
    system = build_system_prompt(context, datetime.now(UTC).date().isoformat())
    turns = _normalize_history(history)

    try:
        answer = call_chat_completion(
            base_url,
            api_key,
            model,
            system,
            message.strip(),
            timeout=CHAT_TIMEOUT,
            history=turns,
            temperature=0.2,
        )
    except httpx.HTTPStatusError as exc:
        detail = _extract_llm_error(exc.response)
        raise AssistantProviderError(
            detail or f"The AI provider returned HTTP {exc.response.status_code}."
        ) from exc
    except httpx.TimeoutException as exc:
        raise AssistantProviderError(
            "The AI provider took too long to respond. Please try again."
        ) from exc
    except httpx.HTTPError as exc:
        raise AssistantProviderError(
            f"Could not reach the AI provider ({exc.__class__.__name__})."
        ) from exc
    except (KeyError, IndexError, ValueError) as exc:
        raise AssistantProviderError(
            "The AI provider returned an unexpected response."
        ) from exc

    return {
        "answer": (answer or "").strip(),
        "llm_source": source,
        "model": model,
        "context_contract_count": context["total"],
        "context_truncated": context["truncated"],
    }
