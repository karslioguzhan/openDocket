from __future__ import annotations

import httpx

from tests.test_contracts import make_contract


async def _client_as(client: httpx.AsyncClient, email: str) -> httpx.AsyncClient:
    return client


async def test_owner_sees_only_own(client, owner, viewer, login):
    await login(client, "owner@example.com")
    c1 = await make_contract(client, title="Owner's contract")

    # viewer logs in, sees nothing
    await client.post("/api/auth/logout")
    await login(client, "viewer@example.com")
    rows = await client.get("/api/contracts")
    assert rows.json() == []

    # viewer cannot read owner's contract
    resp = await client.get(f"/api/contracts/{c1['id']}")
    assert resp.status_code == 404


async def test_share_grants_view(client, owner, viewer, login):
    await login(client, "owner@example.com")
    c1 = await make_contract(client, title="Shared lease")

    share = await client.post(
        f"/api/contracts/{c1['id']}/shares",
        json={"email": "viewer@example.com"},
    )
    assert share.status_code == 201

    await client.post("/api/auth/logout")
    await login(client, "viewer@example.com")
    rows = await client.get("/api/contracts")
    assert len(rows.json()) == 1
    assert rows.json()[0]["role"] == "viewer"
    assert rows.json()[0]["title"] == "Shared lease"

    got = await client.get(f"/api/contracts/{c1['id']}")
    assert got.status_code == 200
    assert got.json()["shares"] == []  # viewers do not see the share list


async def test_viewer_cannot_edit_or_delete(client, owner, viewer, login):
    await login(client, "owner@example.com")
    c1 = await make_contract(client, title="Read only")
    await client.post(
        f"/api/contracts/{c1['id']}/shares", json={"email": "viewer@example.com"}
    )

    await client.post("/api/auth/logout")
    await login(client, "viewer@example.com")

    patch = await client.patch(f"/api/contracts/{c1['id']}", json={"title": "hacked"})
    assert patch.status_code == 404  # scoped as not found, not 403
    delete = await client.delete(f"/api/contracts/{c1['id']}")
    assert delete.status_code == 404
    dup = await client.post(f"/api/contracts/{c1['id']}/duplicate")
    assert dup.status_code == 404


async def test_remove_share_revokes_access(client, owner, viewer, login):
    await login(client, "owner@example.com")
    c1 = await make_contract(client, title="Temporary share")
    await client.post(
        f"/api/contracts/{c1['id']}/shares", json={"email": "viewer@example.com"}
    )
    shares = await client.get(f"/api/contracts/{c1['id']}")
    share_id = shares.json()["shares"][0]["user_id"]

    removed = await client.delete(f"/api/contracts/{c1['id']}/shares/{share_id}")
    assert removed.status_code == 204

    await client.post("/api/auth/logout")
    await login(client, "viewer@example.com")
    assert (await client.get(f"/api/contracts/{c1['id']}")).status_code == 404


async def test_cannot_share_with_self_or_unknown(client, owner, login):
    await login(client, "owner@example.com")
    c1 = await make_contract(client)

    resp = await client.post(
        f"/api/contracts/{c1['id']}/shares", json={"email": "owner@example.com"}
    )
    assert resp.status_code == 400

    resp = await client.post(
        f"/api/contracts/{c1['id']}/shares", json={"email": "nobody@example.com"}
    )
    assert resp.status_code == 404
