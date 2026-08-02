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
    cat = await client.post("/api/meta/categories", json={"name": "Utilities"})
    assert cat.status_code == 201

    contract = await make_contract(
        client, tags=["home", "monthly"], category_id=cat.json()["id"]
    )
    assert set(contract["tags"]) == {"home", "monthly"}
    assert contract["category"]["name"] == "Utilities"

    # update tags (replace)
    resp = await client.patch(
        f"/api/contracts/{contract['id']}", json={"tags": ["work"]}
    )
    assert resp.json()["tags"] == ["work"]


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
