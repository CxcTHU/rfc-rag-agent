from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.repositories import SourceRepository  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.source_registry import (  # noqa: E402
    SourceRegistryService,
    SourceRegistrySummary,
    read_existing_source_candidates,
)


DEFAULT_CANDIDATE_CSVS = [Path("data/source_candidates.csv")]
DEFAULT_FULLTEXT_MANIFESTS = [Path("data/fulltext_manifest.csv")]
DEFAULT_METADATA_CSVS = [Path("data/metadata/rfc_papers_metadata.csv")]
DEFAULT_METADATA_CARDS_DIRS = [Path("data/imports/metadata_corpus")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync source candidates into the sources registry.")
    parser.add_argument("--candidate-csv", action="append", default=[], help="Candidate CSV path.")
    parser.add_argument("--fulltext-manifest", action="append", default=[], help="Fulltext manifest CSV path.")
    parser.add_argument("--metadata-csv", action="append", default=[], help="Metadata corpus CSV path.")
    parser.add_argument("--metadata-cards-dir", action="append", default=[], help="Metadata card directory.")
    parser.add_argument("--no-defaults", action="store_true", help="Do not include project default source files.")
    args = parser.parse_args()

    init_db()
    candidate_csvs, fulltext_manifests, metadata_csvs, metadata_cards_dirs = resolve_source_paths(
        include_defaults=not args.no_defaults,
        candidate_csvs=[Path(path) for path in args.candidate_csv],
        fulltext_manifests=[Path(path) for path in args.fulltext_manifest],
        metadata_csvs=[Path(path) for path in args.metadata_csv],
        metadata_cards_dirs=[Path(path) for path in args.metadata_cards_dir],
    )
    with SessionLocal() as db:
        summary = sync_sources(
            db=db,
            candidate_csv_paths=candidate_csvs,
            fulltext_manifest_paths=fulltext_manifests,
            metadata_csv_paths=metadata_csvs,
            metadata_cards_dirs=metadata_cards_dirs,
        )
    print(
        "sources_sync\t"
        f"total={summary.total}\tcreated={summary.created}\t"
        f"updated={summary.updated}\tduplicates={summary.duplicates}"
    )


def resolve_source_paths(
    include_defaults: bool,
    candidate_csvs: list[Path] | None = None,
    fulltext_manifests: list[Path] | None = None,
    metadata_csvs: list[Path] | None = None,
    metadata_cards_dirs: list[Path] | None = None,
) -> tuple[list[Path], list[Path], list[Path], list[Path]]:
    candidate_paths = list(candidate_csvs or [])
    fulltext_paths = list(fulltext_manifests or [])
    metadata_paths = list(metadata_csvs or [])
    card_dirs = list(metadata_cards_dirs or [])
    if include_defaults:
        candidate_paths = [*DEFAULT_CANDIDATE_CSVS, *candidate_paths]
        fulltext_paths = [*DEFAULT_FULLTEXT_MANIFESTS, *fulltext_paths]
        metadata_paths = [*DEFAULT_METADATA_CSVS, *metadata_paths]
        card_dirs = [*DEFAULT_METADATA_CARDS_DIRS, *card_dirs]
    return (
        existing_paths(candidate_paths),
        existing_paths(fulltext_paths),
        existing_paths(metadata_paths),
        existing_paths(card_dirs),
    )


def existing_paths(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def sync_sources(
    db,
    candidate_csv_paths: list[Path] | None = None,
    fulltext_manifest_paths: list[Path] | None = None,
    metadata_csv_paths: list[Path] | None = None,
    metadata_cards_dirs: list[Path] | None = None,
) -> SourceRegistrySummary:
    candidates = read_existing_source_candidates(
        candidate_csv_paths=candidate_csv_paths,
        fulltext_manifest_paths=fulltext_manifest_paths,
        metadata_csv_paths=metadata_csv_paths,
        metadata_cards_dirs=metadata_cards_dirs,
    )
    registry = SourceRegistryService(SourceRepository(db))
    return registry.register_candidates(candidates)


if __name__ == "__main__":
    main()
