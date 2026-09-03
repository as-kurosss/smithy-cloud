"""Add agents.token_hash for agent authentication (MVP: hash in DB).

Revision ID: 005_agent_token
Revises: 004_drop_flows
Create Date: 2026-09-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005_agent_token"
down_revision: str | None = "004_drop_flows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("token_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "token_hash")
