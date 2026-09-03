from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)


class ExecutorBackend(Protocol):
    """Interface for running a process locally (dev) or on an agent (prod)."""

    async def run(
        self,
        *,
        process_id: str,
        entry_point: str,
        workdir: Path,
    ) -> int:
        """Run the process, stream logs, return the exit code."""
        ...


@dataclass
class RemoteLogSink:
    """Best-effort, non-blocking log sink for the orchestrator (opt-in).

    Failures never fail the local run — they are logged as warnings and the
    batch is dropped. Disabled unless both orchestrator_url and run_id set.
    """

    orchestrator_url: str | None = None
    run_id: uuid.UUID | None = None
    batch_size: int = 20
    _buffer: list[dict[str, Any]] = field(default_factory=list, repr=False)

    @property
    def enabled(self) -> bool:
        return self.orchestrator_url is not None and self.run_id is not None

    async def emit(self, client: httpx.AsyncClient, entry: dict[str, Any]) -> None:
        if not self.enabled:
            return
        self._buffer.append(entry)
        if len(self._buffer) >= self.batch_size:
            await self.flush(client)

    async def flush(self, client: httpx.AsyncClient) -> None:
        if not self.enabled or not self._buffer:
            return
        assert self.orchestrator_url is not None
        assert self.run_id is not None
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            await client.post(
                f"{self.orchestrator_url}/api/internal/runs/{self.run_id}/logs",
                json={"logs": batch},
                timeout=5.0,
            )
        except httpx.HTTPError:
            logger.warning("Remote log push failed — dropping %d entries", len(batch))


class LocalBackend:
    """Run a process on this machine (VSCode dev loop).

    Streams subprocess stdout/stderr to the local logger. Remote logging to
    the orchestrator is opt-in via RemoteLogSink (env-gated by the caller).
    """

    def __init__(self, sink: RemoteLogSink | None = None) -> None:
        self._sink = sink or RemoteLogSink()

    async def run(
        self,
        *,
        process_id: str,
        entry_point: str,
        workdir: Path,
    ) -> int:
        entry = workdir / entry_point
        if not entry.is_file():
            raise FileNotFoundError(f"Entry point {entry_point!r} not found in {workdir}")

        logger.info("Running process %s locally: %s %s", process_id, sys.executable, entry)
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(entry),
            cwd=str(workdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        async with httpx.AsyncClient() as client:
            readers = []
            if proc.stdout is not None:
                readers.append(self._stream_reader(client, proc.stdout, "stdout"))
            if proc.stderr is not None:
                readers.append(self._stream_reader(client, proc.stderr, "stderr"))
            if readers:
                await asyncio.gather(*readers)
            await self._sink.flush(client)
            return await proc.wait()

    async def _stream_reader(
        self,
        client: httpx.AsyncClient,
        stream: asyncio.StreamReader,
        source: str,
    ) -> None:
        while True:
            raw = await stream.readline()
            if not raw:
                break
            text = raw.decode(errors="replace").rstrip("\r\n")
            entry: dict[str, Any] = {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": "info",
                "source": source,
                "message": text,
            }
            logger.info("[%s] %s", source, text)
            await self._sink.emit(client, entry)


def remote_sink_from_env(
    *,
    orchestrator_url: str | None,
    run_id: uuid.UUID | None,
) -> RemoteLogSink:
    """Build an opt-in sink; disabled when either argument is None."""
    return RemoteLogSink(orchestrator_url=orchestrator_url, run_id=run_id)
