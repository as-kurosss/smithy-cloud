"""Async HTTP client for the Smithy orchestrator API."""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

import httpx


def _credentials_path() -> Path:
    """Location of the CLI token store (``~/.smithy/credentials.json``)."""
    return Path.home() / ".smithy" / "credentials.json"


def _load_tokens(base_url: str) -> dict[str, str]:
    try:
        data = json.loads(_credentials_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entry = data.get(base_url) if isinstance(data, dict) else None
    return entry if isinstance(entry, dict) else {}


def _save_tokens(base_url: str, tokens: dict[str, str] | None) -> None:
    path = _credentials_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    if tokens is None:
        data.pop(base_url, None)
    else:
        data[base_url] = tokens
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class OrchestratorClient:
    """Thin wrapper around :mod:`httpx` for the orchestrator REST API.

    Bearer tokens saved by ``smithy-cloud login`` are loaded automatically
    and refreshed transparently when the server answers 401.
    """

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base = base_url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self._base, timeout=30)
        tokens = _load_tokens(self._base)
        self._access_token: str | None = tokens.get("access_token")
        self._refresh_token: str | None = tokens.get("refresh_token")

    # -- context-manager support ------------------------------------------------

    async def __aenter__(self) -> OrchestratorClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self._http.aclose()

    @property
    def logged_in(self) -> bool:
        """Whether stored user credentials are available."""
        return self._access_token is not None

    # -- auth -----------------------------------------------------------------

    async def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate via ``POST /api/auth/login`` and persist the token pair."""
        resp = await self._http.post(
            "/api/auth/login", data={"username": email, "password": password}
        )
        resp.raise_for_status()
        body = cast(dict[str, Any], resp.json())
        self._store_tokens(str(body["access_token"]), str(body["refresh_token"]))
        return await self.me()

    async def logout(self) -> None:
        """Revoke the refresh token server-side and drop local credentials."""
        if self._refresh_token:
            with suppress(httpx.HTTPError):
                await self._http.post(
                    "/api/auth/logout", json={"refresh_token": self._refresh_token}
                )
        self._access_token = None
        self._refresh_token = None
        _save_tokens(self._base, None)

    async def me(self) -> dict[str, Any]:
        """Return the current user via ``GET /api/auth/me``."""
        resp = await self._send("GET", "/api/auth/me")
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    # -- transport --------------------------------------------------------------

    def _store_tokens(self, access_token: str, refresh_token: str) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token
        _save_tokens(
            self._base,
            {"access_token": access_token, "refresh_token": refresh_token},
        )

    async def _refresh_access(self) -> bool:
        """Rotate the token pair. Returns True when new tokens were stored."""
        if not self._refresh_token:
            return False
        try:
            resp = await self._http.post(
                "/api/auth/refresh", json={"refresh_token": self._refresh_token}
            )
        except httpx.HTTPError:
            return False
        if resp.status_code != 200:
            self._access_token = None
            self._refresh_token = None
            _save_tokens(self._base, None)
            return False
        body = cast(dict[str, Any], resp.json())
        self._store_tokens(str(body["access_token"]), str(body["refresh_token"]))
        return True

    async def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request with Bearer auth, refreshing once on 401."""
        if self._access_token:
            headers = dict(kwargs.pop("headers", {}) or {})
            headers.setdefault("Authorization", f"Bearer {self._access_token}")
            kwargs["headers"] = headers
        resp = await self._http.request(method, url, **kwargs)
        if (
            resp.status_code == 401
            and self._refresh_token
            and await self._refresh_access()
            and self._access_token
        ):
            headers = dict(kwargs.pop("headers", {}) or {})
            headers["Authorization"] = f"Bearer {self._access_token}"
            kwargs["headers"] = headers
            resp = await self._http.request(method, url, **kwargs)
        return resp

    # -- processes --------------------------------------------------------------

    async def create_process(
        self,
        *,
        name: str,
        description: str = "",
        entry_point: str = "main.py",
        files: dict[str, str],
        requirements: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new process via ``POST /api/processes``."""
        resp = await self._send(
            "POST",
            "/api/processes",
            json={
                "name": name,
                "description": description,
                "entry_point": entry_point,
                "files": files,
                "requirements": requirements or [],
            },
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def update_process(self, process_id: str, **kwargs: object) -> dict[str, Any]:
        """Update an existing process via ``PUT /api/processes/{id}``."""
        resp = await self._send("PUT", f"/api/processes/{process_id}", json=kwargs)
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def list_processes(self) -> list[dict[str, Any]]:
        """Return all processes via ``GET /api/processes``."""
        resp = await self._send("GET", "/api/processes")
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    # -- agents ----------------------------------------------------------------

    async def list_agents(self) -> list[dict[str, Any]]:
        """Return all registered agents via ``GET /api/agents``."""
        resp = await self._send("GET", "/api/agents")
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    # -- deployment / execution ------------------------------------------------

    async def deploy(self, process_id: str, agent_id: str) -> dict[str, Any]:
        """Deploy a process to an agent via ``POST /api/processes/{id}/deploy``."""
        resp = await self._send(
            "POST",
            f"/api/processes/{process_id}/deploy",
            json={"agent_id": agent_id},
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def run(self, process_id: str, agent_id: str) -> dict[str, Any]:
        """Run a process on an agent via ``POST /api/processes/{id}/run``."""
        resp = await self._send(
            "POST",
            f"/api/processes/{process_id}/run",
            json={"agent_id": agent_id},
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())
