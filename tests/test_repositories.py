from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import ChunkCreate, DocumentCreate, DocumentRepository
from app.db.session import create_sqlite_engine


def test_document_repository_creates_and_queries_document(tmp_path) -> None:
    database_path = tmp_path / "repository.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    with TestingSessionLocal() as db:
        repository = DocumentRepository(db)
        document = repository.create_with_chunks(
            DocumentCreate(
                title="堆石混凝土资料",
                source_type="local_file",
                source_path="sample.md",
                file_name="sample.md",
                file_extension=".md",
                content_hash="repository-hash",
                raw_path="data/raw/repository-hash.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="堆石混凝土概念。",
                    char_count=8,
                    heading_path="概念",
                    start_char=0,
                    end_char=8,
                )
            ],
        )

        saved_document = repository.get_by_content_hash("repository-hash")
        documents = repository.list_documents()
        chunk_count = repository.count_chunks(document.id)

    assert saved_document is not None
    assert saved_document.id == document.id
    assert [item.title for item in documents] == ["堆石混凝土资料"]
    assert chunk_count == 1
