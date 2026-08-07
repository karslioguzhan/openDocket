from __future__ import annotations

import io
import json

import httpx
from PIL import Image

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


def _tiny_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


async def test_llm_vision_sends_images(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    calls = []

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs))
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettings)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files=[
            ("files", ("scan.png", _tiny_png(), "image/png")),
            ("files", ("note.txt", b"gibberish", "text/plain")),
        ],
        data={"llm_vision": "1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["counterparty_name"] == "LLM Corp"

    assert calls
    content = calls[0][1]["json"]["messages"][1]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert any(
        part["type"] == "image_url"
        and part["image_url"]["url"].startswith("data:image/jpeg;base64,")
        for part in content
    )


async def test_llm_vision_off_uses_text_only(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    calls = []

    def fake_post(url: str, **kwargs):
        calls.append((url, kwargs))
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettings)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files=[
            ("files", ("scan.png", _tiny_png(), "image/png")),
            ("files", ("note.txt", b"gibberish", "text/plain")),
        ],
    )
    assert resp.status_code == 200, resp.text
    assert calls
    assert isinstance(calls[0][1]["json"]["messages"][1]["content"], str)


async def test_llm_vision_falls_back_to_text_on_provider_error(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    calls = []

    def fake_post(url: str, **kwargs):
        content = kwargs["json"]["messages"][1]["content"]
        if isinstance(content, list):
            raise httpx.HTTPStatusError(
                "Client error '400 Bad Request' for url 'https://llm.example.test/v1/chat/completions'",
                request=httpx.Request("POST", "https://llm.example.test/v1/chat/completions"),
                response=_FakeLLMResponse(),
            )
        calls.append((url, kwargs))
        return _FakeLLMResponse()

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettings)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files=[
            ("files", ("scan.png", _tiny_png(), "image/png")),
            ("files", ("note.txt", b"gibberish", "text/plain")),
        ],
        data={"llm_vision": "1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["counterparty_name"] == "LLM Corp"
    assert len(calls) == 1
    assert isinstance(calls[0][1]["json"]["messages"][1]["content"], str)


def test_detect_category_insurance():
    text = "Private Haftpflichtversicherung - Versicherungsschein Nr. 42"
    assert extraction._detect_category(text) == "privathaftpflicht"


def test_detect_category_kfz_teilkasko():
    text = "Kfz-Teilkasko Versicherung fuer meinen Wagen"
    assert extraction._detect_category(text) == "kfz_teilkasko"


def test_detect_category_rent():
    text = "Mietvertrag zwischen Vermieter und Mieter fuer eine Wohnung"
    assert extraction._detect_category(text) == "mietvertrag"


def test_detect_category_generic_falls_back_to_none():
    text = "Ein ganz normales Dokument ohne Hinweis auf die Art."
    assert extraction._detect_category(text) is None


def test_detect_title_skips_letterhead():
    text = (
        "HUK-COBURG Versicherungsverein\n"
        "Gartenstr. 4\n"
        "96444 Coburg\n"
        "\n"
        "Kfz-Haftpflichtversicherung\n"
        "Versicherungsschein Nr. 7-123-456-789\n"
    )
    assert extraction._detect_title(text, "doc.txt") == "Kfz-Haftpflichtversicherung"


def test_detect_title_letterhead_only():
    text = "Techniker Krankenkasse\nHeilbronner Str. 2\n10779 Berlin\n"
    assert extraction._detect_title(text, "doc.txt") == "Techniker Krankenkasse"


def test_detect_amount_prefers_beitrag_over_versicherungssumme():
    text = (
        "Versicherungssumme: 500.000,00 EUR\n"
        "Monatlicher Beitrag: 32,50 EUR\n"
    )
    amount, currency = extraction._detect_amount(text)
    assert str(amount) == "32.50"
    assert currency == "EUR"


def test_detect_amount_prefers_monthly_over_annual():
    text = (
        "Jahresbeitrag: 390,00 EUR\n"
        "Monatlicher Beitrag: 32,50 EUR\n"
    )
    amount, _ = extraction._detect_amount(text)
    assert str(amount) == "32.50"


def test_detect_amount_currency_first():
    text = "Monatlicher Beitrag: EUR 49,99"
    amount, currency = extraction._detect_amount(text)
    assert str(amount) == "49.99"
    assert currency == "EUR"


def test_detect_amount_none():
    assert extraction._detect_amount("Kein Geld im Text") == (None, None)


def test_detect_counterparty_letterhead():
    text = (
        "Techniker Krankenkasse\n"
        "Heilbronner Str. 2\n"
        "10779 Berlin\n"
        "\n"
        "Sehr geehrte Frau Mustermann,\n"
        "Ihre Versicherungsnummer lautet 7-123-456-789.\n"
    )
    assert extraction._detect_counterparty(text) == "Techniker Krankenkasse"


def test_detect_counterparty_label_vertragspartner():
    text = "Vertragspartner: Acme GmbH\nVersicherungsnummer: 7-123-456-789"
    assert extraction._detect_counterparty(text) == "Acme GmbH"


def test_detect_single_word_letterhead_and_currency_first():
    text = (
        "Allianz\n"
        "One Allianz Drive\n"
        "London\n"
        "\n"
        "Home insurance policy 99-ABC-42\n"
        "Sum insured: 300000 USD\n"
        "Monthly premium: 24.99 USD\n"
    )
    assert extraction._detect_counterparty(text) == "Allianz"
    assert extraction._detect_title(text, "doc.txt") == "Home insurance policy 99-ABC-42"
    amount, currency = extraction._detect_amount(text)
    assert str(amount) == "24.99"
    assert currency == "USD"


def test_normalize_llm_category_accepts_key_and_label():
    result = extraction._normalize_llm_result(
        '{"category": "kfz_haftpflicht", "title": "x"}'
    )
    assert result["category"] == "kfz_haftpflicht"

    result = extraction._normalize_llm_result(
        '{"category": "Private Krankenversicherung", "title": "x"}'
    )
    assert result["category"] == "private_kv"


def test_normalize_llm_category_ignores_invalid():
    result = extraction._normalize_llm_result(
        '{"category": "nonsense", "title": "x"}'
    )
    assert "category" not in result


async def test_extract_api_includes_category(client, owner, login):
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/contracts/extract",
        files={
            "files": (
                "miete.txt",
                "Mietvertrag zwischen Vermieter und Mieter, Monatsmiete 850,00 EUR, Kündigungsfrist 3 Monate".encode(),
                "text/plain",
            )
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["category"] == "mietvertrag"
    assert data["value"] == "850.00"


async def test_llm_category_overrides_heuristics(client, owner, login, monkeypatch):
    await login(client, "owner@example.com")

    class _Resp:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({"category": "hausrat", "title": "LLM Title"})
                        }
                    }
                ]
            }

    def fake_post(url: str, **kwargs):
        return _Resp()

    monkeypatch.setattr(extraction, "get_settings", _FakeLLMSettings)
    monkeypatch.setattr(extraction.httpx, "post", fake_post)

    resp = await client.post(
        "/api/contracts/extract",
        files={"files": ("miete.txt", b"Mietvertrag, Monatsmiete 850,00 EUR", "text/plain")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["category"] == "hausrat"
