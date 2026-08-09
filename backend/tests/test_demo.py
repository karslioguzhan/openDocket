from __future__ import annotations

import app.db as db_module
from app.models import User
from app.services.demo import DEMO_EMAIL, DEMO_SEED_VERSION, ensure_demo


async def test_demo_login_creates_and_logs_in(client, login):
    resp = await client.post("/api/auth/demo-login")
    assert resp.status_code == 204, resp.text

    me = await client.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == DEMO_EMAIL
    assert me.json()["is_superuser"] is False


async def test_demo_login_is_idempotent(client):
    first = await client.post("/api/auth/demo-login")
    second = await client.post("/api/auth/demo-login")
    assert first.status_code == 204 and second.status_code == 204

    me = await client.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == DEMO_EMAIL


async def test_demo_contracts_populate_board_and_dashboard(client):
    await client.post("/api/auth/demo-login")

    contracts = await client.get("/api/contracts")
    assert contracts.status_code == 200
    rows = contracts.json()
    assert len(rows) >= 15

    statuses = {c["status"] for c in rows}
    assert {"active", "draft", "expired", "terminated"} <= statuses

    with_expiry = [c for c in rows if c["expiry_date"]]
    assert len(with_expiry) >= 5
    with_value = [c for c in rows if c["value"]]
    assert len(with_value) >= 5

    dashboard = await client.get("/api/dashboard")
    assert dashboard.status_code == 200
    data = dashboard.json()
    assert data["expiring_soon"], "expected expiring contracts on the dashboard"
    assert data["status_counts"]["active"] >= 5


async def test_demo_contract_has_attached_file(client):
    await client.post("/api/auth/demo-login")
    contracts = await client.get("/api/contracts")
    rows = contracts.json()
    haftpflicht = next(c for c in rows if c["title"] == "Privathaftpflichtversicherung")
    detail = await client.get(f"/api/contracts/{haftpflicht['id']}")
    assert detail.status_code == 200
    files = detail.json()["files"]
    assert len(files) == 1
    assert files[0]["original_name"] == "Haftpflichtversicherung.txt"


async def test_demo_user_isolated_from_other_users(client, make_user, login):
    await make_user("bob@example.com")
    await login(client, "bob@example.com")
    bob_contracts = await client.get("/api/contracts")
    assert bob_contracts.json() == []

    await client.post("/api/auth/logout")
    await client.post("/api/auth/demo-login")
    demo_contracts = await client.get("/api/contracts")
    assert len(demo_contracts.json()) >= 15


async def test_demo_contracts_cover_all_groups(client):
    await client.post("/api/auth/demo-login")
    all_rows = (await client.get("/api/contracts")).json()
    assert len(all_rows) >= 35

    kfz = (await client.get("/api/contracts?group=kfz")).json()
    assert kfz
    kfz_categories = {c["category"] for c in kfz}
    assert kfz_categories <= {
        "kfz_haftpflicht",
        "kfz_teilkasko",
        "kfz_vollkasko",
        "kfz_schutzbrief",
        "motorrad",
        "fahrrad",
    }

    vorsorge = (await client.get("/api/contracts?group=vorsorge")).json()
    assert vorsorge
    assert all(
        c["category"]
        in {"risikoleben", "rentenversicherung", "altersvorsorge", "berufsunfaehigkeit"}
        for c in vorsorge
    )


async def test_demo_counterparty_types(client):
    await client.post("/api/auth/demo-login")
    cps = (await client.get("/api/counterparties")).json()
    by_name = {c["name"]: c["type"] for c in cps}

    assert by_name["HUK-Coburg"] == "company"
    assert by_name["DEVK Versicherungen"] == "company"
    assert by_name["Max Mustermann"] == "person"
    assert by_name["Anna Schmidt"] == "person"
    assert by_name["Lisa Fischer"] == "person"

    contracts = (await client.get("/api/contracts")).json()
    person_linked = next(
        c for c in contracts if c["counterparty"] and c["counterparty"]["name"] == "Max Mustermann"
    )
    assert person_linked["counterparty"]["type"] == "person"


async def test_demo_reseeds_when_seed_version_outdated(client):
    from sqlalchemy import select

    await client.post("/api/auth/demo-login")
    first_count = len((await client.get("/api/contracts")).json())

    async with db_module.AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
        assert user is not None
        user.demo_seed_version = 0
        await session.commit()

    await ensure_demo()

    async with db_module.AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
        assert user.demo_seed_version == DEMO_SEED_VERSION

    await client.post("/api/auth/demo-login")
    after = (await client.get("/api/contracts")).json()
    assert len(after) == first_count  # replaced, not duplicated


async def test_demo_versicherungsnehmer(client):
    await client.post("/api/auth/demo-login")
    rows = (await client.get("/api/contracts")).json()
    assert len(rows) >= 35
    assert all(c["versicherungsnehmer"] for c in rows)

    kfz = next(c for c in rows if c["title"] == "KFZ-Haftpflichtversicherung")
    assert kfz["versicherungsnehmer"]["name"] == "Demo User"
    assert kfz["versicherungsnehmer"]["type"] == "person"

    child = next(c for c in rows if c["title"] == "Kinderunfallversicherung")
    assert child["versicherungsnehmer"]["name"] == "Elena Beispiel"
