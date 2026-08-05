from __future__ import annotations

import json

import httpx

from app.services import extraction

CONTRACT_TEXT = """Telecom Services Agreement
Customer: Acme GmbH
Versicherungsnummer: 7-123-456-789
This agreement is effective January 15, 2024 and expires on January 14, 2026.
Either party may terminate with 60 days written notice.
Monthly fee: $49.99 USD
"""


async def test_extract_requires_auth(client):
    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("doc.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 401


async def test_extract_parses_txt(client, owner, login):
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("telecom.txt", CONTRACT_TEXT.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "Telecom Services Agreement"
    assert data["counterparty_name"] == "Acme GmbH"
    assert data["versicherungsnummer"] == "7-123-456-789"
    assert data["effective_date"] == "2024-01-15"
    assert data["expiry_date"] == "2026-01-14"
    assert data["notice_days"] == 60
    assert data["value"] == "49.99"
    assert data["currency"] == "USD"
    assert data["files"] == [
        {
            "original_name": "telecom.txt",
            "mime_type": "text/plain",
            "size_bytes": len(CONTRACT_TEXT),
        }
    ]


async def test_extract_multiple_files(client, owner, login):
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/contracts/extract",
        files=[
            ("files", ("a.txt", b"Erster Teil eines Vertrags", "text/plain")),
            ("files", ("b.txt", b"Zweiter Teil mit 123,45 EUR", "text/plain")),
        ],
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["files"]) == 2


async def test_extract_rejects_bad_type(client, owner, login):
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("evil.exe", b"MZ", "application/x-msdownload")},
    )
    assert resp.status_code == 415


async def test_extract_rejects_uploadable_but_unparseable(client, owner, login):
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/contracts/extract",
        files={
            "files": (
                "doc.docx",
                b"PK\x03\x04 fake",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 415


async def test_extract_oversize(client, owner, login):
    await login(client, "owner@example.com")
    big = b"x" * (25 * 1024 * 1024 + 1)
    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("big.txt", big, "text/plain")},
    )
    assert resp.status_code == 413


async def test_extract_empty_text(client, owner, login):
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("empty.txt", b"", "text/plain")},
    )
    assert resp.status_code == 422


class _FakeLLMSettings:
    llm_base_url = "https://llm.example.test/v1"
    llm_api_key = "test-key"
    llm_model = "test-model"


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
                            }
                        )
                    }
                }
            ]
        }


async def test_llm_used_when_configured(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    calls = []

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs))
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettings)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("gibberish.txt", b"nothing structured here", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["title"] == "LLM Title"
    assert data["counterparty_name"] == "LLM Corp"
    assert data["effective_date"] == "2023-01-01"
    assert data["expiry_date"] == "2026-01-01"
    assert data["notice_days"] == 90
    assert data["value"] == "123.45"
    assert data["currency"] == "EUR"

    assert calls and calls[0][0].endswith("/v1/chat/completions")
    assert calls[0][1]["json"]["model"] == "test-model"


async def test_llm_failure_falls_back_to_heuristics(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    def fake_post(url: str, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettings)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("telecom.txt", CONTRACT_TEXT.encode("utf-8"), "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["counterparty_name"] == "Acme GmbH"
    assert data["notice_days"] == 60
