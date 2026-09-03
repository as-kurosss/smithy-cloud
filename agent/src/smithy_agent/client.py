"""HTTP client for communicating with the Smithy orchestrator."""

from __future__ import annotations

import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
HEARTBEAT_INTERVAL_SECONDS = 30


class OrchestratorError(Exception):
    """Raised when the orchestrator returns an unexpected response."""


class OrchestratorClient:
    """Async HTTP client wrapping all orchestrator API calls."""

    def __init__(
        self,
        orchestrator_url: str,
        agent_name: str,
        agent_url: str,
    ) -> None:
        self.orchestrator_url = orchestrator_url.rstrip("/")
        self.agent_name = agent_name
        self.agent_url = agent_url
        self.agent_id: str | None = None
        self._secret: str | None = None
        self._http = httpx.AsyncClient(
            base_url=self.orchestrator_url,
            timeout=httpx.Timeout(30.0),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def register(self) -> None:
        """Register this agent with the orchestrator on startup."""
        resp = await self._http.post(
            "/api/agents",
            json={"name": self.agent_name, "url": self.agent_url},
        )
        resp.raise_for_status()
        data = resp.json()
        self.agent_id = data["id"]
        self._secret = data.get("secret")
        logger.info("Registered with orchestrator — agent id=%s", self.agent_id)

    async def close(self) -> None:
        """Shut down the HTTP client."""
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def heartbeat(self) -> None:
        """Send a single heartbeat to the orchestrator."""
        await self._post(f"/api/agents/{self._agent_id}/heartbeat")

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def poll(self) -> list[dict[str, Any]]:
        """Poll the orchestrator for pending commands.

        Returns a list of command dicts.  Each command has at least a ``type``
        key, e.g.::

            {"type": "run", "run_id": "...", "process": {…}}
        """
        resp = await self._get(f"/api/agents/{self._agent_id}/poll")
        if resp.status_code == 204:
            return []
        resp.raise_for_status()
        return cast(list[dict[str, Any]], resp.json())

    # ------------------------------------------------------------------
    # Logs & status
    # ------------------------------------------------------------------

    async def push_logs(self, run_id: str, logs: list[dict[str, Any]]) -> None:
        """Push a batch of log entries to the orchestrator."""
        if not logs:
            return
        await self._post(
            f"/api/agents/{self._agent_id}/logs",
            json={"run_id": run_id, "logs": logs},
        )

    async def report_status(
        self,
        run_id: str,
        status: str,
        *,
        error: str | None = None,
    ) -> None:
        """Report a run status change to the orchestrator."""
        payload: dict[str, Any] = {"run_id": run_id, "status": status}
        if error is not None:
            payload["error"] = error
        await self._post(f"/api/agents/{self._agent_id}/status", json=payload)

    async def ack_deployment(
        self,
        deployment_id: str,
        status: str,
        *,
        error: str | None = None,
    ) -> None:
        """Confirm a deployment result (deployed/failed) to the orchestrator."""
        payload: dict[str, Any] = {"status": status}
        if error is not None:
            payload["error"] = error
        await self._post(
            f"/api/agents/{self._agent_id}/deployments/{deployment_id}/ack",
            json=payload,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @property
    def _agent_id(self) -> str:
        if self.agent_id is None:
            raise OrchestratorError("Agent not registered — call register() first")
        return self.agent_id

    @property
    def _auth_headers(self) -> dict[str, str]:
        if self._secret is None:
            return {}
        return {"Authorization": f"Bearer {self._secret}"}

    async def _get(self, path: str) -> httpx.Response:
        logger.debug("GET %s", path)
        return await self._http.get(path, headers=self._auth_headers)

    async def _post(self, path: str, *, json: Any = None) -> httpx.Response:
        logger.debug("POST %s", path)
        resp = await self._http.post(path, json=json, headers=self._auth_headers)
        if resp.status_code >= 400:
            # Non-raising on purpose: the agent loop must survive transient
            # orchestrator errors; the warning keeps failures visible.
            logger.warning("POST %s -> %s: %s", path, resp.status_code, resp.text[:500])
        return resp
