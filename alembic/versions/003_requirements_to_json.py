"""Change requirements column from text to JSON

Revision ID: 003_requirements_to_json
Revises: 002_processes_agents
Create Date: 2026-09-01 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_requirements_to_json"
down_revision: str | None = "002_processes_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Convert existing text requirements to JSON arrays.
    # Empty string → empty array; newline-separated lines → trimmed list of strings.
    op.execute(
        """
        UPDATE processes
        SET requirements = CASE
            WHEN trim(requirements) = '' THEN '[]'::jsonb
            ELSE (
                SELECT jsonb_agg(trim(s))
                FROM regexp_split_to_table(requirements, E'\n') AS s
                WHERE trim(s) != ''
            )
        END
        """
    )

    # Change column type from text to jsonb
    op.execute(
        "ALTER TABLE processes ALTER COLUMN requirements TYPE jsonb USING requirements::jsonb"
    )


def downgrade() -> None:
    # Convert JSON arrays back to newline-separated text
    op.execute(
        """
        UPDATE processes
        SET requirements = COALESCE(
            array_to_string(requirements::jsonb::text[], E'\n'),
            ''
        )
        """
    )

    op.alter_column(
        "processes",
        "requirements",
        type_=sa.Text,
        nullable=False,
        server_default="",
    )
