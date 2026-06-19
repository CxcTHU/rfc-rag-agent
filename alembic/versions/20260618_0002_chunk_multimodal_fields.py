"""Add multimodal chunk fields.

Revision ID: 20260618_0002
Revises: 20260617_0001
Create Date: 2026-06-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260618_0002"
down_revision: str | None = "20260617_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column("chunk_type", sa.String(length=30), nullable=False, server_default="text"),
    )
    op.add_column(
        "chunks",
        sa.Column("source_image_path", sa.String(length=500), nullable=True),
    )
    op.create_index(op.f("ix_chunks_chunk_type"), "chunks", ["chunk_type"], unique=False)
    op.alter_column("chunks", "chunk_type", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_chunks_chunk_type"), table_name="chunks")
    op.drop_column("chunks", "source_image_path")
    op.drop_column("chunks", "chunk_type")
