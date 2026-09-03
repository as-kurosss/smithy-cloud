"""CLI entry-point — ``smithy-cloud`` command."""

from __future__ import annotations

import asyncio
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from smithy_cloud_cli.client import OrchestratorClient
from smithy_cloud_cli.packager import read_directory, read_requirements

console = Console()


# ---------------------------------------------------------------------------
# Helper: resolve orchestrator URL from option / env-var / default
# ---------------------------------------------------------------------------


def _client_ctx(ctx: click.Context) -> OrchestratorClient:
    return OrchestratorClient(base_url=ctx.obj["orchestrator"])


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.option(
    "--orchestrator",
    envvar="SMITHY_CLOUD_URL",
    default="http://localhost:8000",
    show_default=True,
    help="URL of the orchestrator service.",
)
@click.pass_context
def cli(ctx: click.Context, orchestrator: str) -> None:
    """Smithy Cloud CLI — deploy and run processes on remote agents."""
    ctx.ensure_object(dict)
    ctx.obj["orchestrator"] = orchestrator


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False))
@click.option("--name", required=True, help="Process name.")
@click.option("--description", default="", help="Human-readable description.")
@click.option(
    "--entry",
    "entry_point",
    default="main.py",
    show_default=True,
    help="Entry-point filename.",
)
@click.pass_context
def deploy(ctx: click.Context, path: str, name: str, description: str, entry_point: str) -> None:
    """Pack a directory and upload it as a new process."""
    console.print(f"[bold]Packing[/bold] {path} …")
    files = read_directory(path)
    if not files:
        console.print("[red]No files found in the given directory.[/red]")
        raise SystemExit(1)

    requirements = read_requirements(path)
    console.print(f"  {len(files)} file(s), {len(requirements)} requirement(s)")

    async def _create() -> dict[str, Any]:
        async with _client_ctx(ctx) as client:
            return await client.create_process(
                name=name,
                description=description,
                entry_point=entry_point,
                files=files,
                requirements=requirements,
            )

    result = asyncio.run(_create())
    pid = result.get("id") or result.get("process_id") or "?"
    console.print(f"[green]✓ Process created[/green]  id={pid}")


# ---------------------------------------------------------------------------
# processes
# ---------------------------------------------------------------------------


@cli.command()
@click.pass_context
def processes(ctx: click.Context) -> None:
    """List all processes."""

    async def _list() -> list[dict[str, Any]]:
        async with _client_ctx(ctx) as client:
            return await client.list_processes()

    items = asyncio.run(_list())

    table = Table(title="Processes")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Entry Point")
    table.add_column("Description")

    for p in items:
        table.add_row(
            str(p.get("id", "")),
            p.get("name", ""),
            p.get("entry_point", ""),
            p.get("description", ""),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# agents
# ---------------------------------------------------------------------------


@cli.command()
@click.pass_context
def agents(ctx: click.Context) -> None:
    """List all registered agents."""

    async def _list() -> list[dict[str, Any]]:
        async with _client_ctx(ctx) as client:
            return await client.list_agents()

    items = asyncio.run(_list())

    table = Table(title="Agents")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Status")

    for a in items:
        table.add_row(
            str(a.get("id", "")),
            a.get("name", ""),
            a.get("status", ""),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("process_id")
@click.argument("agent_id")
@click.pass_context
def run(ctx: click.Context, process_id: str, agent_id: str) -> None:
    """Trigger a process run on an agent."""

    async def _run() -> dict[str, Any]:
        async with _client_ctx(ctx) as client:
            return await client.run(process_id, agent_id)

    result = asyncio.run(_run())
    console.print(f"[green]✓ Run triggered[/green]  {result}")


if __name__ == "__main__":
    cli()
