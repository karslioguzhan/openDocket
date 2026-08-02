from __future__ import annotations

from datetime import date, timedelta

from tests.test_contracts import make_contract


async def test_dashboard_counts_and_expiring(client, owner, login):
    await login(client, "owner@example.com")
    soon = date.today() + timedelta(days=15)
    late = date.today() + timedelta(days=200)
    await make_contract(client, title="Expiring soon", expiry_date=soon.isoformat())
    await make_contract(client, title="Expiring late", expiry_date=late.isoformat())
    await make_contract(client, title="Draft one", status="draft")

    resp = await client.get("/api/dashboard")
    assert resp.status_code == 200
    body = resp.json()

    titles = {c["title"] for c in body["expiring_soon"]}
    assert "Expiring soon" in titles
    assert "Expiring late" not in titles

    assert body["status_counts"]["active"] == 2
    assert body["status_counts"]["draft"] == 1


async def test_dashboard_category_rollup(client, owner, login):
    await login(client, "owner@example.com")
    cat = (await client.post("/api/meta/categories", json={"name": "Insurance"})).json()
    await make_contract(client, title="Home ins", category_id=cat["id"])
    await make_contract(client, title="Car ins", category_id=cat["id"])

    body = (await client.get("/api/dashboard")).json()
    assert {"name": "Insurance", "count": 2} in body["category_counts"]
