"""Create initial tables

Revision ID: 001_initial
Revises:
Create Date: 2026-08-31 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("config", sa.JSON, nullable=False, server_default="[]"),
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

    op.create_table(
        "executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "flow_id",
            UUID(as_uuid=True),
            sa.ForeignKey("flows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )

    op.create_table(
        "execution_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "execution_id",
            UUID(as_uuid=True),
            sa.ForeignKey("executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("level", sa.String(20), nullable=False, server_default="info"),
        sa.Column("tool_name", sa.String(255), nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
    )

    op.create_index("ix_executions_flow_id", "executions", ["flow_id"])
    op.create_index("ix_executions_status", "executions", ["status"])
    op.create_index("ix_execution_logs_execution_id", "execution_logs", ["execution_id"])


def downgrade() -> None:
    op.drop_index("ix_execution_logs_execution_id", table_name="execution_logs")
    op.drop_index("ix_executions_status", table_name="executions")
    op.drop_index("ix_executions_flow_id", table_name="executions")
    op.drop_table("execution_logs")
    op.drop_table("executions")
    op.drop_table("flows")
