"""Add processes, agents, deployments, runs, and logs

Revision ID: 002_processes_agents
Revises: 001_initial
Create Date: 2026-09-01 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_processes_agents"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Agents
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="offline"),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capabilities", sa.JSON, nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Processes
    op.create_table(
        "processes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("entry_point", sa.String(255), nullable=False, server_default="main.py"),
        sa.Column("files", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("requirements", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Process Deployments
    op.create_table(
        "process_deployments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "process_id",
            UUID(as_uuid=True),
            sa.ForeignKey("processes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="deploying"),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Process Runs
    op.create_table(
        "process_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "process_id",
            UUID(as_uuid=True),
            sa.ForeignKey("processes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "deployment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("process_deployments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )

    # Process Logs
    op.create_table(
        "process_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("process_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("source", sa.String(20), nullable=False, server_default="stdout"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
    )

    # Indexes
    op.create_index("ix_agents_name", "agents", ["name"], unique=True)
    op.create_index("ix_agents_status", "agents", ["status"])
    op.create_index("ix_process_deployments_process_id", "process_deployments", ["process_id"])
    op.create_index("ix_process_deployments_agent_id", "process_deployments", ["agent_id"])
    op.create_index("ix_process_deployments_status", "process_deployments", ["status"])
    op.create_index("ix_process_runs_process_id", "process_runs", ["process_id"])
    op.create_index("ix_process_runs_agent_id", "process_runs", ["agent_id"])
    op.create_index("ix_process_runs_status", "process_runs", ["status"])
    op.create_index("ix_process_runs_deployment_id", "process_runs", ["deployment_id"])
    op.create_index("ix_process_logs_run_id", "process_logs", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_process_logs_run_id", table_name="process_logs")
    op.drop_index("ix_process_runs_deployment_id", table_name="process_runs")
    op.drop_index("ix_process_runs_status", table_name="process_runs")
    op.drop_index("ix_process_runs_agent_id", table_name="process_runs")
    op.drop_index("ix_process_runs_process_id", table_name="process_runs")
    op.drop_index("ix_process_deployments_status", table_name="process_deployments")
    op.drop_index("ix_process_deployments_agent_id", table_name="process_deployments")
    op.drop_index("ix_process_deployments_process_id", table_name="process_deployments")
    op.drop_index("ix_agents_status", table_name="agents")
    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_table("process_logs")
    op.drop_table("process_runs")
    op.drop_table("process_deployments")
    op.drop_table("processes")
    op.drop_table("agents")
