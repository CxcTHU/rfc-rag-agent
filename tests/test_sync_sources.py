import csv

from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.db.repositories import SourceRepository
from app.db.session import create_sqlite_engine
from app.services.source_registry import read_metadata_cards
from scripts.sync_sources import resolve_source_paths, sync_sources


def make_session(tmp_path):
    database_path = tmp_path / "sync_sources.sqlite"
    engine = create_sqlite_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def write_csv(path, fieldnames, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_read_metadata_cards_parses_generated_card(tmp_path) -> None:
    cards_dir = tmp_path / "metadata_corpus"
    cards_dir.mkdir()
    (cards_dir / "paper.md").write_text(
        "\n".join(
            [
                "# A Brief Review of Rock-Filled Concrete Dams",
                "",
                "- source_id: card_1",
                "- authors: Feng Jin",
                "- year: 2023",
                "- venue: Engineering",
                "- category: review;dam_engineering",
                "- discovered_via: OpenAlex;Crossref",
                "- doi: 10.123/review",
                "- url: https://doi.org/10.123/review",
                "- language: en",
                "- citation_count: 37",
                "",
                "## Keywords",
                "",
                "RFC; dam",
                "",
                "## Abstract",
                "",
                "This review studies rock-filled concrete dams.",
            ]
        ),
        encoding="utf-8",
    )

    candidates = read_metadata_cards(cards_dir)

    assert len(candidates) == 1
    assert candidates[0].source_id == "card_1"
    assert candidates[0].source_type == "metadata_record"
    assert candidates[0].access_rights == "metadata"
    assert candidates[0].abstract == "This review studies rock-filled concrete dams."
    assert candidates[0].keywords == "RFC; dam"


def test_sync_sources_imports_csv_manifest_and_metadata_cards_idempotently(tmp_path) -> None:
    candidate_csv = tmp_path / "source_candidates.csv"
    fulltext_manifest = tmp_path / "fulltext_manifest.csv"
    metadata_csv = tmp_path / "metadata.csv"
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir()
    write_csv(
        candidate_csv,
        ["source_id", "title", "doi", "url", "source_type", "access_rights", "status"],
        [
            {
                "source_id": "candidate_1",
                "title": "Rock-Filled Concrete Dam",
                "doi": "10.123/example",
                "url": "https://example.org/metadata",
                "source_type": "open_access_candidate",
                "access_rights": "metadata",
                "status": "candidate",
            }
        ],
    )
    write_csv(
        fulltext_manifest,
        ["source_id", "title", "doi", "pdf_url", "source_type", "access_rights", "local_path", "status"],
        [
            {
                "source_id": "manifest_1",
                "title": "Rock-Filled Concrete Dam",
                "doi": "https://doi.org/10.123/example",
                "pdf_url": "https://example.org/paper.pdf",
                "source_type": "open_access_pdf",
                "access_rights": "open access",
                "local_path": "data/fulltext/open_access/paper.pdf",
                "status": "downloaded",
            }
        ],
    )
    write_csv(
        metadata_csv,
        ["source_id", "title", "doi", "url", "source_type", "access_rights", "abstract"],
        [
            {
                "source_id": "metadata_1",
                "title": "Elastic Modulus of Rock-Filled Concrete",
                "doi": "",
                "url": "https://openalex.org/W1",
                "source_type": "open_access_candidate",
                "access_rights": "metadata",
                "abstract": "Elastic modulus metadata.",
            }
        ],
    )
    (cards_dir / "card.md").write_text(
        "\n".join(
            [
                "# Construction Quality of Rock-Filled Concrete",
                "",
                "- source_id: card_1",
                "- authors: unknown",
                "- year: 2022",
                "- venue: unknown",
                "- category: dam_engineering",
                "- discovered_via: Metadata card",
                "- doi: unknown",
                "- url: https://example.org/card",
                "",
                "## Abstract",
                "",
                "Quality control metadata.",
            ]
        ),
        encoding="utf-8",
    )
    TestingSessionLocal = make_session(tmp_path)

    with TestingSessionLocal() as db:
        first_summary = sync_sources(
            db,
            candidate_csv_paths=[candidate_csv],
            fulltext_manifest_paths=[fulltext_manifest],
            metadata_csv_paths=[metadata_csv],
            metadata_cards_dirs=[cards_dir],
        )
        repository = SourceRepository(db)
        merged_source = repository.get_by_source_id("candidate_1")
        metadata_source = repository.get_by_source_id("metadata_1")
        card_source = repository.get_by_source_id("card_1")
        second_summary = sync_sources(
            db,
            candidate_csv_paths=[candidate_csv],
            fulltext_manifest_paths=[fulltext_manifest],
            metadata_csv_paths=[metadata_csv],
            metadata_cards_dirs=[cards_dir],
        )
        source_count = repository.count_sources()
        merged_pdf_url = merged_source.pdf_url if merged_source else None
        merged_status = merged_source.status if merged_source else None
        metadata_source_exists = metadata_source is not None
        card_source_exists = card_source is not None

    assert first_summary.total == 4
    assert first_summary.created == 3
    assert first_summary.duplicates == 1
    assert merged_pdf_url == "https://example.org/paper.pdf"
    assert merged_status == "collected"
    assert metadata_source_exists is True
    assert card_source_exists is True
    assert second_summary.created == 0
    assert second_summary.updated == 3
    assert second_summary.duplicates == 1
    assert source_count == 3


def test_resolve_source_paths_filters_missing_defaults(tmp_path) -> None:
    existing = tmp_path / "existing.csv"
    existing.write_text("source_id,title\n", encoding="utf-8")

    candidate_paths, fulltext_paths, metadata_paths, card_dirs = resolve_source_paths(
        include_defaults=False,
        candidate_csvs=[existing, tmp_path / "missing.csv"],
        fulltext_manifests=[],
        metadata_csvs=[],
        metadata_cards_dirs=[],
    )

    assert candidate_paths == [existing]
    assert fulltext_paths == []
    assert metadata_paths == []
    assert card_dirs == []
