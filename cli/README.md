# smithy-cloud-cli

CLI for deploying and managing processes on the Smithy Cloud orchestrator.

## Install

```bash
cd cli
pip install -e .
```

## Configuration

Set the orchestrator URL via the `--orchestrator` flag or the `SMITHY_CLOUD_URL` environment variable (default: `http://localhost:8000`).

## Usage

### Deploy a project

Pack a local directory and upload it as a new process:

```bash
smithy-cloud deploy ./my-process --name "Data Pipeline" --description "Nightly ETL" --entry main.py
```

### List processes

```bash
smithy-cloud processes
```

### List agents

```bash
smithy-cloud agents
```

### Run a process on an agent

```bash
smithy-cloud run <process_id> <agent_id>
```

### Custom orchestrator URL

```bash
smithy-cloud --orchestrator http://remote-host:8000 deploy ./my-process --name "Pipeline"
```

Or via environment variable:

```bash
export SMITHY_CLOUD_URL=http://remote-host:8000
smithy-cloud deploy ./my-process --name "Pipeline"
```
