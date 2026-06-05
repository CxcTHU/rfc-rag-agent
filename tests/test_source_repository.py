from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import (
    ChunkCreate,
    DocumentCreate,
    DocumentRepository,
    SourceCreate,
    SourceRepository,
)
from app.db.session import create_sqlite_engine


def create_testing_session(tmp_path, name: str = "sources.sqlite"):
    database_path = tmp_path / name
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def source_record(**overrides) -> SourceCreate:
    data = {
        "source_id": "rfc_full_001",
        "title": "Research on Rock-Filled Concrete Dam",
        "normalized_title": "research on rock-filled concrete dam",
        "authors": "Feng Jin; Hu Zhou",
        "year": "2017",
        "venue": "LTBD",
        "category": "review;dam_engineering",
        "discovered_via": "fulltext_manifest",
        "doi": None,
        "normalized_doi": None,
        "url": "https://openlib.tugraz.at/download.php?id=5ad6f4c04671e&location=browse",
        "normalized_url": "https://openlib.tugraz.at/download.php?id=5ad6f4c04671e&location=browse",
        "pdf_url": "https://openlib.tugraz.at/download.php?id=5ad6f4c04671e&location=browse",
        "abstract": None,
        "keywords": None,
        "language": "en",
        "citation_count": None,
        "source_type": "open_access_pdf",
        "trust_level": "high",
        "access_rights": "open proceedings PDF",
        "fulltext_permission": "open_access",
        "license_or_terms": "source terms not fully normalized",
        "local_path": "data/fulltext/open_access/rfc_full_2017_jin.pdf",
        "status": "collected",
        "notes": "manifest row",
        "document_id": None,
    }
    data.update(overrides)
    return SourceCreate(**data)


def test_source_repository_creates_and_queries_source(tmp_path) -> None:
    TestingSessionLocal = create_testing_session(tmp_path)

    with TestingSessionLocal() as db:
        repository = SourceRepository(db)
        source = repository.create_source(source_record())

        saved_source = repository.get_by_source_id("rfc_full_001")
        sources = repository.list_sources(status="collected")
        source_count = repository.count_sources(fulltext_permission="open_access")

    assert saved_source is not None
    assert saved_source.id == source.id
    assert saved_source.title == "Research on Rock-Filled Concrete Dam"
    assert saved_source.trust_level == "high"
    assert saved_source.fulltext_permission == "open_access"
    assert [item.source_id for item in sources] == ["rfc_full_001"]
    assert source_count == 1


def test_source_repository_updates_existing_source_by_source_id(tmp_path) -> None:
    TestingSessionLocal = create_testing_session(tmp_path, "sources_update.sqlite")

    with TestingSessionLocal() as db:
        repository = SourceRepository(db)
        first_source = repository.save_source(source_record(status="candidate"))
        updated_source = repository.save_source(
            source_record(
                status="imported",
                document_id=42,
                notes="linked to imported document",
            )
        )
        source_count = repository.count_sources()

    assert updated_source.id == first_source.id
    assert updated_source.status == "imported"
    assert updated_source.document_id == 42
    assert updated_source.notes == "linked to imported document"
    assert source_count == 1


def test_source_repository_finds_duplicates_by_priority(tmp_path) -> None:
    TestingSessionLocal = create_testing_session(tmp_path, "sources_duplicates.sqlite")

    with TestingSessionLocal() as db:
        repository = SourceRepository(db)
        doi_source = repository.create_source(
            source_record(
                source_id="openalex_1",
                doi="https://doi.org/10.123/example",
                normalized_doi="10.123/example",
                url="https://openalex.org/W1",
                normalized_url="https://openalex.org/w1",
            )
        )
        url_source = repository.create_source(
            source_record(
                source_id="manifest_1",
                doi=None,
                normalized_doi=None,
                url="https://example.org/paper",
                normalized_url="https://example.org/paper",
                normalized_title="different title",
            )
        )
        title_source = repository.create_source(
            source_record(
                source_id="metadata_1",
                doi=None,
                normalized_doi=None,
                url=None,
                normalized_url=None,
                normalized_title="a brief review of rock-filled concrete dams",
                title="A Brief Review of Rock-Filled Concrete Dams",
            )
        )

        duplicate_by_doi = repository.find_duplicate(
            normalized_doi="10.123/example",
            normalized_url="https://not-the-same.example/paper",
            normalized_title="not the same",
        )
        duplicate_by_url = repository.find_duplicate(
            normalized_url="https://example.org/paper",
            normalized_title="not the same",
        )
        duplicate_by_title = repository.find_duplicate(
            normalized_title="a brief review of rock-filled concrete dams",
            exclude_source_id="new_candidate",
        )

    assert duplicate_by_doi is not None
    assert duplicate_by_doi.id == doi_source.id
    assert duplicate_by_url is not None
    assert duplicate_by_url.id == url_source.id
    assert duplicate_by_title is not None
    assert duplicate_by_title.id == title_source.id


def test_source_can_link_to_imported_document(tmp_path) -> None:
    TestingSessionLocal = create_testing_session(tmp_path, "sources_document_link.sqlite")

    with TestingSessionLocal() as db:
        document_repository = DocumentRepository(db)
        document = document_repository.create_with_chunks(
            DocumentCreate(
                title="Rock-Filled Concrete Metadata Card",
                source_type="metadata_record",
                source_path="https://openalex.org/W1",
                file_name="metadata.md",
                file_extension=".md",
                content_hash="metadata-card-hash",
                raw_path="data/raw/metadata.md",
            ),
            [
                ChunkCreate(
                    chunk_index=0,
                    content="Rock-filled concrete metadata abstract.",
                    char_count=39,
                    heading_path="Abstract",
                    start_char=0,
                    end_char=39,
                )
            ],
        )
        source_repository = SourceRepository(db)
        source = source_repository.create_source(
            source_record(
                source_id="metadata_1",
                source_type="metadata_record",
                fulltext_permission="metadata_only",
                status="imported",
                document_id=document.id,
            )
        )

        saved_source = source_repository.get_by_id(source.id)
        saved_document_title = saved_source.document.title if saved_source and saved_source.document else None

    assert saved_source is not None
    assert saved_document_title == "Rock-Filled Concrete Metadata Card"
