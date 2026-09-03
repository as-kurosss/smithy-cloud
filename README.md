# smithy-cloud

Cloud orchestrator for the [smithy-py](https://pypi.org/project/smithy-py/) RPA SDK.

## Prerequisites

- Python 3.11+
- Docker (for PostgreSQL)

## Setup

1. **Start PostgreSQL**

   ```bash
   docker-compose up -d
   ```

2. **Install dependencies**

   ```bash
   pip install -e ".[dev]"
   ```

3. **Copy environment file**

   ```bash
   cp .env.example .env
   ```

4. **Run migrations**

   ```bash
   alembic upgrade head
   ```

5. **Start the server**

   ```bash
   uvicorn smithy_cloud.main:app --reload
   ```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

## API Overview

Processes are business processes. They are deployed to agents and run there.

| Method | Endpoint                        | Description              |
| ------ | ------------------------------- | ------------------------ |
| POST   | `/api/processes`                | Create a process         |
| GET    | `/api/processes`                | List processes           |
| GET    | `/api/processes/{id}`           | Get process details      |
| PUT    | `/api/processes/{id}`           | Update a process         |
| DELETE | `/api/processes/{id}`           | Delete a process         |
| POST   | `/api/processes/{id}/deploy`    | Deploy to an agent       |
| POST   | `/api/processes/{id}/run`       | Start a run on an agent  |
| POST   | `/api/processes/{id}/stop`      | Stop the running run     |
| GET    | `/api/processes/{id}/runs`      | List runs of a process   |
| GET    | `/api/processes/{id}/logs`      | Logs of the latest run   |
| POST   | `/api/agents`                   | Register an agent        |
| GET    | `/api/agents`                   | List agents              |
| WS     | `/ws/processes/{process_id}`    | Live process log stream  |
| WS     | `/ws/runs/{run_id}`             | Live run log stream      |

## Local run (VSCode dev loop)

Use `LocalBackend` from `smithy_cloud.executor` to run a process on your
machine without an agent. Remote logging to the orchestrator is opt-in
(`RemoteLogSink`, disabled by default) and never fails the local run.
