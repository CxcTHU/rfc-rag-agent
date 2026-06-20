"""Add caption field to chunks.

Revision ID: 20260619_0003
Revises: 20260618_0002
Create Date: 2026-06-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0003"
down_revision: str | None = "20260618_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("caption", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chunks", "caption")
