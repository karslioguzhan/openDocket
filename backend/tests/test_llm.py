from __future__ import annotations

import json

import httpx

from app.services import extraction


class _FakeLLMResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "title": "LLM Title",
                                "counterparty_name": "LLM Corp",
                                "effective_date": "2023-01-01",
                                "expiry_date": "2026-01-01",
                                "notice_days": 90,
                                "value": 123.45,
                                "currency": "EUR",
                                "versicherungsnummer": "LLM-123",
                            }
                        )
                    }
                }
            ]
        }


class _FakeLLMSettings:
    llm_base_url = "https://llm.example.test/v1"
    llm_api_key = "env-key"
    llm_model = "env-model"
    llm_allowed_hosts = "override.example"
    llm_allow_private = False


class _FakeLLMSettingsNoKey:
    llm_base_url = "https://llm.example.test/v1"
    llm_api_key = ""
    llm_model = "env-model"
    llm_allowed_hosts = ""
    llm_allow_private = False


async def test_extract_override_endpoint_off_allowlist_is_refused(
    client, owner, login, monkeypatch
):
    """A per-request endpoint that is not allow-listed must never be contacted."""
    await login(client, "owner@example.com")

    calls = []

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs))
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettings)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("doc.txt", b"gibberish", "text/plain")},
        data={
            "llm_base_url": "http://169.254.169.254/v1",
            "llm_model": "override-model",
        },
    )
    assert resp.status_code == 200, resp.text
    assert calls == []  # SSRF attempt blocked before any request was made


async def test_extract_override_allowed_host_withholds_server_key(
    client, owner, login, monkeypatch
):
    """An allow-listed user endpoint gets the user's key, never the server's."""
    await login(client, "owner@example.com")

    calls = []

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs))
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettings)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("doc.txt", b"gibberish", "text/plain")},
        data={
            "llm_base_url": "https://override.example/v1",
            "llm_model": "override-model",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["counterparty_name"] == "LLM Corp"

    assert calls
    url, kwargs = calls[0]
    assert url == "https://override.example/v1/chat/completions"
    assert "Authorization" not in kwargs["headers"]
    assert kwargs["json"]["model"] == "override-model"


async def test_extract_override_forwards_the_users_own_key(
    client, owner, login, monkeypatch
):
    await login(client, "owner@example.com")

    calls = []

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs))
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettings)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("doc.txt", b"gibberish", "text/plain")},
        data={
            "llm_base_url": "https://override.example/v1",
            "llm_api_key": "override-key",
            "llm_model": "override-model",
        },
    )
    assert resp.status_code == 200, resp.text

    assert calls
    url, kwargs = calls[0]
    assert url == "https://override.example/v1/chat/completions"
    assert kwargs["headers"] == {"Authorization": "Bearer override-key"}
    assert kwargs["json"]["model"] == "override-model"


async def test_llm_no_key_omits_auth_header(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    calls = []

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs))
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettingsNoKey)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("doc.txt", b"gibberish", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    url, kwargs = calls[0]
    assert url == "https://llm.example.test/v1/chat/completions"
    assert "Authorization" not in kwargs["headers"]


async def test_llm_test_requires_auth(client):
    resp = await client.post(
        "/api/llm/test",
        json={"base_url": "https://x.example/v1", "api_key": "k", "model": "m"},
    )
    assert resp.status_code == 401


async def test_llm_test_ok(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    def fake_post(url: str, **kwargs):
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/llm/test",
        json={"base_url": "https://x.example/v1", "api_key": "k", "model": "m"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["error"] is None
    assert body["response"]


async def test_llm_test_error(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    def fake_post(url: str, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/llm/test",
        json={"base_url": "https://x.example/v1", "api_key": "k", "model": "m"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]


async def test_llm_test_surfaces_provider_message(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    class _ErrResponse:
        status_code = 401

        def raise_for_status(self):
            raise httpx.HTTPStatusError(
                "Client error '401 Unauthorized' for url 'https://x.example/v1/chat/completions'",
                request=httpx.Request("POST", "https://x.example/v1/chat/completions"),
                response=self,
            )

        def json(self) -> dict:
            return {"error": {"message": "Invalid API key."}}

    def fake_post(url: str, **kwargs):
        return _ErrResponse()

    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/llm/test",
        json={"base_url": "https://x.example/v1", "api_key": "k", "model": "m"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "Invalid API key." in body["error"]


async def test_llm_key_is_trimmed(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    calls = []

    def fake_post(url: str, **kwargs):
        calls.append(kwargs)
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/llm/test",
        json={"base_url": "https://x.example/v1", "api_key": "  sk-abc\n", "model": "m"},
    )
    assert resp.status_code == 200
    assert calls
    assert calls[0]["headers"] == {"Authorization": "Bearer sk-abc"}
