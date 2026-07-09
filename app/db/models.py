import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

try:
    from pgvector.sqlalchemy import Vector as PgVector
except ImportError:  # pragma: no cover - dependency is declared for runtime images.
    PgVector = None


class JsonTextVector(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps([float(item) for item in value], ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        loaded = json.loads(value)
        if not isinstance(loaded, list):
            return None
        return [float(item) for item in loaded]


def pgvector_column_type(dimension: int):
    if PgVector is None:
        return JsonTextVector()
    return PgVector(dimension)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="local_file")
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    raw_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="imported")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="Chunk.chunk_index",
    )
    sources: Mapped[list["Source"]] = relationship(
        back_populates="document",
        order_by="Source.id",
    )
    tables: Mapped[list["DocumentTable"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentTable.id",
    )
    table_extraction_runs: Mapped[list["TableExtractionRun"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="TableExtractionRun.id",
    )


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("source_id", name="uq_sources_source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    authors: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    discovered_via: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_doi: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    normalized_url: Mapped[str | None] = mapped_column(String(1000), nullable=True, index=True)
    pdf_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False, default="candidate")
    trust_level: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown", index=True)
    access_rights: Mapped[str] = mapped_column(String(100), nullable=False, default="unknown")
    fulltext_permission: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown", index=True)
    license_or_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="candidate", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    document: Mapped[Document | None] = relationship(back_populates="sources")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_document_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_char: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_type: Mapped[str] = mapped_column(String(30), nullable=False, default="text", index=True)
    source_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_bbox_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    document: Mapped[Document] = relationship(back_populates="chunks")
    parent_chunk: Mapped["Chunk | None"] = relationship(
        remote_side="Chunk.id",
        back_populates="child_chunks",
    )
    child_chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="parent_chunk",
        order_by="Chunk.chunk_index",
    )
    source_document_tables: Mapped[list["DocumentTable"]] = relationship(
        back_populates="source_table_chunk",
        order_by="DocumentTable.id",
    )
    embeddings: Mapped[list["ChunkEmbedding"]] = relationship(
        back_populates="chunk",
        cascade="all, delete-orphan",
        order_by="ChunkEmbedding.id",
    )


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "provider",
            "model_name",
            name="uq_chunk_embeddings_chunk_provider_model",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_vector: Mapped[list[float] | None] = mapped_column(pgvector_column_type(2048), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    chunk: Mapped[Chunk] = relationship(back_populates="embeddings")


class TableExtractionRun(Base):
    __tablename__ = "table_extraction_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="pymupdf_find_tables", index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running", index=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tables_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tables_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tables_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        index=True,
    )

    document: Mapped[Document | None] = relationship(back_populates="table_extraction_runs")
    tables: Mapped[list["DocumentTable"]] = relationship(
        back_populates="extraction_run",
        order_by="DocumentTable.id",
    )


class DocumentTable(Base):
    __tablename__ = "document_tables"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "page_number",
            "table_index",
            "structure_hash",
            name="uq_document_tables_document_page_index_hash",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_table_chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    extraction_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("table_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    table_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    bbox_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    header_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    col_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_rows_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    normalized_rows_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    headers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    units_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    structure_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    semantic_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        index=True,
    )

    document: Mapped[Document] = relationship(back_populates="tables")
    source_table_chunk: Mapped[Chunk | None] = relationship(back_populates="source_document_tables")
    extraction_run: Mapped[TableExtractionRun | None] = relationship(back_populates="tables")
    columns: Mapped[list["DocumentTableColumn"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="DocumentTableColumn.column_index",
    )
    rows: Mapped[list["DocumentTableRow"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="DocumentTableRow.row_index",
    )
    cells: Mapped[list["DocumentTableCell"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="DocumentTableCell.row_index, DocumentTableCell.col_index",
    )
    retrieval_units: Mapped[list["TableRetrievalUnit"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="TableRetrievalUnit.id",
    )


class DocumentTableColumn(Base):
    __tablename__ = "document_table_columns"
    __table_args__ = (
        UniqueConstraint("table_id", "column_index", name="uq_document_table_columns_table_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    table_id: Mapped[int] = mapped_column(
        ForeignKey("document_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    header: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_header: Mapped[str] = mapped_column(Text, nullable=False, default="")
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    table: Mapped[DocumentTable] = relationship(back_populates="columns")
    cells: Mapped[list["DocumentTableCell"]] = relationship(
        back_populates="column",
        order_by="DocumentTableCell.row_index",
    )


class DocumentTableRow(Base):
    __tablename__ = "document_table_rows"
    __table_args__ = (
        UniqueConstraint("table_id", "row_index", name="uq_document_table_rows_table_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    table_id: Mapped[int] = mapped_column(
        ForeignKey("document_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_cells_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    normalized_cells_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    table: Mapped[DocumentTable] = relationship(back_populates="rows")
    cells: Mapped[list["DocumentTableCell"]] = relationship(
        back_populates="row",
        order_by="DocumentTableCell.col_index",
    )


class DocumentTableCell(Base):
    __tablename__ = "document_table_cells"
    __table_args__ = (
        UniqueConstraint("table_id", "row_index", "col_index", name="uq_document_table_cells_table_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    table_id: Mapped[int] = mapped_column(
        ForeignKey("document_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_table_rows.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    column_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_table_columns.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    col_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_header: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    bbox_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    table: Mapped[DocumentTable] = relationship(back_populates="cells")
    row: Mapped[DocumentTableRow | None] = relationship(back_populates="cells")
    column: Mapped[DocumentTableColumn | None] = relationship(back_populates="cells")


class TableRetrievalUnit(Base):
    __tablename__ = "table_retrieval_units"
    __table_args__ = (
        UniqueConstraint(
            "table_id",
            "unit_type",
            "unit_index",
            "content_hash",
            name="uq_table_retrieval_units_table_type_index_hash",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    table_id: Mapped[int] = mapped_column(
        ForeignKey("document_tables.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    unit_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    unit_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_row_index: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_col_index: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        index=True,
    )

    table: Mapped[DocumentTable] = relationship(back_populates="retrieval_units")
    embeddings: Mapped[list["TableRetrievalUnitEmbedding"]] = relationship(
        back_populates="retrieval_unit",
        cascade="all, delete-orphan",
        order_by="TableRetrievalUnitEmbedding.id",
    )


class TableRetrievalUnitEmbedding(Base):
    __tablename__ = "table_retrieval_unit_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "retrieval_unit_id",
            "provider",
            "model_name",
            name="uq_table_retrieval_unit_embeddings_unit_provider_model",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    retrieval_unit_id: Mapped[int] = mapped_column(
        ForeignKey("table_retrieval_units.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_vector: Mapped[list[float] | None] = mapped_column(pgvector_column_type(2048), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    retrieval_unit: Mapped[TableRetrievalUnit] = relationship(back_populates="embeddings")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        order_by="Conversation.updated_at",
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        index=True,
    )

    user: Mapped[User | None] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class AgentRuntimeRun(Base):
    __tablename__ = "agent_runtime_runs"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_agent_runtime_runs_run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", index=True)
    current_node: Mapped[str] = mapped_column(String(80), nullable=False, default="context_assembled")
    last_completed_node: Mapped[str] = mapped_column(String(80), nullable=False, default="context_assembled")
    resume_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_question: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_task: Mapped[str] = mapped_column(Text, nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        index=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class QuestionAnswerLog(Base):
    __tablename__ = "qa_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_chunk_ids: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[str] = mapped_column(Text, nullable=False)
    model_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    retrieval_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    refused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refusal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QAFeedback(Base):
    __tablename__ = "qa_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_answer_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("qa_logs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_id: Mapped[int | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
