"""Widen chunk heading_path for PostgreSQL migration.

Revision ID: 20260621_0006
Revises: 20260621_0005
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260621_0006"
down_revision: str | None = "20260621_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "chunks",
        "heading_path",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "chunks",
        "heading_path",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
