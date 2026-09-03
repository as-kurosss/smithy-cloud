"""Transactional queue tables: queues + queue_items (REFramework-style).

Revision ID: 008_queues
Revises: 007_auth_users
Create Date: 2026-09-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008_queues"
down_revision: str | None = "007_auth_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "queues",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "queue_items",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["process_runs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("queue_id", "idempotency_key", name="uq_queue_items_queue_key"),
    )
    op.create_index(
        "ix_queue_items_queue_status", "queue_items", ["queue_id", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_queue_items_queue_status", table_name="queue_items")
    op.drop_table("queue_items")
    op.drop_table("queues")
