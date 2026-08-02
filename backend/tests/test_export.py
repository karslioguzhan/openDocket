from __future__ import annotations

import io
import json
import zipfile

from tests.test_contracts import make_contract


async def test_export_zip(client, owner, login):
    await login(client, "owner@example.com")
    contract = await make_contract(client, title="Export me", tags=["a", "b"])
    files = {"file": ("letter.pdf", b"pdfbytes", "application/pdf")}
    await client.post(f"/api/contracts/{contract['id']}/files", files=files)

    resp = await client.get("/api/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["app"] == "openDocket"
    assert len(manifest["contracts"]) == 1
    entry = manifest["contracts"][0]
    assert entry["title"] == "Export me"
    assert entry["tags"] == ["a", "b"]
    assert len(entry["files"]) == 1
    stored = entry["files"][0]["stored_name"]
    assert zf.read(f"files/{stored}") == b"pdfbytes"


async def test_export_excludes_shared_and_trashed(client, owner, viewer, login):
    await login(client, "owner@example.com")
    mine = await make_contract(client, title="Mine")
    await client.post(
        f"/api/contracts/{mine['id']}/shares", json={"email": "viewer@example.com"}
    )
    trashed = await make_contract(client, title="Gone")
    await client.delete(f"/api/contracts/{trashed['id']}")

    resp = await client.get("/api/export")
    manifest = json.loads(zipfile.ZipFile(io.BytesIO(resp.content)).read("manifest.json"))
    titles = {c["title"] for c in manifest["contracts"]}
    assert titles == {"Mine"}
