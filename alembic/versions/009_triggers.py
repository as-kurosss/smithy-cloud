"""One-shot scheduled triggers: triggers table.

Revision ID: 009_triggers
Revises: 008_queues
Create Date: 2026-09-04 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_triggers"
down_revision: str | None = "008_queues"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "triggers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("agent_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("process_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["process_id"], ["processes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["last_run_id"], ["process_runs.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_triggers_due", "triggers", ["enabled", "run_at"])


def downgrade() -> None:
    op.drop_index("ix_triggers_due", table_name="triggers")
    op.drop_table("triggers")
