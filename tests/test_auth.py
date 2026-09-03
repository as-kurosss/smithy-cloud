"""Auth + RBAC foundation: registration, login, refresh rotation, role gating."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from smithy_cloud.config import get_settings

PASSWORD = "password123"


@pytest.fixture()
def enable_auth(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Turn user auth on for one test (settings object is lru-cached)."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-auth-tests-00000000")
    monkeypatch.setenv("REGISTRATION_OPEN", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _bearer(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def _register(client: httpx.AsyncClient, email: str) -> httpx.Response:
    return await client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD}
    )


async def _login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login", data={"username": email, "password": PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _me(client: httpx.AsyncClient, access_token: str) -> httpx.Response:
    return await client.get("/api/auth/me", headers=_bearer(access_token))


async def test_first_user_becomes_admin(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    resp = await _register(client, "first@example.com")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]

    me = await _me(client, body["access_token"])
    assert me.status_code == 200, me.text
    assert me.json()["role"] == "admin"
    assert me.json()["email"] == "first@example.com"


async def test_second_user_is_viewer(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    await _register(client, "admin@example.com")
    resp = await _register(client, "viewer@example.com")
    assert resp.status_code == 201, resp.text

    me = await _me(client, resp.json()["access_token"])
    assert me.json()["role"] == "viewer"


async def test_duplicate_email_rejected(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    assert (await _register(client, "dup@example.com")).status_code == 201
    assert (await _register(client, "dup@example.com")).status_code == 400


async def test_login_wrong_password(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    assert (await _register(client, "u@example.com")).status_code == 201
    resp = await client.post(
        "/api/auth/login", data={"username": "u@example.com", "password": "wrong-pass-1"}
    )
    assert resp.status_code == 401


async def test_closed_registration_blocks_second_user(
    client: httpx.AsyncClient,
    enable_auth: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (await _register(client, "admin@example.com")).status_code == 201
    monkeypatch.setenv("REGISTRATION_OPEN", "false")
    get_settings.cache_clear()
    try:
        resp = await _register(client, "late@example.com")
        assert resp.status_code == 403, resp.text
    finally:
        get_settings.cache_clear()


async def test_refresh_rotation_and_reuse_nukes_family(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    await _register(client, "rot@example.com")
    tokens = await _login(client, "rot@example.com")

    rotated = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert rotated.status_code == 200, rotated.text
    fresh = rotated.json()

    # Reusing the old refresh token signals theft → whole family revoked.
    reuse = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse.status_code == 401
    # Even the freshly rotated token is dead now.
    dead = await client.post(
        "/api/auth/refresh", json={"refresh_token": fresh["refresh_token"]}
    )
    assert dead.status_code == 401


async def test_logout_revokes_refresh_token(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    await _register(client, "bye@example.com")
    tokens = await _login(client, "bye@example.com")

    resp = await client.post(
        "/api/auth/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200, resp.text

    gone = await client.post(
        "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert gone.status_code == 401


async def test_unauthenticated_requests_rejected(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    assert (await client.get("/api/processes")).status_code == 401
    assert (await client.get("/api/agents")).status_code == 401
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_viewer_reads_but_cannot_mutate(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    await _register(client, "admin@example.com")
    viewer = (await _register(client, "viewer@example.com")).json()
    headers = _bearer(viewer["access_token"])

    assert (await client.get("/api/processes", headers=headers)).status_code == 200

    denied = await client.post(
        "/api/processes",
        json={
            "name": "nope",
            "entry_point": "main.py",
            "files": {"main.py": "print('hi')"},
            "requirements": [],
        },
        headers=headers,
    )
    assert denied.status_code == 403, denied.text
    assert (await client.post(
        "/api/agents",
        json={"name": "nope", "url": "http://agent:9000"},
        headers=headers,
    )).status_code == 403


async def test_admin_can_manage_processes_and_agents(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    admin = (await _register(client, "root@example.com")).json()
    viewer = (await _register(client, "v@example.com")).json()
    admin_h = _bearer(admin["access_token"])
    viewer_h = _bearer(viewer["access_token"])

    proc = await client.post(
        "/api/processes",
        json={
            "name": "demo",
            "entry_point": "main.py",
            "files": {"main.py": "print('hi')"},
            "requirements": [],
        },
        headers=admin_h,
    )
    assert proc.status_code == 201, proc.text
    process_id = str(proc.json()["id"])

    agent = await client.post(
        "/api/agents",
        json={"name": "agent-1", "url": "http://agent:9000"},
        headers=admin_h,
    )
    assert agent.status_code == 201, agent.text
    agent_id = str(agent.json()["id"])

    # Viewer may read but not deploy or run.
    assert (
        await client.post(
            f"/api/processes/{process_id}/deploy",
            json={"agent_id": agent_id},
            headers=viewer_h,
        )
    ).status_code == 403
    assert (
        await client.post(
            f"/api/processes/{process_id}/run",
            json={"agent_id": agent_id},
            headers=admin_h,
        )
    ).status_code == 201


async def test_status_reports_auth_enabled(
    client: httpx.AsyncClient, enable_auth: Any
) -> None:
    resp = await client.get("/api/auth/status")
    assert resp.status_code == 200
    assert resp.json() == {"auth_enabled": True}


async def test_auth_disabled_keeps_api_open(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/auth/status")
    assert resp.json() == {"auth_enabled": False}
    assert (await client.get("/api/processes")).status_code == 200
