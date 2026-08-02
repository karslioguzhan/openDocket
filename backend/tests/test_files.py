from __future__ import annotations

from tests.test_contracts import make_contract


async def test_upload_download_delete(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client)

    files = {"file": ("lease.pdf", b"%PDF-1.4 fake pdf content", "application/pdf")}
    upload = await client.post(f"/api/contracts/{contract['id']}/files", files=files)
    assert upload.status_code == 201
    file_id = upload.json()["id"]
    assert upload.json()["original_name"] == "lease.pdf"

    # appears in contract detail
    got = await client.get(f"/api/contracts/{contract['id']}")
    assert len(got.json()["files"]) == 1

    # download round-trips content and original filename
    dl = await client.get(f"/api/contracts/{contract['id']}/files/{file_id}")
    assert dl.status_code == 200
    assert dl.content == b"%PDF-1.4 fake pdf content"
    assert "lease.pdf" in dl.headers["content-disposition"]

    # delete
    removed = await client.delete(f"/api/contracts/{contract['id']}/files/{file_id}")
    assert removed.status_code == 204
    assert (await client.get(f"/api/contracts/{contract['id']}")).json()["files"] == []


async def test_reject_bad_type_and_oversize(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client)

    bad = {"file": ("evil.exe", b"MZ", "application/x-msdownload")}
    resp = await client.post(f"/api/contracts/{contract['id']}/files", files=bad)
    assert resp.status_code == 415

    big = {"file": ("big.pdf", b"x" * (25 * 1024 * 1024 + 1), "application/pdf")}
    resp = await client.post(f"/api/contracts/{contract['id']}/files", files=big)
    assert resp.status_code == 413


async def test_viewer_can_download_not_upload(client, owner, viewer, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client)
    files = {"file": ("doc.pdf", b"pdf", "application/pdf")}
    upload = await client.post(f"/api/contracts/{contract['id']}/files", files=files)
    file_id = upload.json()["id"]
    await client.post(
        f"/api/contracts/{contract['id']}/shares", json={"email": "viewer@example.com"}
    )

    await client.post("/api/auth/logout")
    await login(client, "viewer@example.com")

    dl = await client.get(f"/api/contracts/{contract['id']}/files/{file_id}")
    assert dl.status_code == 200
    assert dl.content == b"pdf"

    upload = await client.post(
        f"/api/contracts/{contract['id']}/files",
        files={"file": ("more.pdf", b"more", "application/pdf")},
    )
    assert upload.status_code == 404
