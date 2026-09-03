# smithy-agent

Standalone agent that runs on each Windows server and communicates with the
Smithy Cloud orchestrator. It registers itself, sends heartbeats, polls for
commands, deploys processes in isolated virtual environments, and streams logs
back to the orchestrator.

## Prerequisites

- Python 3.11+
- `pip` (included with Python)

## Install

From the `agent/` directory:

```bash
pip install -e .
```

## Run

```bash
smithy-agent \
    --orchestrator http://localhost:8000 \
    --name my-agent \
    --url http://localhost:8001
```

| Flag | Description |
|------|-------------|
| `--orchestrator` | URL of the orchestrator API |
| `--name` | Human-readable agent name |
| `--url` | Public URL this agent is reachable at |
| `--log-level` | Logging verbosity: DEBUG, INFO (default), WARNING, ERROR, CRITICAL |

## How it works

1. **Register** — on startup the agent POSTs its name and URL to the
   orchestrator and receives an agent ID.
2. **Heartbeat** — every 30 seconds the agent pings the orchestrator to
   signal it is alive.
3. **Poll** — every 5 seconds the agent GETs pending commands.
4. **Execute** — when a `run` command arrives, the agent:
   - Writes source files to `~/.smithy-agent/processes/<id>/`
   - Creates / updates a Python venv and installs dependencies
   - Spawns the process as a subprocess
   - Streams stdout/stderr logs back to the orchestrator
   - Reports the final status (`completed` or `failed`)

## Project layout

```
agent/
├── pyproject.toml
├── README.md
└── src/
    └── smithy_agent/
        ├── __init__.py
        ├── main.py         # Entry point & CLI
        ├── client.py       # Orchestrator HTTP client
        ├── executor.py     # Process deployment & execution
        └── streamer.py     # Log streaming
```
