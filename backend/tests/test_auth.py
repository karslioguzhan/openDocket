from __future__ import annotations


async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_login_logout_me(client, make_user):
    await make_user("alice@example.com")
    resp = await client.post(
        "/api/auth/login",
        data={"username": "alice@example.com", "password": "password123"},
    )
    assert resp.status_code == 204

    me = await client.get("/api/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"

    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 204
    me = await client.get("/api/users/me")
    assert me.status_code == 401


async def test_login_wrong_password(client, make_user):
    await make_user("bob@example.com")
    resp = await client.post(
        "/api/auth/login",
        data={"username": "bob@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 400


async def test_csrf_origin_rejected(client, make_user, login):
    await make_user("carol@example.com")
    await login(client, "carol@example.com")
    resp = await client.post(
        "/api/contracts",
        json={"title": "x"},
        headers={"Origin": "http://evil.example"},
    )
    assert resp.status_code == 403
