from __future__ import annotations


async def test_admin_creates_lists_updates_deletes_user(client, admin, login):
    await login(client, "admin@example.com")

    created = await client.post(
        "/api/users",
        json={"email": "newbie@example.com", "password": "password123"},
    )
    assert created.status_code == 201
    new_id = created.json()["id"]

    listed = await client.get("/api/users")
    assert listed.status_code == 200
    emails = {u["email"] for u in listed.json()}
    assert {"admin@example.com", "newbie@example.com"} <= emails

    # disable the user
    disabled = await client.patch(
        f"/api/users/{new_id}", json={"is_active": False}
    )
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False

    # the disabled user can no longer log in
    resp = await client.post(
        "/api/auth/login",
        data={"username": "newbie@example.com", "password": "password123"},
    )
    assert resp.status_code == 400

    deleted = await client.delete(f"/api/users/{new_id}")
    assert deleted.status_code == 204


async def test_admin_deleting_user_with_data_succeeds(client, admin, login):
    await login(client, "admin@example.com")

    created = await client.post(
        "/api/users", json={"email": "dataguy@example.com", "password": "password123"}
    )
    assert created.status_code == 201
    uid = created.json()["id"]

    await login(client, "dataguy@example.com")
    cp = await client.post("/api/counterparties", json={"name": "Acme GmbH"})
    assert cp.status_code == 201
    contract = await client.post(
        "/api/contracts", json={"title": "Telecom", "counterparty_id": cp.json()["id"]}
    )
    assert contract.status_code == 201
    await client.post("/api/auth/logout")

    await login(client, "admin@example.com")
    resp = await client.delete(f"/api/users/{uid}")
    assert resp.status_code == 204, resp.text

    gone = await client.post(
        "/api/auth/login",
        data={"username": "dataguy@example.com", "password": "password123"},
    )
    assert gone.status_code == 400


async def test_non_admin_cannot_manage_users(client, make_user, login):
    await make_user("regular@example.com")
    await login(client, "regular@example.com")
    resp = await client.get("/api/users")
    assert resp.status_code == 403
    resp = await client.post(
        "/api/users", json={"email": "x@example.com", "password": "password123"}
    )
    assert resp.status_code == 403


async def test_admin_cannot_delete_self(client, admin, login):
    await login(client, "admin@example.com")
    me = await client.get("/api/users/me")
    resp = await client.delete(f"/api/users/{me.json()['id']}")
    assert resp.status_code == 400


async def test_change_own_password(client, make_user, login):
    await make_user("pw@example.com")
    await login(client, "pw@example.com")
    resp = await client.post(
        "/api/users/me/change-password",
        json={"current_password": "password123", "new_password": "newpassword456"},
    )
    assert resp.status_code == 200

    await client.post("/api/auth/logout")
    resp = await client.post(
        "/api/auth/login",
        data={"username": "pw@example.com", "password": "newpassword456"},
    )
    assert resp.status_code == 204


async def test_admin_resets_other_password(client, admin, make_user, login):
    target = await make_user("target@example.com")
    await login(client, "admin@example.com")
    resp = await client.patch(
        f"/api/users/{target.id}", json={"password": "resetpass123"}
    )
    assert resp.status_code == 200
    await client.post("/api/auth/logout")
    resp = await client.post(
        "/api/auth/login",
        data={"username": "target@example.com", "password": "resetpass123"},
    )
    assert resp.status_code == 204
