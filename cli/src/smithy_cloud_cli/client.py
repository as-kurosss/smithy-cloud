"""Async HTTP client for the Smithy orchestrator API."""

from __future__ import annotations

from typing import Any, cast

import httpx


class OrchestratorClient:
    """Thin wrapper around :mod:`httpx` for the orchestrator REST API."""

    def __init__(self, base_url: str = "http://localhost:8000") -> None:
        self._base = base_url.rstrip("/")
        self._http = httpx.AsyncClient(base_url=self._base, timeout=30)

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
        resp = await self._http.post(
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
        resp = await self._http.put(f"/api/processes/{process_id}", json=kwargs)
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def list_processes(self) -> list[dict[str, Any]]:
        """Return all processes via ``GET /api/processes``."""
        resp = await self._http.get("/api/processes")
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    # -- agents ----------------------------------------------------------------

    async def list_agents(self) -> list[dict[str, Any]]:
        """Return all registered agents via ``GET /api/agents``."""
        resp = await self._http.get("/api/agents")
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    # -- deployment / execution ------------------------------------------------

    async def deploy(self, process_id: str, agent_id: str) -> dict[str, Any]:
        """Deploy a process to an agent via ``POST /api/processes/{id}/deploy``."""
        resp = await self._http.post(
            f"/api/processes/{process_id}/deploy",
            json={"agent_id": agent_id},
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def run(self, process_id: str, agent_id: str) -> dict[str, Any]:
        """Run a process on an agent via ``POST /api/processes/{id}/run``."""
        resp = await self._http.post(
            f"/api/processes/{process_id}/run",
            json={"agent_id": agent_id},
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())
