"""Log streaming — reads subprocess output and pushes it to the orchestrator."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any

from smithy_agent.client import OrchestratorClient

logger = logging.getLogger(__name__)

# Matches structured log lines like: [INFO] Processing item …
_STRUCTURED_RE = re.compile(r"^\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]\s*(.*)$")

# Flush logs in batches (rows or time-bounded)
_BATCH_SIZE = 20


class LogStreamer:
    """Reads stdout/stderr from a subprocess and pushes logs to the orchestrator."""

    def __init__(self, client: OrchestratorClient, run_id: str) -> None:
        self._client = client
        self._run_id = run_id
        self._buffer: list[dict[str, Any]] = []

    async def stream(self, process: asyncio.subprocess.Process) -> None:
        """Read stdout and stderr concurrently, push logs as they arrive.

        Returns once both streams are exhausted and the process exits.
        """
        tasks = []
        if process.stdout is not None:
            tasks.append(asyncio.create_task(self._read_stream(process.stdout, "stdout")))
        if process.stderr is not None:
            tasks.append(asyncio.create_task(self._read_stream(process.stderr, "stderr")))

        # Wait for all readers to finish
        if tasks:
            await asyncio.gather(*tasks)

        # Final flush
        await self._flush()

        # Wait for process to fully exit
        await process.wait()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _read_stream(
        self,
        stream: asyncio.StreamReader,
        source: str,
    ) -> None:
        """Read lines from a stream and enqueue log entries."""
        while True:
            raw_line = await stream.readline()
            if not raw_line:
                break  # stream closed

            text = raw_line.decode(errors="replace").rstrip("\n\r")
            entry = self._parse_line(text, source)
            self._buffer.append(entry)

            if len(self._buffer) >= _BATCH_SIZE:
                await self._flush()

    @staticmethod
    def _parse_line(text: str, source: str) -> dict[str, Any]:
        """Parse a line, extracting level if it matches the structured format."""
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "source": source,
            "message": text,
        }
        match = _STRUCTURED_RE.match(text)
        if match:
            entry["level"] = match.group(1)
            entry["message"] = match.group(2)
        return entry

    async def _flush(self) -> None:
        """Push buffered logs to the orchestrator and clear the buffer."""
        if not self._buffer:
            return
        batch = self._buffer[:]
        self._buffer.clear()
        try:
            await self._client.push_logs(self._run_id, batch)
        except Exception:
            logger.exception("Failed to push logs for run %s", self._run_id)
