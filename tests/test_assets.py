"""POST/GET/PATCH/DELETE /api/assets + immutable protection."""

from __future__ import annotations

import httpx


async def _create_asset(
    client: httpx.AsyncClient,
    name: str,
    value: str = "",
    immutable: bool = False,
) -> dict:
    resp = await client.post(
        "/api/assets", json={"name": name, "value": value, "immutable": immutable}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_and_list_assets(client: httpx.AsyncClient) -> None:
    created = await _create_asset(client, "api-url", "http://example:9000")

    assert created["name"] == "api-url"
    assert created["value"] == "http://example:9000"
    assert created["immutable"] is False

    resp = await client.get("/api/assets")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["id"] == created["id"]

    resp = await client.get("/api/assets/api-url")
    assert resp.status_code == 200, resp.text
    assert resp.json()["value"] == "http://example:9000"


async def test_duplicate_name_is_409(client: httpx.AsyncClient) -> None:
    await _create_asset(client, "dup", "one")
    resp = await client.post("/api/assets", json={"name": "dup", "value": "two"})
    assert resp.status_code == 409, resp.text


async def test_unknown_asset_is_404(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/assets/nope")
    assert resp.status_code == 404, resp.text
    resp = await client.patch("/api/assets/nope", json={"value": "x"})
    assert resp.status_code == 404, resp.text
    resp = await client.delete("/api/assets/nope")
    assert resp.status_code == 404, resp.text


async def test_update_value_and_lock(client: httpx.AsyncClient) -> None:
    created = await _create_asset(client, "mutable", "v1")

    resp = await client.patch(f"/api/assets/{created['name']}", json={"value": "v2"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["value"] == "v2"
    assert resp.json()["immutable"] is False

    resp = await client.patch(
        f"/api/assets/{created['name']}", json={"immutable": True}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["immutable"] is True

    # Locked now: any further change is rejected.
    resp = await client.patch(
        f"/api/assets/{created['name']}", json={"value": "v3"}
    )
    assert resp.status_code == 409, resp.text
    resp = await client.delete(f"/api/assets/{created['name']}")
    assert resp.status_code == 409, resp.text


async def test_create_immutable_and_delete_mutable(
    client: httpx.AsyncClient,
) -> None:
    await _create_asset(client, "locked", "secret", immutable=True)

    resp = await client.patch("/api/assets/locked", json={"value": "other"})
    assert resp.status_code == 409, resp.text
    resp = await client.delete("/api/assets/locked")
    assert resp.status_code == 409, resp.text

    await _create_asset(client, "temp", "x")
    resp = await client.delete("/api/assets/temp")
    assert resp.status_code == 204, resp.text
    resp = await client.get("/api/assets/temp")
    assert resp.status_code == 404, resp.text
