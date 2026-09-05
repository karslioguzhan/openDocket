from __future__ import annotations

import httpx

from app.services import assistant
from tests.test_contracts import make_contract


class _FakeSettings:
    llm_base_url = "https://llm.example.test/v1"
    llm_api_key = "server-key"
    llm_model = "server-model"


class _FakeSettingsNoLlm:
    llm_base_url = ""
    llm_api_key = ""
    llm_model = ""


class _CapturingChat:
    """Patches assistant.call_chat_completion and records the call."""

    def __init__(self, answer: str = "Sure!"):
        self.answer = answer
        self.calls: list[dict] = []

    def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.answer


async def test_chat_requires_auth(client):
    resp = await client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 401


async def test_chat_without_provider_is_400(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")
    monkeypatch.setattr(assistant, "get_settings", _FakeSettingsNoLlm)
    resp = await client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 400
    assert "No AI provider" in resp.json()["detail"]


async def test_chat_uses_server_settings_and_contract_context(
    client, owner, login, monkeypatch
):
    await login(client, "owner@example.com")
    await make_contract(client, title="Apartment Lease", status="active")

    fake = _CapturingChat(answer="It expires soon.")
    monkeypatch.setattr(assistant, "call_chat_completion", fake)
    monkeypatch.setattr(assistant, "get_settings", _FakeSettings)

    resp = await client.post(
        "/api/chat", json={"message": "Which contracts expire soon?"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["answer"] == "It expires soon."
    assert body["llm_source"] == "server"
    assert body["model"] == "server-model"
    assert body["context_contract_count"] == 1
    assert body["context_truncated"] is False

    assert len(fake.calls) == 1
    base_url, api_key, model, system, user_text = fake.calls[0]["args"]
    kwargs = fake.calls[0]["kwargs"]
    assert base_url == "https://llm.example.test/v1"
    assert api_key == "server-key"
    assert model == "server-model"
    assert user_text == "Which contracts expire soon?"
    assert kwargs["temperature"] == 0.2
    assert kwargs["timeout"] == 120
    # System prompt: usage guide + user's contracts, current user only.
    assert "openDocket is a self-hostable personal contract manager" in system
    assert '"Apartment Lease"' in system
    assert "Which contracts expire soon?" in user_text


async def test_chat_request_override_takes_precedence(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")
    fake = _CapturingChat()
    monkeypatch.setattr(assistant, "call_chat_completion", fake)
    monkeypatch.setattr(assistant, "get_settings", _FakeSettings)

    resp = await client.post(
        "/api/chat",
        json={
            "message": "hello",
            "base_url": "https://override.example/v1",
            "api_key": "  user-key  ",
            "model": "user-model",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["llm_source"] == "user"
    assert body["model"] == "user-model"

    base_url, api_key, model, _, _ = fake.calls[0]["args"]
    assert base_url == "https://override.example/v1"
    assert api_key == "user-key"
    assert model == "user-model"


async def test_chat_override_without_key_does_not_leak_server_key(
    client, owner, login, monkeypatch
):
    await login(client, "owner@example.com")
    fake = _CapturingChat()
    monkeypatch.setattr(assistant, "call_chat_completion", fake)
    monkeypatch.setattr(assistant, "get_settings", _FakeSettings)

    resp = await client.post(
        "/api/chat",
        json={
            "message": "hello",
            "base_url": "https://third-party.example/v1",
            "model": "user-model",
        },
    )
    assert resp.status_code == 200, resp.text

    base_url, api_key, model, _, _ = fake.calls[0]["args"]
    assert base_url == "https://third-party.example/v1"
    assert api_key is None
    assert model == "user-model"


async def test_chat_history_is_sanitized_and_ordered(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")
    fake = _CapturingChat()
    monkeypatch.setattr(assistant, "call_chat_completion", fake)
    monkeypatch.setattr(assistant, "get_settings", _FakeSettings)

    resp = await client.post(
        "/api/chat",
        json={
            "message": "and now?",
            "history": [
                {"role": "assistant", "content": "stray"},  # dropped (leading)
                {"role": "user", "content": "first question"},
                {"role": "assistant", "content": "first answer"},
                {"role": "assistant", "content": "later answer"},  # collapses
                {"role": "user", "content": "trailing"},  # dropped (trailing user)
            ],
        },
    )
    assert resp.status_code == 200, resp.text

    messages = fake.calls[0]["kwargs"]["history"]
    assert messages == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "later answer"},
    ]
    assert fake.calls[0]["args"][4] == "and now?"


async def test_chat_context_respects_acls(client, owner, viewer, login, monkeypatch):
    await login(client, "owner@example.com")
    await make_contract(client, title="Shared Lease")
    await make_contract(client, title="Private Insurance")
    # share only the first one
    contracts = (await client.get("/api/contracts")).json()
    shared = next(c for c in contracts if c["title"] == "Shared Lease")
    share = await client.post(
        f"/api/contracts/{shared['id']}/shares", json={"email": "viewer@example.com"}
    )
    assert share.status_code == 201

    await client.post("/api/auth/logout")
    await login(client, "viewer@example.com")

    fake = _CapturingChat()
    monkeypatch.setattr(assistant, "call_chat_completion", fake)
    monkeypatch.setattr(assistant, "get_settings", _FakeSettings)

    resp = await client.post("/api/chat", json={"message": "what do I have?"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["context_contract_count"] == 1
    system = fake.calls[0]["args"][3]
    assert '"Shared Lease"' in system
    assert "Private Insurance" not in system


async def test_chat_surfaces_provider_error(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    class _ErrResponse:
        status_code = 502

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "Server error '502'",
                request=httpx.Request("POST", "https://llm.example.test/v1/chat/completions"),
                response=self,
            )

        def json(self):
            return {"error": {"message": "Upstream provider is down."}}

    def boom(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "Server error '502'",
            request=httpx.Request("POST", "https://llm.example.test/v1/chat/completions"),
            response=_ErrResponse(),
        )

    monkeypatch.setattr(assistant, "call_chat_completion", boom)
    monkeypatch.setattr(assistant, "get_settings", _FakeSettings)

    resp = await client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 502
    assert "Upstream provider is down." in resp.json()["detail"]


async def test_chat_provider_timeout_is_reported(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    def boom(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(assistant, "call_chat_completion", boom)
    monkeypatch.setattr(assistant, "get_settings", _FakeSettings)

    resp = await client.post("/api/chat", json={"message": "hello"})
    assert resp.status_code == 502
    assert "too long" in resp.json()["detail"]
