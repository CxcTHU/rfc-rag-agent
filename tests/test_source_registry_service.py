from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import SourceRepository
from app.db.session import create_sqlite_engine
from app.services.source_collection import SourceCandidate
from app.services.source_registry import (
    SourceRegistryService,
    candidate_to_source_create,
    derive_fulltext_permission,
    derive_status,
    derive_trust_level,
    normalize_url,
)


def create_source_registry(tmp_path, name: str = "source_registry.sqlite") -> SourceRegistryService:
    database_path = tmp_path / name
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    return SourceRegistryService(SourceRepository(db))


def test_normalize_url_stabilizes_case_query_and_fragment() -> None:
    url = "HTTPS://Example.ORG:443/Paper/?b=2&utm_source=x&a=1#section"

    assert normalize_url(url) == "https://example.org/Paper?a=1&b=2"


def test_candidate_to_source_create_derives_registry_fields() -> None:
    candidate = SourceCandidate(
        source_id="crossref_1",
        title=" Rock-Filled Concrete Dam ",
        authors="Feng Jin",
        year="2017",
        discovered_via="Crossref",
        doi="https://doi.org/10.123/Example",
        url="HTTPS://doi.org/10.123/Example/",
        pdf_url="https://example.org/paper.pdf",
        citation_count="12",
        source_type="open_access_pdf",
        access_rights="open access",
        local_path="data/fulltext/open_access/paper.pdf",
        status="downloaded",
    )

    source_data = candidate_to_source_create(candidate)

    assert source_data.title == "Rock-Filled Concrete Dam"
    assert source_data.normalized_doi == "10.123/example"
    assert source_data.normalized_url == "https://doi.org/10.123/Example"
    assert source_data.normalized_title == "rock-filled concrete dam"
    assert source_data.trust_level == "high"
    assert source_data.fulltext_permission == "open_access"
    assert source_data.status == "collected"
    assert source_data.citation_count == 12


def test_registry_dedupes_by_doi_and_merges_richer_fields(tmp_path) -> None:
    registry = create_source_registry(tmp_path)

    first = SourceCandidate(
        source_id="openalex_1",
        title="Rock-Filled Concrete Dam",
        discovered_via="OpenAlex",
        doi="10.123/example",
        source_type="open_access_candidate",
        access_rights="metadata",
        status="candidate",
    )
    duplicate = SourceCandidate(
        source_id="crossref_1",
        title="Rock-Filled Concrete Dam",
        discovered_via="Crossref",
        doi="https://doi.org/10.123/example",
        pdf_url="https://example.org/paper.pdf",
        abstract="This paper studies rock-filled concrete dams.",
        citation_count="8",
        source_type="open_access_pdf",
        access_rights="open access",
        local_path="data/fulltext/open_access/paper.pdf",
        status="downloaded",
    )

    created = registry.register_candidate(first)
    merged = registry.register_candidate(duplicate)

    assert created.created is True
    assert merged.created is False
    assert merged.duplicate_of_source_id == "openalex_1"
    assert merged.source.source_id == "openalex_1"
    assert merged.source.pdf_url == "https://example.org/paper.pdf"
    assert merged.source.abstract == "This paper studies rock-filled concrete dams."
    assert merged.source.citation_count == 8
    assert merged.source.status == "collected"
    assert "OpenAlex;Crossref" == merged.source.discovered_via


def test_registry_dedupes_by_url_then_title(tmp_path) -> None:
    registry = create_source_registry(tmp_path, "source_registry_url_title.sqlite")

    by_url = registry.register_candidates(
        [
            SourceCandidate(
                source_id="url_1",
                title="Filling Capacity Evaluation",
                url="https://example.org/paper/",
            ),
            SourceCandidate(
                source_id="url_2",
                title="Filling Capacity Evaluation - duplicate",
                url="https://example.org/paper#abstract",
            ),
        ]
    )
    by_title = registry.register_candidates(
        [
            SourceCandidate(source_id="title_1", title="Elastic Modulus of Rock-Filled Concrete"),
            SourceCandidate(source_id="title_2", title=" elastic   modulus of rock-filled concrete "),
        ]
    )

    assert by_url.created == 1
    assert by_url.duplicates == 1
    assert by_title.created == 1
    assert by_title.duplicates == 1


def test_permission_trust_and_status_rules_cover_main_source_types() -> None:
    institutional = SourceCandidate(
        source_id="cnki_1",
        title="堆石混凝土及堆石混凝土大坝",
        source_type="institutional_access_pdf",
        access_rights="CNKI institutional access",
        local_path="data/fulltext/cnki_pending/paper.pdf",
    )
    metadata = SourceCandidate(
        source_id="metadata_1",
        title="Metadata-only RFC paper",
        source_type="metadata_record",
        access_rights="metadata",
        abstract="Public abstract.",
    )

    assert derive_fulltext_permission(institutional) == "institutional_access"
    assert derive_trust_level(institutional) == "high"
    assert derive_status(institutional) == "collected"
    assert derive_fulltext_permission(metadata) == "metadata_only"
    assert derive_trust_level(metadata) == "medium"
    assert derive_status(metadata) == "candidate"
