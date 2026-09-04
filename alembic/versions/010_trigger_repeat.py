"""Recurring triggers: repeat mode + interval + weekdays + timezone.

Revision ID: 010_trigger_repeat
Revises: 009_triggers
Create Date: 2026-09-04 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010_trigger_repeat"
down_revision: str | None = "009_triggers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "triggers",
        sa.Column("repeat", sa.String(10), nullable=False, server_default="once"),
    )
    op.add_column(
        "triggers", sa.Column("repeat_interval_hours", sa.Integer(), nullable=True)
    )
    op.add_column("triggers", sa.Column("days_of_week", JSONB, nullable=True))
    op.add_column(
        "triggers",
        sa.Column(
            "timezone", sa.String(64), nullable=False, server_default="Europe/Moscow"
        ),
    )


def downgrade() -> None:
    op.drop_column("triggers", "timezone")
    op.drop_column("triggers", "days_of_week")
    op.drop_column("triggers", "repeat_interval_hours")
    op.drop_column("triggers", "repeat")
