from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.db as db_module
from app.auth import UserManager
from app.config import get_settings
from app.models import (
    Contract,
    ContractCategory,
    ContractFile,
    ContractStatus,
    Counterparty,
    Tag,
    User,
)
from app.schemas import UserCreate
from app.storage import storage_dir

DEMO_EMAIL = "demo@opendocket.example"
DEMO_PASSWORD = "demo-password-123"
DEMO_DISPLAY_NAME = "Demo User"


def _days(offset: int | None) -> date | None:
    if offset is None:
        return None
    return date.today() + timedelta(days=offset)


# (title, status, category, counterparty, effective, expiry, notice_days, value, currency, tags, notes, vn)
_CONTRACTS: list[tuple] = [
    (
        "KFZ-Haftpflichtversicherung",
        ContractStatus.active,
        ContractCategory.kfz_haftpflicht,
        "HUK-Coburg",
        -300,
        12,
        30,
        "610.00",
        "EUR",
        ["auto", "jaehrlich"],
        "Deckungssumme 100 Mio. EUR pauschal, Schadenfreiheitsklasse SF 12.",
        "VN-HUK-2024-0182",
    ),
    (
        "KFZ-Teilkasko",
        ContractStatus.active,
        ContractCategory.kfz_teilkasko,
        "HUK-Coburg",
        -300,
        12,
        30,
        "220.00",
        "EUR",
        ["auto", "jaehrlich"],
        None,
        None,
    ),
    (
        "KFZ-Schutzbrief",
        ContractStatus.active,
        ContractCategory.kfz_schutzbrief,
        "HUK-Coburg",
        -200,
        150,
        None,
        "49.00",
        None,
        ["auto"],
        "Europaweite Pannen- und Abschlepphilfe.",
        None,
    ),
    (
        "Wohngebäudeversicherung",
        ContractStatus.active,
        ContractCategory.wohngebaeude,
        "DEVK Versicherungen",
        -540,
        45,
        90,
        "420.00",
        "EUR",
        ["haus", "jaehrlich"],
        "Inklusive Elementarschaden. Versicherungssumme 450.000 EUR.",
        "VN-DEVK-2023-1104",
    ),
    (
        "Privathaftpflichtversicherung",
        ContractStatus.active,
        ContractCategory.privathaftpflicht,
        "DEVK Versicherungen",
        -800,
        75,
        90,
        "56.00",
        "EUR",
        ["familie", "jaehrlich"],
        None,
        None,
    ),
    (
        "Hausratversicherung",
        ContractStatus.active,
        ContractCategory.hausrat,
        "Allianz",
        -400,
        88,
        60,
        "130.00",
        "EUR",
        ["haus"],
        None,
        None,
    ),
    (
        "Rechtsschutzversicherung",
        ContractStatus.active,
        ContractCategory.rechtsschutz_privat,
        "ARAG",
        -200,
        120,
        90,
        "180.00",
        "EUR",
        ["familie"],
        "Privat-, Verkehrs- und Mietrechtsschutz in einem Paket.",
        None,
    ),
    (
        "Berufsunfähigkeitsversicherung",
        ContractStatus.active,
        ContractCategory.berufsunfaehigkeit,
        "CosmosDirekt",
        -1500,
        300,
        30,
        "780.00",
        "EUR",
        ["vorsorge", "monatlich"],
        "BU-Rente 1.500 EUR monatlich seit 2021.",
        None,
    ),
    (
        "Private Krankenversicherung",
        ContractStatus.active,
        ContractCategory.private_kv,
        "Allianz",
        -1000,
        None,
        90,
        "420.00",
        "EUR",
        ["gesundheit", "monatlich"],
        "Unbefristet. Tarif PKV Best.",
        "VN-ALL-2019-0077",
    ),
    (
        "Mobilfunkvertrag",
        ContractStatus.active,
        ContractCategory.mobilfunk_internet,
        "Telekom",
        -100,
        33,
        30,
        "49.00",
        "EUR",
        ["monatlich"],
        "MagentaMobil M mit 5G, 30 GB Datenvolumen.",
        None,
    ),
    (
        "Internet & Festnetz",
        ContractStatus.active,
        ContractCategory.mobilfunk_internet,
        "Vodafone",
        -250,
        250,
        30,
        "39.00",
        "EUR",
        ["monatlich"],
        None,
        None,
    ),
    (
        "Stromvertrag",
        ContractStatus.active,
        ContractCategory.energie,
        "Stadtwerke",
        -500,
        60,
        30,
        "89.00",
        "EUR",
        ["haus", "monatlich"],
        "Vertragslaufzeit 12 Monate, danach monatlich kündbar.",
        None,
    ),
    (
        "Riester-Rente",
        ContractStatus.active,
        ContractCategory.altersvorsorge,
        "Allianz",
        -900,
        15,
        60,
        "120.00",
        "EUR",
        ["vorsorge", "monatlich"],
        None,
        None,
    ),
    (
        "Mietvertrag Wohnung",
        ContractStatus.active,
        ContractCategory.mietvertrag,
        None,
        -1200,
        None,
        None,
        "850.00",
        "EUR",
        ["haus", "monatlich"],
        "Unbefristet. 3 Monate Kündigungsfrist.",
        None,
    ),
    (
        "Girokonto & Kreditkarte",
        ContractStatus.active,
        ContractCategory.sonstiges,
        "Deutsche Bank",
        -2000,
        None,
        None,
        "0.00",
        "EUR",
        ["banking"],
        "Kontoführung gebührenfrei.",
        None,
    ),
    (
        "Zahnzusatzversicherung",
        ContractStatus.draft,
        ContractCategory.zahnzusatz,
        None,
        None,
        None,
        None,
        "15.00",
        "EUR",
        ["gesundheit"],
        None,
        None,
    ),
    (
        "Unfallversicherung (Angebot)",
        ContractStatus.draft,
        ContractCategory.unfall,
        "AXA",
        None,
        None,
        None,
        None,
        None,
        [],
        "Angebot Nr. 4711 – Entscheidung offen.",
        None,
    ),
    (
        "Alte Handyversicherung",
        ContractStatus.expired,
        ContractCategory.sonstiges,
        "Vodafone",
        -700,
        -20,
        None,
        "6.00",
        "EUR",
        [],
        None,
        None,
    ),
    (
        "Fitnessstudio-Mitgliedschaft",
        ContractStatus.expired,
        ContractCategory.mitgliedschaft,
        None,
        -500,
        -100,
        None,
        "25.00",
        "EUR",
        [],
        "Gekündigt nach Vertragsende.",
        None,
    ),
    (
        "DSL-Vertrag (alt)",
        ContractStatus.terminated,
        ContractCategory.sonstiges,
        "Vodafone",
        -1800,
        -400,
        None,
        "29.00",
        "EUR",
        [],
        None,
        None,
    ),
    (
        "KFZ-Vollkasko (altes Auto)",
        ContractStatus.terminated,
        ContractCategory.kfz_vollkasko,
        "Allianz",
        -2200,
        -500,
        30,
        "640.00",
        "EUR",
        ["auto"],
        None,
        None,
    ),
]

_DEMO_FILE = (
    "Haftpflichtversicherung.txt",
    "text/plain",
    (
        "Haftpflichtversicherung (Privat)\n"
        "Vertragspartner: DEVK Versicherungen\n"
        "Vertragsnummer: VN-DEVK-2023-1104\n"
        "Laufzeit: 1 Jahr, jeweils zum Jahresende verlängerbar.\n"
        "Kündigungsfrist: 3 Monate zum Vertragsende.\n\n"
        "Dies ist eine Beispieldatei des Demo-Kontos."
    ),
)


async def _seed_data(session: AsyncSession, user: User) -> None:
    counterparties: dict[str, Counterparty] = {}
    tags: dict[str, Tag] = {}

    async def get_cp(name: str | None) -> Counterparty | None:
        if not name:
            return None
        if name not in counterparties:
            cp = Counterparty(owner_id=user.id, name=name)
            session.add(cp)
            await session.flush()
            counterparties[name] = cp
        return counterparties[name]

    async def get_tag(name: str) -> Tag:
        if name not in tags:
            existing = await session.scalar(
                select(Tag).where(Tag.owner_id == user.id, Tag.name == name)
            )
            if existing is None:
                existing = Tag(owner_id=user.id, name=name)
                session.add(existing)
                await session.flush()
            tags[name] = existing
        return tags[name]

    seeded_files = False
    for item in _CONTRACTS:
        (title, status, category, cp_name, eff, exp, notice, value, currency, tag_names, notes, vn) = item
        cp = await get_cp(cp_name)
        contract = Contract(
            owner_id=user.id,
            title=title,
            status=status,
            category=category,
            counterparty_id=cp.id if cp else None,
            effective_date=_days(eff),
            expiry_date=_days(exp),
            notice_days=notice,
            value=Decimal(value) if value else None,
            currency=currency,
            notes=notes,
        )
        if vn:
            contract.versicherungsnummer = vn
        contract.tags = [await get_tag(t) for t in tag_names]
        session.add(contract)
        await session.flush()

        if not seeded_files and title == "Privathaftpflichtversicherung":
            name, mime, content = _DEMO_FILE
            stored = f"{uuid.uuid4().hex}.txt"
            (storage_dir() / stored).write_text(content, encoding="utf-8")
            session.add(
                ContractFile(
                    contract_id=contract.id,
                    original_name=name,
                    stored_name=stored,
                    mime_type=mime,
                    size_bytes=len(content.encode("utf-8")),
                )
            )
            seeded_files = True

    await session.commit()


async def ensure_demo() -> None:
    settings = get_settings()
    if not settings.enable_demo:
        return
    async with db_module.AsyncSessionLocal() as session:
        user_db = SQLAlchemyUserDatabase(session, User)
        manager = UserManager(user_db)
        existing = await user_db.get_by_email(DEMO_EMAIL)
        if existing is not None:
            return
        user = await manager.create(
            UserCreate(
                email=DEMO_EMAIL,
                password=DEMO_PASSWORD,
                display_name=DEMO_DISPLAY_NAME,
            ),
            safe=False,
        )
        await _seed_data(session, user)
