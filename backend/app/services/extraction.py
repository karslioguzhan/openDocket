from __future__ import annotations

import base64
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
from app.models import ContractCategory

# File types we can extract text from. doc/docx/odt are uploadable but not
# extractable in v1 — the scan endpoint rejects them.
EXTRACTABLE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt"}

_VISION_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# When vision mode is enabled, we send rendered page images to the model.
# Cap the number of pages/images and their resolution to keep requests cheap.
_VISION_MAX_PAGES = 6
_VISION_MAX_DIM = 1568
_VISION_JPEG_QUALITY = 85

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
    re.compile(
        r"(?P<num>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\s*(?P<cur>€|EUR|US\$|USD|US\s*Dollar|\$|TRY|TL)(?!\w)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<cur>€|EUR|US\$|USD|US\s*Dollar|\$|TRY|TL)(?!\w)\s*(?P<num>\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)",
        re.IGNORECASE,
    ),
]

_CURRENCY_TO_CODE = {
    "€": "EUR", "eur": "EUR", "euro": "EUR",
    "$": "USD", "usd": "USD", "us$": "USD", "us dollar": "USD",
    "tl": "TRY", "try": "TRY",
}

# Keywords that mark an amount as the recurring amount the customer pays.
_AMOUNT_POSITIVE_KEYWORDS = re.compile(
    r"beitrag|prämi|praemi|monatlich|pro\s*monat|/monat\b|/jahr\b|pro\s*jahr|jährlich|jaehrlich|"
    r"quartalsweise|einmalig\b|zahlung|kosten\b|gebühr|gebuehr|grundgebühr|grundgebuehr|preis\b|"
    r"\bpremium\b|monthly|quarterly|annual|yearly|payment|tarif\b|vs\.?\s*beitrag",
    re.IGNORECASE,
)

# Keywords that mark an amount as a sum insured / coverage that is NOT the premium.
_AMOUNT_NEGATIVE_KEYWORDS = re.compile(
    r"versicherungssumme|deckungssumme|sum\s*insured|deckung\b|grundsumme|haftungssumme|"
    r"einmalige\s*leistung|leistungssumme|versicherungsleistung|jahresgesamtbeitrag|jahresbeitrag",
    re.IGNORECASE,
)

# Label directly preceding a number that marks it as a reference, not a value.
_AMOUNT_REF_LABEL_RE = re.compile(
    r"(?:nr\.?|nummer|no\.?|tel\.?|telefon|fax|blz|iban|kontonr|u[- ]?id|police|kunden)\s*[:.\-#]?\s*$",
    re.IGNORECASE,
)

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
    "vermieter": "vermieter",
    "kauf": "kauf",
    "verkäufer": "verkäufer", "verkaeufer": "verkäufer",
    "kunde": "kunde", "kundin": "kunde",
    "auftraggeber": "auftraggeber",
    "auftragnehmer": "auftragnehmer",
    "versicherer": "versicherer",
    "versicherungsgesellschaft": "versicherer",
    "versicherungsträger": "versicherer", "versicherungstraeger": "versicherer",
    "versicherungsnehmer": "versicherungsnehmer",
    "vertragspartner": "vertragspartner",
    "kontrahent": "vertragspartner",
    "anbieter": "anbieter", "anbieterin": "anbieter",
    "leistungserbringer": "anbieter",
    "lieferant": "anbieter",
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
    "contract partner": "vertragspartner",
}

_LEGAL_FORM_RE = re.compile(
    r"([A-ZÄÖÜ][A-Za-zÄÖÜßöäü .&'()/-]{2,60}?"
    r"(?:GmbH|AG|KG|e\.?\s*V\.?|UG|Inc\.?|Ltd\.?|LLC|S\.?A\.?|B\.?V\.?|SE|GbR|"
    r"VVaG|LLP|e\.?G\.?|e\.?K\.?|Krankenkasse|Sparkasse|Bank|Genossenschaft|Stiftung|"
    r"Versicherungsverein|Gemeinschaft|Verband)(?!\w))",
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

# Category detection: ordered most-specific-first (regex, ContractCategory).
# The first matching rule wins, so place specific forms before generic ones.
_CATEGORY_RULES: list[tuple[re.Pattern[str], ContractCategory]] = [
    (re.compile(r"kfz[- ]?haftpflicht|motor\s*haftpflicht|pkz[- ]?haftpflicht", re.IGNORECASE), ContractCategory.kfz_haftpflicht),
    (re.compile(r"teilkasko", re.IGNORECASE), ContractCategory.kfz_teilkasko),
    (re.compile(r"kasko\s*(?:versicherung)?|voll\s*kasko", re.IGNORECASE), ContractCategory.kfz_vollkasko),
    (re.compile(r"schutzbrief", re.IGNORECASE), ContractCategory.kfz_schutzbrief),
    (re.compile(r"motorrad\s*versicherung|motorradversicherung", re.IGNORECASE), ContractCategory.motorrad),
    (re.compile(r"fahrrad|e[- ]?bike|pedelec", re.IGNORECASE), ContractCategory.fahrrad),
    (re.compile(r"tierhalterhaftpflicht|haustier|hund|katze", re.IGNORECASE), ContractCategory.tierhalterhaftpflicht),
    (re.compile(r"haus[- ]?und\s*grundbesitzer|gebäudehaftpflicht|gebaeudehaftpflicht|grundbesitzerhaftpflicht", re.IGNORECASE), ContractCategory.haus_haftpflicht),
    (re.compile(r"berufshaftpflicht", re.IGNORECASE), ContractCategory.berufshaftpflicht),
    (re.compile(r"privathaftpflicht|private\s*haftpflicht", re.IGNORECASE), ContractCategory.privathaftpflicht),
    (re.compile(r"gesetzliche\s*krankenversicherung|gesetzlich\s*versichert|krankenkasse\b", re.IGNORECASE), ContractCategory.gesetzliche_kv),
    (re.compile(r"private\s*krankenversicherung|privat\s*krankenversichert", re.IGNORECASE), ContractCategory.private_kv),
    (re.compile(r"zahnzusatz|zahn[- ]?behandlung", re.IGNORECASE), ContractCategory.zahnzusatz),
    (re.compile(r"pflegezusatz|pflegeversicherung|pflegepflichtversicherung", re.IGNORECASE), ContractCategory.pflegezusatz),
    (re.compile(r"krankenzusatz|zusatzversicherung", re.IGNORECASE), ContractCategory.kv_zusatz),
    (re.compile(r"krankenversicherung", re.IGNORECASE), ContractCategory.private_kv),
    (re.compile(r"risikolebensversicherung|risikoleben", re.IGNORECASE), ContractCategory.risikoleben),
    (re.compile(r"berufsunfähigkeitsversicherung|berufsunfaehigkeitsversicherung|berufsunfähigkeit|berufsunfaehigkeit|\bbu[- ]?versicherung", re.IGNORECASE), ContractCategory.berufsunfaehigkeit),
    (re.compile(r"rürup|ruerup|riester|altersvorsorge", re.IGNORECASE), ContractCategory.altersvorsorge),
    (re.compile(r"rentenversicherung|kapitalversicherung|lebensversicherung", re.IGNORECASE), ContractCategory.rentenversicherung),
    (re.compile(r"kinderunfall", re.IGNORECASE), ContractCategory.kinderunfall),
    (re.compile(r"insassenunfall", re.IGNORECASE), ContractCategory.insassenunfall),
    (re.compile(r"unfallversicherung|unfall", re.IGNORECASE), ContractCategory.unfall),
    (re.compile(r"wohngebäude|wohngebaeude|gebäudeversicherung|gebaeudeversicherung|haus[- ]?versicherung", re.IGNORECASE), ContractCategory.wohngebaeude),
    (re.compile(r"hausrat", re.IGNORECASE), ContractCategory.hausrat),
    (re.compile(r"elementar(?:schaden)?", re.IGNORECASE), ContractCategory.elementar),
    (re.compile(r"glasversicherung|\bglas\b", re.IGNORECASE), ContractCategory.glas),
    (re.compile(r"rechtsschutz.*(verkehr|kfz|fahrzeug)", re.IGNORECASE), ContractCategory.rechtsschutz_verkehr),
    (re.compile(r"rechtsschutz.*(miet|arbeits|arbeit)", re.IGNORECASE), ContractCategory.rechtsschutz_miet_arbeit),
    (re.compile(r"rechtsschutz", re.IGNORECASE), ContractCategory.rechtsschutz_privat),
    (re.compile(r"mietvertrag|mieter|vermiet(er|ung)|wohnungsvertrag", re.IGNORECASE), ContractCategory.mietvertrag),
    (re.compile(r"mobilfunk|handy|smartphone|internet(?:vertrag)?|breitband|dsl\b", re.IGNORECASE), ContractCategory.mobilfunk_internet),
    (re.compile(r"strom|gas(?:vertrag)?|energie(?:vertrag)?|energieversorgung|stromversorgung", re.IGNORECASE), ContractCategory.energie),
    (re.compile(r"kredit|darlehen|ratenkredit", re.IGNORECASE), ContractCategory.kredit),
    (re.compile(r"mitgliedschaft|abo\b|subscription|abonnement", re.IGNORECASE), ContractCategory.mitgliedschaft),
    (re.compile(r"garantie|wartung|service(?:vertrag)?|maintenance", re.IGNORECASE), ContractCategory.garantie_wartung),
]

# Common German category labels -> enum key, used to interpret LLM output.
_CATEGORY_LABELS: dict[str, ContractCategory] = {
    "kfz-haftpflicht": ContractCategory.kfz_haftpflicht,
    "kfz haftpflicht": ContractCategory.kfz_haftpflicht,
    "kfz_haftpflicht": ContractCategory.kfz_haftpflicht,
    "kfz-teilkasko": ContractCategory.kfz_teilkasko,
    "kfz_vollkasko": ContractCategory.kfz_vollkasko,
    "kfz-vollkasko": ContractCategory.kfz_vollkasko,
    "kfz-schutzbrief": ContractCategory.kfz_schutzbrief,
    "motorradversicherung": ContractCategory.motorrad,
    "fahrradversicherung": ContractCategory.fahrrad,
    "privathaftpflicht": ContractCategory.privathaftpflicht,
    "tierhalterhaftpflicht": ContractCategory.tierhalterhaftpflicht,
    "haus- und grundbesitzerhaftpflicht": ContractCategory.haus_haftpflicht,
    "haus und grundbesitzerhaftpflicht": ContractCategory.haus_haftpflicht,
    "berufshaftpflicht": ContractCategory.berufshaftpflicht,
    "gesetzliche krankenversicherung": ContractCategory.gesetzliche_kv,
    "krankenversicherung": ContractCategory.private_kv,
    "private krankenversicherung": ContractCategory.private_kv,
    "krankenzusatzversicherung": ContractCategory.kv_zusatz,
    "zusatzversicherung": ContractCategory.kv_zusatz,
    "zahnzusatzversicherung": ContractCategory.zahnzusatz,
    "pflegezusatzversicherung": ContractCategory.pflegezusatz,
    "pflegeversicherung": ContractCategory.pflegezusatz,
    "risikolebensversicherung": ContractCategory.risikoleben,
    "rentenversicherung": ContractCategory.rentenversicherung,
    "kapital-rentenversicherung": ContractCategory.rentenversicherung,
    "altersvorsorge": ContractCategory.altersvorsorge,
    "berufsunfähigkeitsversicherung": ContractCategory.berufsunfaehigkeit,
    "berufsunfaehigkeitsversicherung": ContractCategory.berufsunfaehigkeit,
    "unfallversicherung": ContractCategory.unfall,
    "kinderunfallversicherung": ContractCategory.kinderunfall,
    "insassenunfallversicherung": ContractCategory.insassenunfall,
    "wohngebäudeversicherung": ContractCategory.wohngebaeude,
    "wohngebaeudeversicherung": ContractCategory.wohngebaeude,
    "hausratversicherung": ContractCategory.hausrat,
    "elementarschadenversicherung": ContractCategory.elementar,
    "glasversicherung": ContractCategory.glas,
    "rechtsschutzversicherung": ContractCategory.rechtsschutz_privat,
    "rechtsschutz": ContractCategory.rechtsschutz_privat,
    "verkehrs-rechtsschutz": ContractCategory.rechtsschutz_verkehr,
    "miet-rechtsschutz": ContractCategory.rechtsschutz_miet_arbeit,
    "mietvertrag": ContractCategory.mietvertrag,
    "mobilfunkvertrag": ContractCategory.mobilfunk_internet,
    "internetvertrag": ContractCategory.mobilfunk_internet,
    "energievertrag": ContractCategory.energie,
    "stromvertrag": ContractCategory.energie,
    "gasvertrag": ContractCategory.energie,
    "kreditvertrag": ContractCategory.kredit,
    "mitgliedschaft": ContractCategory.mitgliedschaft,
    "abo": ContractCategory.mitgliedschaft,
    "garantievertrag": ContractCategory.garantie_wartung,
    "wartungsvertrag": ContractCategory.garantie_wartung,
    "sonstiges": ContractCategory.sonstiges,
}


def _detect_category(text: str) -> ContractCategory | None:
    """Classify the contract type from its text via keyword rules."""
    for pattern, category in _CATEGORY_RULES:
        if pattern.search(text):
            return category
    return None


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
    return _pdf_pipeline(data)[0]


def _pdf_pipeline(data: bytes) -> tuple[str, list[bytes]]:
    """Extract text and, if possible, up to _VISION_MAX_PAGES JPEG page renders.

    Returns ``(text, images)``. ``text`` falls back to OCR when the embedded
    text layer is too thin (scanned documents); ``images`` are kept so vision
    models can look at the actual pages directly.
    """
    text = ""
    try:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        text = ""

    images: list[bytes] = []
    try:
        import fitz

        doc = fitz.open(stream=data, filetype="pdf")
        for idx, page in enumerate(doc):
            if idx >= _VISION_MAX_PAGES:
                break
            pix = page.get_pixmap(dpi=200)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            images.append(_to_jpeg(img))
    except Exception:
        return text, images

    if len(text.strip()) >= 80:
        return text, images

    ocr_text = ""
    for jpeg in images:
        try:
            ocr_text += _ocr_image_bytes(Image.open(io.BytesIO(jpeg)))
        except Exception:
            continue

    return (text + "\n" + ocr_text).strip() or text, images


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


def _to_jpeg(img: Image.Image) -> bytes:
    """Downscale and re-encode an image as JPEG for vision requests."""
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.thumbnail((_VISION_MAX_DIM, _VISION_MAX_DIM))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_VISION_JPEG_QUALITY)
    return buf.getvalue()


def vision_images_from_bytes(filename: str, data: bytes) -> list[bytes]:
    """Return JPEG bytes suitable for a vision LLM request (or [] if none)."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _pdf_pipeline(data)[1]
    if suffix in _VISION_IMAGE_EXTENSIONS:
        try:
            img = Image.open(io.BytesIO(data))
            return [_to_jpeg(img)]
        except (UnidentifiedImageError, OSError):
            return []
    return []


def parse_contract_documents(
    files: list[tuple[str, bytes]], llm_config: dict[str, str] | None = None, use_vision: bool = False
) -> dict[str, Any]:
    """Parse a list of (filename, bytes) into extracted contract fields.

    ``llm_config`` optionally overrides the server-side LLM settings with
    per-request values (``base_url``, ``api_key``, ``model``). When
    ``use_vision`` is true, rendered page images are sent to the LLM alongside
    the extracted text.
    """
    texts: list[str] = []
    images: list[bytes] = []
    for name, data in files:
        text = extract_text_from_bytes(name, data)
        if text.strip():
            texts.append(text)
        if use_vision:
            images.extend(vision_images_from_bytes(name, data))

    combined = "\n\n".join(texts)
    if not combined.strip():
        return {}

    heuristics = _parse_heuristically(combined, files[0][0] if files else "")
    llm = _parse_with_llm(combined, images=images or None, llm_config=llm_config)
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
        "versicherungsnehmer": _detect_versicherungsnehmer(text),
        "versicherungsnummer": _detect_policy_number(text),
        "category": _detect_category(text),
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
    """Find the contract value, preferring the recurring amount the customer pays.

    All amounts with a currency are scored: amounts near premium/contribution
    keywords (Beitrag, Prämie, monatlich, jährlich, fee, premium, ...) are
    preferred; amounts near sum-insured keywords (Versicherungssumme, ...) or
    reference numbers are penalized.
    """
    candidates: list[tuple[int, Decimal, str, int]] = []
    for pattern in _AMOUNT_RE:
        for match in pattern.finditer(text):
            amount = _normalize_amount(match.group("num"))
            if amount is None:
                continue
            code = _CURRENCY_TO_CODE.get(match.group("cur").lower(), None)
            if not code or not (0 < amount < 10 ** 13):
                continue

            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end == -1:
                line_end = len(text)
            line = text[line_start:line_end]

            score = 0
            if _AMOUNT_POSITIVE_KEYWORDS.search(line):
                score += 4
            if _AMOUNT_NEGATIVE_KEYWORDS.search(line):
                score -= 6
            if _AMOUNT_REF_LABEL_RE.search(line[: match.start() - line_start][-30:]):
                score -= 2
            candidates.append((score, amount, code, match.start()))

    if not candidates:
        return None, None
    candidates.sort(key=lambda c: (-c[0], c[3]))
    best = candidates[0]
    return best[1], best[2]


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
    letterhead = _detect_letterhead_company(text)
    candidates: list[str] = []
    for line in text.splitlines()[:20]:
        line = line.strip().strip("*#")
        if not line or len(line) < 3 or len(line) > 160:
            continue
        if _SKIP_LINE_RE.search(line) or _SECTION_LABELS_RE.match(line) or _TITLE_SKIP_RE.match(line):
            continue
        if _PLZ_CITY_RE.search(line) or _STREET_ADDRESS_RE.match(line) or _HONORIFIC_RE.match(line):
            continue
        if not re.search(r"[A-Za-zÄÖÜäöü]", line):
            continue
        candidates.append(line)

    for line in candidates:
        if _TITLE_KEYWORD_RE.search(line) and line != letterhead:
            return line[:160]
    for line in candidates:
        if not _looks_like_company_line(line):
            return line[:160]
    if letterhead:
        return letterhead[:160]
    stem = Path(filename).stem
    return stem[:200] if stem else None


_COUNTERPARTY_BAD_START = re.compile(
    r"^(vertrag|contract|agreement|vereinbarung|policy|versicherungsschein|versicherungsvertrag"
    r"|dokument|document|rechnung|invoice|bestätigung|bestaetigung|über|ueber|zwischen)",
    re.IGNORECASE,
)

_LETTERHEAD_SALUTATION_RE = re.compile(
    r"sehr\s+geehrte|liebe\s+r|guten\s+tag|betreff\s*[:]?|versicherungsschein|versicherungsvertrag|"
    r"vertragsnr|rechnung\s*nr|invoice\s*no|customer\s*no|kundennr|datum\s*[:]?|stand\s*[:]?",
    re.IGNORECASE,
)

_PLZ_CITY_RE = re.compile(r"\b\d{4,5}\s+[A-ZÄÖÜ][a-zäöüß]")

_ADDRESS_LINE_RE = re.compile(
    r"\bstr(?:aße)?\.?\b|\bstraße\b|\bstreet\b|\bdrive\b|\broad\b|\brd\.?\b|\bavenue\b|"
    r"\bave\.?\b|\bboulevard\b|\bblvd\b|\blane\b|\bgasse\b|\bweg\b|\ballee\b|\balley\b|"
    r"\bplace\b|\bplatz\b|\bway\b|\bhouse\b",
    re.IGNORECASE,
)

_STREET_ADDRESS_RE = re.compile(
    r"^[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß.\-\s]{1,35}\d{1,4}[a-z]?$",
    re.IGNORECASE,
)

_TITLE_KEYWORD_RE = re.compile(
    r"vertrag|vereinbarung|versicherung|police\b|schein\b|rechnung|angebot|vollmacht|"
    r"kündigung|kuendigung|mietvertrag|agreement|contract|insurance|invoice|policy|"
    r"receipt|billing|quote|memorandum|vorsorge",
    re.IGNORECASE,
)

_TITLE_SKIP_RE = re.compile(
    r"^(?:versicherungsnr|versicherungsnummer|versicherungsschein|policennummer|police\s*nr|"
    r"vertragsnummer|vertrags\s*nr|kundennummer|kunden\s*nr|mitgliedsnummer|mitglied\s*nr|"
    r"datum|stand|seite|tel\b|telefon|fax|e-?mail|www|http|konto|iban|steuer|blz)",
    re.IGNORECASE,
)

_HONORIFIC_RE = re.compile(r"^(herr|frau|fr\.?|mr\.?|mrs\.?|ms\.?)\b", re.IGNORECASE)


def _looks_like_company_line(line: str) -> bool:
    if not line or len(line) > 120 or len(line) < 3:
        return False
    if _SKIP_LINE_RE.search(line) or _DATE_TOKEN_RE.search(line):
        return False
    if _LETTERHEAD_SALUTATION_RE.search(line) or ":" in line:
        return False
    if _HONORIFIC_RE.match(line):
        return False
    if line.count(",") > 1:
        return False
    # sentence-like lines (several lowercase words) are not company headers
    if re.search(r"\b[a-zäöüß]{4,}\s+[a-zäöüß]{4,}\b", line):
        return False
    words = re.findall(r"[A-Za-zÄÖÜäöüß0-9&.'/-]+", line)
    capitals = [w for w in words if w and w[0].isupper()]
    return len(words) >= 1 and len(capitals) >= 1


def _detect_letterhead_company(text: str) -> str | None:
    """Find the company in a letterhead (first lines before any labels/salutation)."""
    lines = [ln.strip() for ln in text.splitlines()[:20] if ln.strip()]
    for i, line in enumerate(lines):
        if _LETTERHEAD_SALUTATION_RE.search(line) or _SECTION_LABELS_RE.match(line):
            break
        if not _looks_like_company_line(line):
            continue
        if _LEGAL_FORM_RE.search(line):
            return line.strip(":.,;")[:120]
        following = lines[i + 1: i + 4]
        if any(_PLZ_CITY_RE.search(nxt) or _ADDRESS_LINE_RE.search(nxt) for nxt in following):
            return line.strip(":.,;")[:120]
    return None


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

    letterhead = _detect_letterhead_company(text)
    if letterhead is not None:
        return letterhead

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


def _detect_versicherungsnehmer(text: str) -> str | None:
    """Find the insured person (Versicherungsnehmer) after the matching label."""
    for line in text.splitlines():
        m = _SECTION_LABELS_RE.match(line)
        if not m:
            continue
        if m.group(1).lower() not in {"versicherungsnehmer", "insured"}:
            continue
        name = m.group(2).strip().strip(":.,;")
        if not name or len(name) > 120:
            continue
        if _SKIP_LINE_RE.search(name) or _DATE_TOKEN_RE.search(name):
            continue
        if not re.search(r"[A-Za-zÄÖÜäöü]", name):
            continue
        if _COUNTERPARTY_BAD_START.match(name):
            continue
        return name[:120]
    return None


def call_chat_completion(
    base_url: str,
    api_key: str | None,
    model: str,
    system: str,
    user_text: str,
    timeout: float = 60,
    images: list[bytes] | None = None,
) -> str:
    """Send an OpenAI-style chat completion and return the assistant's text.

    When ``images`` is provided (JPEG bytes), the request uses a multimodal
    ``content`` array with ``image_url`` parts so vision-capable models can see
    the documents. Raises on transport/HTTP errors so callers can decide how to
    handle them.
    """
    headers = {}
    api_key = (api_key or "").strip() or None
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if images:
        content: list[dict[str, object]] = [{"type": "text", "text": user_text}]
        content.extend(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(img).decode()}"},
            }
            for img in images
        )
        user_message: object = content
    else:
        user_message = user_text

    resp = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
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


def _parse_with_llm(
    text: str, images: list[bytes] | None = None, llm_config: dict[str, str] | None = None
) -> dict[str, Any]:
    settings = get_settings()
    base_url = (llm_config or {}).get("base_url") or settings.llm_base_url
    api_key = (llm_config or {}).get("api_key") or settings.llm_api_key
    model = (llm_config or {}).get("model") or settings.llm_model
    if not (base_url and model):
        return {}

    categories = ", ".join(c.value for c in ContractCategory)
    system = (
        "You extract structured data from contract documents. "
        "Return ONLY a valid JSON object with these keys: "
        "title (string or null), counterparty_name (string or null), "
        "versicherungsnehmer (string or null, the insured person / policyholder, "
        "also known as Versicherungsnehmer), "
        "versicherungsnummer (string or null, the insurance/policy/contract number, "
        "also known as Versicherungsnummer, Versicherungsnr., Policennummer or Vertragsnummer), "
        "category (string or null, one of these exact keys: "
        + categories
        + "), "
        "effective_date (YYYY-MM-DD or null), expiry_date (YYYY-MM-DD or null), "
        "notice_days (integer or null), value (number or null), "
        "currency (ISO 4217 code or null). "
        "Guidance: counterparty_name is the other contracting party (the insurer, "
        "provider, landlord or seller the customer has the contract with), usually "
        "found in the letterhead or after labels like 'Versicherer', 'Vertragspartner' "
        "or 'Customer'. Do NOT return the insured person's or customer's own name. "
        "versicherungsnehmer is the insured person / policyholder the contract belongs "
        "to, usually found after labels like 'Versicherungsnehmer' or 'Insured' - "
        "it is the person's own name, NOT the insurer, and NOT the contract type. "
        "value is the recurring amount the customer pays (monthly/annual premium or "
        "fee, Beitrag/Prämie); prefer it over a sum insured or one-off total. "
        "If several recurring amounts exist, prefer the monthly one; if only an "
        "annual total exists, use that. Use null when a value cannot be determined "
        "from the text. Do not invent data."
    )
    user_text = f"Document text:\n{text[:12000]}"
    if images:
        for attempt_images in (images, None):
            try:
                content = call_chat_completion(
                    base_url, api_key, model, system, user_text, timeout=120, images=attempt_images
                )
                return _normalize_llm_result(content)
            except Exception:
                continue
        return {}

    try:
        content = call_chat_completion(base_url, api_key, model, system, user_text, timeout=120)
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
    if isinstance(data.get("versicherungsnehmer"), str) and data["versicherungsnehmer"].strip():
        result["versicherungsnehmer"] = data["versicherungsnehmer"].strip()[:200]
    if isinstance(data.get("versicherungsnummer"), str) and data["versicherungsnummer"].strip():
        result["versicherungsnummer"] = data["versicherungsnummer"].strip()[:40]

    category = _normalize_category(data.get("category"))
    if category is not None:
        result["category"] = category

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


def _normalize_category(raw: object) -> str | None:
    """Accept an enum key or a common (German) label; return the enum key or None."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = raw.strip()
    lowered = value.lower().replace("_", "-").replace(" ", "-").replace("ü", "ue").replace("ä", "ae").replace("ö", "oe")
    for member in ContractCategory:
        if member.value == value or member.value.replace("_", "-") == lowered:
            return member.value
    mapped = _CATEGORY_LABELS.get(value.lower())
    if mapped is not None:
        return mapped.value
    return None
