"""Add structured TableRAG sidecar tables.

Revision ID: 20260709_0009
Revises: 20260629_0008
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - package is installed in runtime images.
    Vector = None


revision: str = "20260709_0009"
down_revision: str | None = "20260629_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def retrieval_unit_vector_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return sa.Text()
    if Vector is None:
        return sa.Text()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    return Vector(2048)


def upgrade() -> None:
    op.create_table(
        "table_extraction_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("tables_seen", sa.Integer(), nullable=False),
        sa.Column("tables_created", sa.Integer(), nullable=False),
        sa.Column("tables_skipped", sa.Integer(), nullable=False),
        sa.Column("error_count", sa.Integer(), nullable=False),
        sa.Column("error_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_table_extraction_runs_id"), "table_extraction_runs", ["id"], unique=False)
    op.create_index(
        op.f("ix_table_extraction_runs_document_id"),
        "table_extraction_runs",
        ["document_id"],
        unique=False,
    )
    op.create_index(op.f("ix_table_extraction_runs_source"), "table_extraction_runs", ["source"], unique=False)
    op.create_index(op.f("ix_table_extraction_runs_status"), "table_extraction_runs", ["status"], unique=False)
    op.create_index(
        op.f("ix_table_extraction_runs_updated_at"),
        "table_extraction_runs",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "document_tables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("source_table_chunk_id", sa.Integer(), nullable=True),
        sa.Column("extraction_run_id", sa.Integer(), nullable=True),
        sa.Column("table_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("bbox_json", sa.Text(), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("header_text", sa.Text(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("col_count", sa.Integer(), nullable=False),
        sa.Column("raw_rows_json", sa.Text(), nullable=False),
        sa.Column("normalized_rows_json", sa.Text(), nullable=False),
        sa.Column("headers_json", sa.Text(), nullable=False),
        sa.Column("units_json", sa.Text(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("structure_hash", sa.String(length=64), nullable=False),
        sa.Column("semantic_metadata_json", sa.Text(), nullable=True),
        sa.Column("processing_metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["table_extraction_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_table_chunk_id"], ["chunks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "page_number",
            "table_index",
            "structure_hash",
            name="uq_document_tables_document_page_index_hash",
        ),
    )
    op.create_index(op.f("ix_document_tables_id"), "document_tables", ["id"], unique=False)
    op.create_index(op.f("ix_document_tables_document_id"), "document_tables", ["document_id"], unique=False)
    op.create_index(
        op.f("ix_document_tables_source_table_chunk_id"),
        "document_tables",
        ["source_table_chunk_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_tables_extraction_run_id"),
        "document_tables",
        ["extraction_run_id"],
        unique=False,
    )
    op.create_index(op.f("ix_document_tables_page_number"), "document_tables", ["page_number"], unique=False)
    op.create_index(op.f("ix_document_tables_structure_hash"), "document_tables", ["structure_hash"], unique=False)
    op.create_index(op.f("ix_document_tables_updated_at"), "document_tables", ["updated_at"], unique=False)

    op.create_table(
        "document_table_columns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("column_index", sa.Integer(), nullable=False),
        sa.Column("header", sa.Text(), nullable=False),
        sa.Column("normalized_header", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["table_id"], ["document_tables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("table_id", "column_index", name="uq_document_table_columns_table_index"),
    )
    op.create_index(op.f("ix_document_table_columns_id"), "document_table_columns", ["id"], unique=False)
    op.create_index(
        op.f("ix_document_table_columns_table_id"),
        "document_table_columns",
        ["table_id"],
        unique=False,
    )
    op.create_index(op.f("ix_document_table_columns_unit"), "document_table_columns", ["unit"], unique=False)

    op.create_table(
        "document_table_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("raw_cells_json", sa.Text(), nullable=False),
        sa.Column("normalized_cells_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["table_id"], ["document_tables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("table_id", "row_index", name="uq_document_table_rows_table_index"),
    )
    op.create_index(op.f("ix_document_table_rows_id"), "document_table_rows", ["id"], unique=False)
    op.create_index(op.f("ix_document_table_rows_table_id"), "document_table_rows", ["table_id"], unique=False)

    op.create_table(
        "document_table_cells",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=True),
        sa.Column("column_id", sa.Integer(), nullable=True),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("col_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("numeric_value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=50), nullable=True),
        sa.Column("is_header", sa.Boolean(), nullable=False),
        sa.Column("bbox_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["column_id"], ["document_table_columns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["row_id"], ["document_table_rows.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["table_id"], ["document_tables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("table_id", "row_index", "col_index", name="uq_document_table_cells_table_position"),
    )
    op.create_index(op.f("ix_document_table_cells_id"), "document_table_cells", ["id"], unique=False)
    op.create_index(op.f("ix_document_table_cells_table_id"), "document_table_cells", ["table_id"], unique=False)
    op.create_index(op.f("ix_document_table_cells_row_id"), "document_table_cells", ["row_id"], unique=False)
    op.create_index(op.f("ix_document_table_cells_column_id"), "document_table_cells", ["column_id"], unique=False)
    op.create_index(
        op.f("ix_document_table_cells_numeric_value"),
        "document_table_cells",
        ["numeric_value"],
        unique=False,
    )
    op.create_index(op.f("ix_document_table_cells_unit"), "document_table_cells", ["unit"], unique=False)
    op.create_index(op.f("ix_document_table_cells_is_header"), "document_table_cells", ["is_header"], unique=False)

    op.create_table(
        "table_retrieval_units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("unit_type", sa.String(length=40), nullable=False),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("source_row_index", sa.Integer(), nullable=True),
        sa.Column("source_col_index", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["table_id"], ["document_tables.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "table_id",
            "unit_type",
            "unit_index",
            "content_hash",
            name="uq_table_retrieval_units_table_type_index_hash",
        ),
    )
    op.create_index(op.f("ix_table_retrieval_units_id"), "table_retrieval_units", ["id"], unique=False)
    op.create_index(op.f("ix_table_retrieval_units_table_id"), "table_retrieval_units", ["table_id"], unique=False)
    op.create_index(op.f("ix_table_retrieval_units_unit_type"), "table_retrieval_units", ["unit_type"], unique=False)
    op.create_index(
        op.f("ix_table_retrieval_units_source_row_index"),
        "table_retrieval_units",
        ["source_row_index"],
        unique=False,
    )
    op.create_index(
        op.f("ix_table_retrieval_units_source_col_index"),
        "table_retrieval_units",
        ["source_col_index"],
        unique=False,
    )
    op.create_index(op.f("ix_table_retrieval_units_content_hash"), "table_retrieval_units", ["content_hash"], unique=False)
    op.create_index(op.f("ix_table_retrieval_units_updated_at"), "table_retrieval_units", ["updated_at"], unique=False)

    op.create_table(
        "table_retrieval_unit_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("retrieval_unit_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("embedding_json", sa.Text(), nullable=False),
        sa.Column("embedding_vector", retrieval_unit_vector_type(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["retrieval_unit_id"], ["table_retrieval_units.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "retrieval_unit_id",
            "provider",
            "model_name",
            name="uq_table_retrieval_unit_embeddings_unit_provider_model",
        ),
    )
    op.create_index(op.f("ix_table_retrieval_unit_embeddings_id"), "table_retrieval_unit_embeddings", ["id"], unique=False)
    op.create_index(
        op.f("ix_table_retrieval_unit_embeddings_retrieval_unit_id"),
        "table_retrieval_unit_embeddings",
        ["retrieval_unit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_table_retrieval_unit_embeddings_content_hash"),
        "table_retrieval_unit_embeddings",
        ["content_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_table_retrieval_unit_embeddings_content_hash"), table_name="table_retrieval_unit_embeddings")
    op.drop_index(
        op.f("ix_table_retrieval_unit_embeddings_retrieval_unit_id"),
        table_name="table_retrieval_unit_embeddings",
    )
    op.drop_index(op.f("ix_table_retrieval_unit_embeddings_id"), table_name="table_retrieval_unit_embeddings")
    op.drop_table("table_retrieval_unit_embeddings")

    op.drop_index(op.f("ix_table_retrieval_units_updated_at"), table_name="table_retrieval_units")
    op.drop_index(op.f("ix_table_retrieval_units_content_hash"), table_name="table_retrieval_units")
    op.drop_index(op.f("ix_table_retrieval_units_source_col_index"), table_name="table_retrieval_units")
    op.drop_index(op.f("ix_table_retrieval_units_source_row_index"), table_name="table_retrieval_units")
    op.drop_index(op.f("ix_table_retrieval_units_unit_type"), table_name="table_retrieval_units")
    op.drop_index(op.f("ix_table_retrieval_units_table_id"), table_name="table_retrieval_units")
    op.drop_index(op.f("ix_table_retrieval_units_id"), table_name="table_retrieval_units")
    op.drop_table("table_retrieval_units")

    op.drop_index(op.f("ix_document_table_cells_is_header"), table_name="document_table_cells")
    op.drop_index(op.f("ix_document_table_cells_unit"), table_name="document_table_cells")
    op.drop_index(op.f("ix_document_table_cells_numeric_value"), table_name="document_table_cells")
    op.drop_index(op.f("ix_document_table_cells_column_id"), table_name="document_table_cells")
    op.drop_index(op.f("ix_document_table_cells_row_id"), table_name="document_table_cells")
    op.drop_index(op.f("ix_document_table_cells_table_id"), table_name="document_table_cells")
    op.drop_index(op.f("ix_document_table_cells_id"), table_name="document_table_cells")
    op.drop_table("document_table_cells")

    op.drop_index(op.f("ix_document_table_rows_table_id"), table_name="document_table_rows")
    op.drop_index(op.f("ix_document_table_rows_id"), table_name="document_table_rows")
    op.drop_table("document_table_rows")

    op.drop_index(op.f("ix_document_table_columns_unit"), table_name="document_table_columns")
    op.drop_index(op.f("ix_document_table_columns_table_id"), table_name="document_table_columns")
    op.drop_index(op.f("ix_document_table_columns_id"), table_name="document_table_columns")
    op.drop_table("document_table_columns")

    op.drop_index(op.f("ix_document_tables_updated_at"), table_name="document_tables")
    op.drop_index(op.f("ix_document_tables_structure_hash"), table_name="document_tables")
    op.drop_index(op.f("ix_document_tables_page_number"), table_name="document_tables")
    op.drop_index(op.f("ix_document_tables_extraction_run_id"), table_name="document_tables")
    op.drop_index(op.f("ix_document_tables_source_table_chunk_id"), table_name="document_tables")
    op.drop_index(op.f("ix_document_tables_document_id"), table_name="document_tables")
    op.drop_index(op.f("ix_document_tables_id"), table_name="document_tables")
    op.drop_table("document_tables")

    op.drop_index(op.f("ix_table_extraction_runs_updated_at"), table_name="table_extraction_runs")
    op.drop_index(op.f("ix_table_extraction_runs_status"), table_name="table_extraction_runs")
    op.drop_index(op.f("ix_table_extraction_runs_source"), table_name="table_extraction_runs")
    op.drop_index(op.f("ix_table_extraction_runs_document_id"), table_name="table_extraction_runs")
    op.drop_index(op.f("ix_table_extraction_runs_id"), table_name="table_extraction_runs")
    op.drop_table("table_extraction_runs")
