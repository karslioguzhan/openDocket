from __future__ import annotations

import httpx


async def make_contract(
    c: httpx.AsyncClient, title: str = "Lease", **overrides
) -> dict:
    payload = {"title": title, "status": "active", **overrides}
    resp = await c.post("/api/contracts", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_and_get(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client, title="Apartment Lease")
    assert contract["title"] == "Apartment Lease"
    assert contract["status"] == "active"
    assert contract["role"] == "owner"

    got = await client.get(f"/api/contracts/{contract['id']}")
    assert got.status_code == 200
    assert got.json()["title"] == "Apartment Lease"


async def test_list_and_search(client, owner, login):
    await login(client, "owner@example.com")
    await make_contract(client, title="Gym Membership")
    await make_contract(client, title="Insurance Policy")
    rows = await client.get("/api/contracts")
    assert rows.status_code == 200
    assert len(rows.json()) == 2

    found = await client.get("/api/contracts", params={"search": "gym"})
    assert len(found.json()) == 1
    assert found.json()[0]["title"] == "Gym Membership"

    filtered = await client.get("/api/contracts", params={"status": "draft"})
    assert len(filtered.json()) == 0


async def test_update(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client)
    resp = await client.patch(
        f"/api/contracts/{contract['id']}",
        json={"title": "Renamed", "status": "terminated"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Renamed"
    assert body["status"] == "terminated"


async def test_tags_and_category(client, owner, login):
    await login(client, "owner@example.com")
    cats = (await client.get("/api/meta/categories")).json()
    keys = [c["key"] for c in cats]
    assert "privathaftpflicht" in keys
    assert "sonstiges" in keys
    privathaftpflicht = next(c for c in cats if c["key"] == "privathaftpflicht")
    assert privathaftpflicht["group"] == "haftpflicht"

    contract = await make_contract(
        client, tags=["home", "monthly"], category="privathaftpflicht"
    )
    assert set(contract["tags"]) == {"home", "monthly"}
    assert contract["category"] == "privathaftpflicht"

    # update tags (replace)
    resp = await client.patch(
        f"/api/contracts/{contract['id']}", json={"tags": ["work"]}
    )
    assert resp.json()["tags"] == ["work"]

    # invalid category rejected
    resp = await client.patch(
        f"/api/contracts/{contract['id']}", json={"category": "not_a_category"}
    )
    assert resp.status_code == 422


async def test_trash_restore(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client)
    resp = await client.delete(f"/api/contracts/{contract['id']}")
    assert resp.status_code == 204

    listed = await client.get("/api/contracts")
    assert listed.json() == []
    trashed = await client.get("/api/contracts", params={"trashed": True})
    assert len(trashed.json()) == 1

    restored = await client.post(f"/api/contracts/{contract['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None
    assert len((await client.get("/api/contracts")).json()) == 1


async def test_duplicate(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client, title="Car Insurance")
    dup = await client.post(f"/api/contracts/{contract['id']}/duplicate")
    assert dup.status_code == 201
    body = dup.json()
    assert body["title"] == "Car Insurance (copy)"
    assert body["status"] == "draft"
    assert body["id"] != contract["id"]


async def test_versicherungsnummer_auto_generated(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client, title="Haftpflicht")
    assert contract["versicherungsnummer"]
    assert contract["versicherungsnummer"].startswith("VN-")
    assert len(contract["versicherungsnummer"]) == 11


async def test_versicherungsnummer_provided(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(
        client, title="Kranken", versicherungsnummer="K123456789"
    )
    assert contract["versicherungsnummer"] == "K123456789"


async def test_versicherungsnummer_cleared_regenerates(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client, title="Kranken")
    resp = await client.patch(
        f"/api/contracts/{contract['id']}",
        json={"versicherungsnummer": None},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["versicherungsnummer"]
    assert body["versicherungsnummer"].startswith("VN-")
    assert body["versicherungsnummer"] != contract["versicherungsnummer"]


async def test_duplicate_generates_new_versicherungsnummer(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client, title="Car Insurance")
    dup = await client.post(f"/api/contracts/{contract['id']}/duplicate")
    body = dup.json()
    assert body["versicherungsnummer"]
    assert body["versicherungsnummer"] != contract["versicherungsnummer"]


async def test_counterparty_auto_created_from_name(client, owner, login):
    await login(client, "owner@example.com")
    resp = await client.post(
        "/api/contracts",
        json={"title": "Handyvertrag", "status": "active", "counterparty_name": "Telekom GmbH"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["counterparty"] is not None
    assert body["counterparty"]["name"] == "Telekom GmbH"

    cps = await client.get("/api/counterparties")
    assert len(cps.json()) == 1
    assert cps.json()[0]["name"] == "Telekom GmbH"


async def test_counterparty_name_reuses_existing(client, owner, login):
    await login(client, "owner@example.com")
    created = await client.post(
        "/api/counterparties", json={"name": "Acme GmbH"}
    )
    assert created.status_code == 201
    cp_id = created.json()["id"]

    for name in ["acme gmbh", "Acme"]:
        resp = await client.post(
            "/api/contracts",
            json={"title": "Agreement", "status": "active", "counterparty_name": name},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["counterparty"]["id"] == cp_id

    cps = await client.get("/api/counterparties")
    assert len(cps.json()) == 1


async def test_counterparty_type_roundtrip(client, make_user, login):
    await make_user("cptype@example.com")
    await login(client, "cptype@example.com")

    created = await client.post(
        "/api/counterparties", json={"name": "Max Mustermann", "type": "person"}
    )
    assert created.status_code == 201
    assert created.json()["type"] == "person"

    updated = await client.patch(
        f"/api/counterparties/{created.json()['id']}", json={"type": "company"}
    )
    assert updated.status_code == 200
    assert updated.json()["type"] == "company"


async def test_versicherungsnehmer_by_name(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(
        client,
        title="Haftpflicht",
        counterparty_name="HUK-Coburg",
        versicherungsnehmer_name="Max Mustermann",
    )
    assert contract["versicherungsnehmer"]["name"] == "Max Mustermann"
    assert contract["versicherungsnehmer"]["type"] == "person"
    assert contract["counterparty"]["name"] == "HUK-Coburg"

    again = await make_contract(
        client, title="Teilkasko", versicherungsnehmer_name="Max Mustermann"
    )
    assert again["versicherungsnehmer"]["id"] == contract["versicherungsnehmer"]["id"]

    cps = (await client.get("/api/counterparties")).json()
    assert len([c for c in cps if c["name"] == "Max Mustermann"]) == 1


async def test_versicherungsnehmer_by_id_and_update(client, owner, login):
    await login(client, "owner@example.com")
    person = await client.post("/api/counterparties", json={"name": "Anna", "type": "person"})
    pid = person.json()["id"]

    contract = await make_contract(client, title="BU", versicherungsnehmer_id=pid)
    assert contract["versicherungsnehmer"]["id"] == pid

    company = await client.post("/api/counterparties", json={"name": "Acme GmbH"})
    bad = await client.post(
        "/api/contracts",
        json={"title": "Bad", "status": "active", "versicherungsnehmer_id": company.json()["id"]},
    )
    assert bad.status_code == 400

    cleared = await client.patch(
        f"/api/contracts/{contract['id']}", json={"versicherungsnehmer_name": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["versicherungsnehmer"] is None


async def test_versicherungsnehmer_extraction_heuristic():
    from app.services.extraction import _detect_versicherungsnehmer

    text = "Versicherungsnehmer: Max Mustermann\nVersicherer: HUK-Coburg AG\nBeitrag: 610,00 EUR"
    assert _detect_versicherungsnehmer(text) == "Max Mustermann"
    assert _detect_versicherungsnehmer("Versicherer: HUK-Coburg AG\nBeitrag: 610 EUR") is None


async def test_counterparty_id_rejects_other_owners(client, owner, viewer, login):
    await login(client, "owner@example.com")
    other_cp = await client.post("/api/counterparties", json={"name": "Mine"})
    other_id = other_cp.json()["id"]
    await login(client, "viewer@example.com")
    resp = await client.post(
        "/api/contracts",
        json={"title": "Nope", "status": "active", "counterparty_id": other_id},
    )
    assert resp.status_code == 400
