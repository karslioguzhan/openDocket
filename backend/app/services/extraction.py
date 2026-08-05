from __future__ import annotations

import io
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
from PIL import Image, UnidentifiedImageError

from app.config import get_settings

# File types we can extract text from. doc/docx/odt are uploadable but not
# extractable in v1 — the scan endpoint rejects them.
EXTRACTABLE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt"}

_MONTHS = {
    "januar": 1, "january": 1, "jan": 1, "jänner": 1, "jaenner": 1,
    "februar": 2, "february": 2, "feb": 2,
    "märz": 3, "maerz": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mai": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "dezember": 12, "december": 12, "dez": 12, "dec": 12,
}

_DATE_TOKEN_RE = re.compile(
    r"\b(?P<n1>\d{1,4})(?:\.|/|-)(?P<n2>\d{1,2})(?:\.|/|-)(?P<n3>\d{2,4})\b"
    r"|\b(?P<d1>\d{1,2})(?:\.\s*)?\s+(?P<m1>januar|january|jan|jänner|jaenner|februar|february|feb|"
    r"märz|maerz|march|mar|april|apr|mai|may|juni|june|jun|juli|july|jul|august|aug|september|sep|sept|"
    r"oktober|october|oct|november|nov|dezember|december|dez)"
    r"\.?\s+(?P<y1>\d{2,4})\b"
    r"|\b(?P<m2>january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|"
    r"september|sep|sept|october|oct|november|nov|december|dec|januar|jänner|jaenner|februar|märz|maerz|"
    r"mai|juni|juli|oktober|dezember)"
    r"\.?\s+(?P<d2>\d{1,2}),?\s+(?P<y2>\d{4})\b",
    re.IGNORECASE,
)

_DATE_KEYWORDS = re.compile(
    r"expir|end\s*(date|s)?|endet|ends?|until|runs?\s+through|terminates?|termination\s+date"
    r"|gültig\s+bis|gueltig\s+bis|endet\s+am|läuft\s+bis|laeuft\s+bis|ausläuft|auslaeuft"
    r"|verlängert\s+sich|verlaengert\s+sich|letzter\s+tag|last\s+day|durch\s+bis|bis\s+zum"
    r"|end\s+of\s+contract|through|vertragsende|ende\s+des\s+vertrags",
    re.IGNORECASE,
)

_AMOUNT_RE = [
    re.compile(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\s*(€|EUR|EUR\b|US\$|USD|US\s*Dollar|\$|TRY|TL)", re.IGNORECASE),
    re.compile(r"(€|EUR|EUR\b|US\$|USD|US\s*Dollar|\$|TRY|TL)\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)", re.IGNORECASE),
]

_CURRENCY_TO_CODE = {
    "€": "EUR", "eur": "EUR", "euro": "EUR",
    "$": "USD", "usd": "USD", "us$": "USD", "us dollar": "USD",
    "tl": "TRY", "try": "TRY",
}

_MONTHS_TO_DAYS = {"month": 30, "monat": 30, "monaten": 30, "monate": 30, "week": 7, "woche": 7, "wochen": 7, "day": 1, "tag": 1, "tage": 1, "tagen": 1}

_NOTICE_PATTERNS = [
    re.compile(r"(\d+)\s*(?:months?|monate|monaten|weeks?|wochen|woche|days?|tage|tagen)(?:\s+\w+){0,3}\s*(?:notice|kündigungsfrist|kuendigungsfrist|vorlauf|termination|notice\s+period)", re.IGNORECASE),
    re.compile(r"(?:notice\s+period|kündigungsfrist|kuendigungsfrist|kündigung|kuendigung|notice)[:\s]{0,30}?(\d+)\s*(?:days?|tage|tagen|weeks?|wochen|woche|months?|monate|monaten)", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:days?|tage|tagen)\s+(?:\w+\s+){0,3}(?:notice|kündigung|kuendigung|kündigungsfrist|kuendigungsfrist|vorab)", re.IGNORECASE),
    re.compile(r"kündigbar|kuendigbar\s+(?:mit|innerhalb\s+von)?\s*(\d+)\s*(?:tagen?|wochen|monaten)", re.IGNORECASE),
]

_POLICY_NO_LABELS = (
    r"versicherungsnummer|versicherungs\s*nr\.?|versicherungsschein\s*nr\.?|"
    r"policennummer|policen\s*nr\.?|police\s*nr\.?|vertragsnummer|vertrags\s*nr\.?|"
    r"policy\s*(?:number|no\.?|#)|contract\s*(?:number|no\.?|#)|"
    r"kundennummer|customer\s*(?:number|no\.?|#)|mitgliedsnummer|member\s*(?:id|number)"
)

_POLICY_NO_RE = re.compile(
    r"\b(?:" + _POLICY_NO_LABELS + r")\s*[:.\-#]?\s*"
    r"(?P<value>[A-Z0-9][A-Z0-9/\-._]{3,39})\b",
    re.IGNORECASE,
)

_SECTION_LABELS = {
    "vermiet": "vermiet",
    "mieter": "mieter",
    "kauf": "kauf",
    "verkäufer": "verkäufer", "verkaeufer": "verkäufer",
    "kunde": "kunde", "kundin": "kunde",
    "auftraggeber": "auftraggeber",
    "auftragnehmer": "auftragnehmer",
    "versicherer": "versicherer",
    "versicherungsnehmer": "versicherungsnehmer",
    "anbieter": "anbieter", "anbieterin": "anbieter",
    "firma": "firma",
    "landlord": "landlord",
    "tenant": "tenant",
    "customer": "customer",
    "client": "client",
    "provider": "provider",
    "supplier": "supplier",
    "vendor": "vendor",
    "party a": "party", "party b": "party",
    "employer": "employer",
    "employee": "employee",
    "insurer": "insurer",
    "insured": "insured",
}

_LEGAL_FORM_RE = re.compile(
    r"([A-ZÄÖÜ][A-Za-zÄÖÜßöäü .&'()/-]{2,50}?"
    r"(?:GmbH|AG|KG|e\.?V\.?|UG|Inc\.?|Ltd\.?|LLC|S\.?A\.?|B\.?V\.?|SE|GbR))",
    re.IGNORECASE,
)

_SECTION_LABELS_RE = re.compile(
    r"^\s*[-•–·]?\s*("
    + "|".join(re.escape(k) for k in sorted(_SECTION_LABELS, key=len, reverse=True))
    + r")(?:in|er|en)?\s*[:.)]?\s*(.*)$",
    re.IGNORECASE,
)

_SKIP_LINE_RE = re.compile(
    r"^(seite\b|page\b|tel\b|telefon\b|fax\b|e-?mail|www\.|http|\d{1,4}[\s./-]+\d{1,2}|"
    r"\b(?:€|eur|us\$|usd|\$|try|tl)\b|\d+[.,]\d+)",
    re.IGNORECASE,
)


def _detect_ocr_langs() -> str | None:
    try:
        import pytesseract
        available = set(pytesseract.get_languages(config=""))
        preferred = ["deu", "eng", "tur"]
        chosen = [lang for lang in preferred if lang in available]
        return "+".join(chosen) if chosen else None
    except Exception:
        return None


def extract_text_from_bytes(filename: str, data: bytes) -> str:
    """Return plain text extracted from a PDF or image upload."""
    suffix = Path(filename).suffix.lower()

    if suffix == ".txt":
        for enc in ("utf-8", "latin-1"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    if suffix == ".pdf":
        return _extract_pdf(data)

    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return _ocr_image(data)

    return ""


def _extract_pdf(data: bytes) -> str:
    text = ""
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        text = ""

    if len(text.strip()) >= 80:
        return text

    ocr_text = ""
    try:
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            ocr_text += _ocr_image_bytes(img)
    except Exception:
        return text

    return (text + "\n" + ocr_text).strip() or text


def _ocr_image(data: bytes) -> str:
    try:
        img = Image.open(io.BytesIO(data))
        return _ocr_image_bytes(img)
    except (UnidentifiedImageError, OSError):
        return ""


def _ocr_image_bytes(img: Image.Image) -> str:
    try:
        import pytesseract

        lang = _detect_ocr_langs()
        if lang:
            return pytesseract.image_to_string(img, lang=lang)
        return pytesseract.image_to_string(img)
    except Exception:
        return ""


def parse_contract_documents(
    files: list[tuple[str, bytes]], llm_config: dict[str, str] | None = None
) -> dict[str, Any]:
    """Parse a list of (filename, bytes) into extracted contract fields.

    ``llm_config`` optionally overrides the server-side LLM settings with
    per-request values (``base_url``, ``api_key``, ``model``).
    """
    texts: list[str] = []
    for name, data in files:
        text = extract_text_from_bytes(name, data)
        if text.strip():
            texts.append(text)

    combined = "\n\n".join(texts)
    if not combined.strip():
        return {}

    heuristics = _parse_heuristically(combined, files[0][0] if files else "")
    llm = _parse_with_llm(combined, llm_config=llm_config)
    result = {**heuristics}
    if llm:
        for key, value in llm.items():
            if value is not None:
                result[key] = value
    return result


def _parse_heuristically(text: str, filename: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "title": _detect_title(text, filename),
        "counterparty_name": _detect_counterparty(text),
        "versicherungsnummer": _detect_policy_number(text),
        "effective_date": None,
        "expiry_date": None,
        "notice_days": None,
        "value": None,
        "currency": None,
    }

    dates = _parse_dates(text)
    if dates:
        result["effective_date"] = dates[0][0].isoformat()

        expiry = _find_expiry(text, dates)
        if expiry is not None:
            result["expiry_date"] = expiry.isoformat()

    amount, currency = _detect_amount(text)
    if amount is not None:
        result["value"] = str(amount)
        result["currency"] = currency

    notice = _detect_notice_period(text)
    if notice is not None:
        result["notice_days"] = notice

    return result


def _parse_dates(text: str) -> list[tuple[date, int]]:
    dates: list[tuple[date, int]] = []
    seen: set[date] = set()
    for match in _DATE_TOKEN_RE.finditer(text):
        try:
            if match.group("n1"):
                first, second, third = match.group("n1"), match.group("n2"), match.group("n3")
                year = int(third)
                if len(third) == 2:
                    year += 2000 if year < 70 else 1900
                month, day = int(second), int(first)
                if 1 <= month <= 12 and 1 <= day <= 31:
                    d = date(year, month, day)
                else:
                    d = date(year, day, month)
            elif match.group("m1"):
                day = int(match.group("d1"))
                month = _MONTHS[match.group("m1").lower()]
                year = int(match.group("y1"))
                if len(match.group("y1")) == 2:
                    year += 2000 if year < 70 else 1900
                d = date(year, month, day)
            else:
                month = _MONTHS[match.group("m2").lower()]
                day = int(match.group("d2"))
                year = int(match.group("y2"))
                d = date(year, month, day)
        except ValueError:
            continue
        if 1900 <= d.year <= 2100 and d not in seen:
            seen.add(d)
            dates.append((d, match.start()))
    dates.sort(key=lambda item: item[1])
    return dates


def _find_expiry(text: str, dates: list[tuple[date, int]]) -> date | None:
    if len(dates) < 2:
        return None
    effective = dates[0][0]
    keyword_matches = list(_DATE_KEYWORDS.finditer(text))
    if keyword_matches:
        best: date | None = None
        best_dist = 10 ** 9
        for m in keyword_matches:
            for d, pos in dates:
                if d <= effective:
                    continue
                dist = abs(m.start() - pos)
                if dist < best_dist:
                    best_dist = dist
                    best = d
        if best is not None:
            return best
    last = dates[-1][0]
    return last if last != effective else None


def _detect_amount(text: str) -> tuple[Decimal | None, str | None]:
    for pattern in _AMOUNT_RE:
        for match in pattern.finditer(text):
            raw, cur = match.group(1), match.group(2).strip()
            amount = _normalize_amount(raw)
            if amount is None:
                continue
            code = _CURRENCY_TO_CODE.get(cur.lower(), None)
            if code and 0 < amount < 10 ** 13:
                return amount, code
    return None, None


def _normalize_amount(raw: str) -> Decimal | None:
    try:
        s = raw.replace("\u00a0", "").replace(" ", "").strip()
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            if len(s.rsplit(",", 1)[1]) == 3:
                s = s.replace(",", "")
            else:
                s = s.replace(",", ".")
        elif "." in s and len(s.rsplit(".", 1)[1]) == 3:
            s = s.replace(".", "")
        return Decimal(s)
    except InvalidOperation:
        return None


def _detect_notice_period(text: str) -> int | None:
    for pattern in _NOTICE_PATTERNS:
        for match in pattern.finditer(text):
            num = int(match.group(1))
            if num <= 0 or num > 120:
                continue
            window = text[max(0, match.start() - 10): match.end()]
            unit = "month"
            if any(u in window.lower() for u in ("woche", "week")):
                unit = "week"
            elif any(u in window.lower() for u in ("tag", "day")):
                unit = "day"
            days = num * _MONTHS_TO_DAYS[unit]
            return min(days, 3650)
    return None


def _detect_title(text: str, filename: str) -> str | None:
    for line in text.splitlines()[:20]:
        line = line.strip().strip("*#")
        if not line or len(line) < 3:
            continue
        if _SKIP_LINE_RE.search(line) or _SECTION_LABELS_RE.match(line):
            continue
        if len(line) <= 160 and re.search(r"[A-Za-zÄÖÜäöü]", line):
            return line[:160]
    stem = Path(filename).stem
    return stem[:200] if stem else None


_COUNTERPARTY_BAD_START = re.compile(
    r"^(vertrag|contract|agreement|vereinbarung|policy|versicherungsschein|versicherungsvertrag"
    r"|dokument|document|rechnung|invoice|bestätigung|bestaetigung|über|ueber|zwischen)",
    re.IGNORECASE,
)


def _detect_counterparty(text: str) -> str | None:
    best: str | None = None
    best_score = 0
    for line in text.splitlines():
        m = _SECTION_LABELS_RE.match(line)
        if not m or not m.group(2):
            continue
        name = m.group(2).strip().strip(":.,;")
        if not name or _SKIP_LINE_RE.search(name) or _DATE_TOKEN_RE.search(name):
            continue
        if len(name) > 120 or not re.search(r"[A-Za-zÄÖÜäöü]", name):
            continue
        if _COUNTERPARTY_BAD_START.match(name):
            continue
        score = 1
        if _LEGAL_FORM_RE.search(name):
            score += 3
        if len(name.split()) >= 2:
            score += 1
        if score > best_score:
            best_score = score
            best = name

    if best is not None:
        return best[:120]

    for m in _LEGAL_FORM_RE.finditer(text):
        return m.group(1).strip().rstrip(".")[:120]

    return None


def _detect_policy_number(text: str) -> str | None:
    """Find an insurance/policy/contract number after a matching label."""
    for match in _POLICY_NO_RE.finditer(text):
        value = match.group("value").strip().strip(":.,;-")
        if _DATE_TOKEN_RE.search(value):
            continue
        if _AMOUNT_RE[0].search(value) or _AMOUNT_RE[1].search(value):
            continue
        if len(value) >= 4:
            return value[:40]
    return None


def call_chat_completion(
    base_url: str,
    api_key: str | None,
    model: str,
    system: str,
    user_text: str,
    timeout: float = 60,
) -> str:
    """Send an OpenAI-style chat completion and return the assistant's text.

    Raises on transport/HTTP errors so callers can decide how to handle them.
    """
    headers = {}
    api_key = (api_key or "").strip() or None
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
        },
        timeout=timeout,
    )
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = _extract_llm_error(resp)
        if detail:
            raise httpx.HTTPStatusError(
                f"HTTP {exc.response.status_code}: {detail}",
                request=exc.request,
                response=exc.response,
            ) from exc
        raise
    return resp.json()["choices"][0]["message"]["content"]


def _extract_llm_error(resp: httpx.Response) -> str | None:
    """Pull the human-readable message from an OpenAI-compatible error body."""
    try:
        data = resp.json()
    except ValueError:
        return None
    error = data.get("error")
    if isinstance(error, str):
        return error
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            return str(message)
    return None


def _parse_with_llm(text: str, llm_config: dict[str, str] | None = None) -> dict[str, Any]:
    settings = get_settings()
    base_url = (llm_config or {}).get("base_url") or settings.llm_base_url
    api_key = (llm_config or {}).get("api_key") or settings.llm_api_key
    model = (llm_config or {}).get("model") or settings.llm_model
    if not (base_url and model):
        return {}

    system = (
        "You extract structured data from contract documents. "
        "Return ONLY a valid JSON object with these keys: "
        "title (string or null), counterparty_name (string or null), "
        "versicherungsnummer (string or null, the insurance/policy/contract number, "
        "also known as Versicherungsnummer, Versicherungsnr., Policennummer or Vertragsnummer), "
        "effective_date (YYYY-MM-DD or null), expiry_date (YYYY-MM-DD or null), "
        "notice_days (integer or null), value (number or null), "
        "currency (ISO 4217 code or null). "
        "Use null when a value cannot be determined from the text. Do not invent data."
    )
    try:
        content = call_chat_completion(
            base_url,
            api_key,
            model,
            system,
            f"Document text:\n{text[:12000]}",
            timeout=120,
        )
    except Exception:
        return {}

    return _normalize_llm_result(content)


def _normalize_llm_result(content: str) -> dict[str, Any]:
    try:
        content = content.strip().strip("`")
        if content.startswith("json"):
            content = content[4:].strip()
        data = json.loads(content)
    except (json.JSONDecodeError, AttributeError):
        return {}

    result: dict[str, Any] = {}
    if isinstance(data.get("title"), str) and data["title"].strip():
        result["title"] = data["title"].strip()[:200]
    if isinstance(data.get("counterparty_name"), str) and data["counterparty_name"].strip():
        result["counterparty_name"] = data["counterparty_name"].strip()[:200]
    if isinstance(data.get("versicherungsnummer"), str) and data["versicherungsnummer"].strip():
        result["versicherungsnummer"] = data["versicherungsnummer"].strip()[:40]

    for key in ("effective_date", "expiry_date"):
        raw = data.get(key)
        if isinstance(raw, str):
            try:
                result[key] = date.fromisoformat(raw[:10]).isoformat()
            except ValueError:
                pass

    if isinstance(data.get("notice_days"), int) and 0 < data["notice_days"] <= 3650:
        result["notice_days"] = data["notice_days"]

    raw_value = data.get("value")
    if isinstance(raw_value, (int, float, str)):
        try:
            amount = Decimal(str(raw_value))
            if 0 < amount < 10 ** 13:
                result["value"] = str(amount.quantize(Decimal("0.01")))
        except (InvalidOperation, ValueError):
            pass

    if isinstance(data.get("currency"), str) and len(data["currency"]) == 3:
        result["currency"] = data["currency"].upper()

    return result
