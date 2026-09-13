"""Regression tests for AI-endpoint security: SSRF allow-list + key isolation."""

from __future__ import annotations

import pytest

from app.services import assistant, extraction


class _FakeAssistantSettings:
    """Server provider configured, but nothing else allow-listed."""

    llm_base_url = "https://llm.example.test/v1"
    llm_api_key = "server-key"
    llm_model = "server-model"
    llm_allowed_hosts = ""
    llm_allow_private = False


class _FakePortSettings:
    llm_base_url = ""
    llm_api_key = ""
    llm_model = ""
    llm_allowed_hosts = "localhost:11434"
    llm_allow_private = False


class _FakeHostOnlySettings:
    llm_base_url = ""
    llm_api_key = ""
    llm_model = ""
    llm_allowed_hosts = "localhost"
    llm_allow_private = False


async def test_llm_test_refuses_link_local_metadata_address(client, owner, login):
    """The classic cloud-metadata target must be rejected, not contacted."""
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/llm/test",
        json={"base_url": "http://169.254.169.254/v1", "model": "m"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "not allowed" in body["error"]


async def test_llm_test_refuses_loopback(client, owner, login):
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/llm/test",
        json={"base_url": "http://localhost:8000/v1", "model": "m"},
    )
    assert resp.json()["ok"] is False
    assert "not allowed" in resp.json()["error"]


async def test_llm_test_refuses_non_http_scheme(client, owner, login):
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/llm/test",
        json={"base_url": "file:///etc/passwd", "model": "m"},
    )
    assert resp.json()["ok"] is False
    assert "http(s)" in resp.json()["error"]


async def test_llm_test_refuses_embedded_credentials(client, owner, login):
    """`https://api.openai.com@evil.example/` must not be treated as openai."""
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/llm/test",
        json={"base_url": "https://api.openai.com@evil.example/v1", "model": "m"},
    )
    assert resp.json()["ok"] is False
    assert "credentials" in resp.json()["error"]


async def test_chat_refuses_unlisted_endpoint(client, owner, login, monkeypatch):
    """The chat override path enforces the same allow-list."""
    await login(client, "owner@example.com")
    monkeypatch.setattr(assistant, "get_settings", _FakeAssistantSettings)

    resp = await client.post(
        "/api/chat",
        json={
            "message": "hello",
            "base_url": "http://169.254.169.254/v1",
            "model": "m",
        },
    )
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"]


def test_allowlist_accepts_explicit_host_port(monkeypatch):
    """A local provider on 11434 can be allowed without opening every host."""
    monkeypatch.setattr(extraction, "get_settings", _FakePortSettings)
    extraction.assert_safe_endpoint("http://localhost:11434/v1")


def test_allowlist_host_without_port_rejects_other_ports(monkeypatch):
    monkeypatch.setattr(extraction, "get_settings", _FakeHostOnlySettings)
    with pytest.raises(extraction.EndpointNotAllowedError):
        extraction.assert_safe_endpoint("http://localhost:11434/v1")
