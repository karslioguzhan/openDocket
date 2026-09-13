"""Regression tests for account lifecycle security: session revocation, trash
write-protection and file cleanup on user deletion."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

import app.db as db_module
from app.models import AccessToken, Contract, ContractFile
from app.storage import storage_dir
from tests.test_contracts import make_contract


async def _token_count(user_id: uuid.UUID) -> int:
    async with db_module.AsyncSessionLocal() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(AccessToken)
                .where(AccessToken.user_id == user_id)
            )
            or 0
        )


async def _add_token(user_id: uuid.UUID, token: str) -> None:
    async with db_module.AsyncSessionLocal() as session:
        session.add(AccessToken(user_id=user_id, token=token))
        await session.commit()


async def _stored_names(user_id: uuid.UUID) -> list[str]:
    async with db_module.AsyncSessionLocal() as session:
        result = await session.scalars(
            select(ContractFile.stored_name)
            .join(Contract, Contract.id == ContractFile.contract_id)
            .where(Contract.owner_id == user_id)
        )
        return list(result.all())


async def test_password_change_revokes_other_sessions(client, owner, login):
    await login(client, "owner@example.com")
    me = (await client.get("/api/users/me")).json()
    user_id = uuid.UUID(me["id"])
    await _add_token(user_id, "stolen-session-token")
    assert await _token_count(user_id) == 2

    resp = await client.post(
        "/api/users/me/change-password",
        json={"current_password": "password123", "new_password": "new-password-123"},
    )
    assert resp.status_code == 200, resp.text

    # The caller keeps working; the other session is gone.
    assert await _token_count(user_id) == 1
    assert (await client.get("/api/users/me")).status_code == 200


async def test_admin_password_reset_revokes_all_sessions(client, owner, admin, login):
    await login(client, "owner@example.com")
    me = (await client.get("/api/users/me")).json()
    user_id = uuid.UUID(me["id"])
    await _add_token(user_id, "stolen-session-token")

    await client.post("/api/auth/logout")
    await login(client, "admin@example.com")

    resp = await client.patch(
        f"/api/users/{me['id']}", json={"password": "reset-password-123"}
    )
    assert resp.status_code == 200, resp.text
    assert await _token_count(user_id) == 0


async def test_admin_disable_revokes_sessions(client, owner, admin, login):
    await login(client, "owner@example.com")
    me = (await client.get("/api/users/me")).json()
    user_id = uuid.UUID(me["id"])

    await client.post("/api/auth/logout")
    await login(client, "admin@example.com")

    resp = await client.patch(f"/api/users/{me['id']}", json={"is_active": False})
    assert resp.status_code == 200, resp.text
    assert await _token_count(user_id) == 0


async def test_trashed_contract_cannot_be_edited_but_can_be_restored(
    client, owner, login
):
    await login(client, "owner@example.com")
    contract = await make_contract(client, title="Trash Me")
    cid = contract["id"]

    assert (await client.delete(f"/api/contracts/{cid}")).status_code == 204

    edit = await client.patch(f"/api/contracts/{cid}", json={"title": "Renamed"})
    assert edit.status_code == 404

    share = await client.post(
        f"/api/contracts/{cid}/shares", json={"email": "viewer@example.com"}
    )
    assert share.status_code == 404

    restore = await client.post(f"/api/contracts/{cid}/restore")
    assert restore.status_code == 200, restore.text

    edit = await client.patch(f"/api/contracts/{cid}", json={"title": "Renamed"})
    assert edit.status_code == 200
    assert edit.json()["title"] == "Renamed"


async def test_deleting_user_removes_their_files_from_disk(client, owner, admin, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client, title="With Attachment")
    upload = await client.post(
        f"/api/contracts/{contract['id']}/files",
        files={"file": ("note.txt", b"hello world", "text/plain")},
    )
    assert upload.status_code == 201, upload.text

    me = (await client.get("/api/users/me")).json()
    user_id = uuid.UUID(me["id"])
    stored = await _stored_names(user_id)
    assert stored
    path = storage_dir() / stored[0]
    assert path.exists()

    await client.post("/api/auth/logout")
    await login(client, "admin@example.com")

    resp = await client.delete(f"/api/users/{me['id']}")
    assert resp.status_code == 204, resp.text
    assert not path.exists()
