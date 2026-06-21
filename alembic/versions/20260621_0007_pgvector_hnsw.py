"""Add pgvector HNSW index for chunk embeddings.

Revision ID: 20260621_0007
Revises: 20260621_0006
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - package is installed in runtime images.
    Vector = None


revision: str = "20260621_0007"
down_revision: str | None = "20260621_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


HNSW_INDEX_NAME = "ix_chunk_embeddings_embedding_vector_hnsw"


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if Vector is None:
        raise RuntimeError("pgvector package is required for PostgreSQL vector migrations")

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "chunk_embeddings",
        sa.Column("embedding_vector", Vector(2048), nullable=True),
    )
    op.execute(
        """
        UPDATE chunk_embeddings
        SET embedding_vector = regexp_replace(embedding_json, '\\s+', '', 'g')::vector
        WHERE embedding_vector IS NULL
          AND embedding_json IS NOT NULL
          AND dimension = 2048
        """
    )
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {HNSW_INDEX_NAME}
        ON chunk_embeddings
        USING hnsw ((embedding_vector::halfvec(2048)) halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 200)
        WHERE embedding_vector IS NOT NULL
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(f"DROP INDEX IF EXISTS {HNSW_INDEX_NAME}")
    op.drop_column("chunk_embeddings", "embedding_vector")
