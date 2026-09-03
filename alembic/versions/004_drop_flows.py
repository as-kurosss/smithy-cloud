"""Drop flows, executions, and execution_logs (unified on processes).

Revision ID: 004_drop_flows
Revises: 003_requirements_to_json
Create Date: 2026-09-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_drop_flows"
down_revision: str | None = "003_requirements_to_json"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_execution_logs_execution_id", table_name="execution_logs")
    op.drop_index("ix_executions_status", table_name="executions")
    op.drop_index("ix_executions_flow_id", table_name="executions")
    op.drop_table("execution_logs")
    op.drop_table("executions")
    op.drop_table("flows")


def downgrade() -> None:
    # Flow tables are not restored — terminology was unified on processes.
    # Re-create them from 001_initial if a rollback is ever required.
    pass
