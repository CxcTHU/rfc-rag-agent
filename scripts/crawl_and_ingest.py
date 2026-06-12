from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.crawling.pipeline import WebCrawlIngestionPipeline  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from app.services.retrieval.vector_index import VectorIndexService  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Crawl public web pages and import extracted Markdown into the RAG corpus.",
    )
    parser.add_argument(
        "--seed-csv",
        default="data/crawl/seed_urls.csv",
        help="CSV file containing url,category,trust_level,notes.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw/web_crawl",
        help="Directory for extracted Markdown files.",
    )
    parser.add_argument(
        "--results-csv",
        default="data/crawl/crawl_results.csv",
        help="CSV file used to track crawl/import status.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between HTTP requests in seconds. Must be at least 2.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=None,
        help="Maximum number of pending URLs to process.",
    )
    parser.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Rebuild deterministic embedding index after crawl/import.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read pending URLs and write dry-run status without fetching pages.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-URL output and print only the final summary.",
    )
    parser.add_argument(
        "--discover-links",
        action="store_true",
        help="Discover same-host public links from fetched HTML and add them to the in-memory queue.",
    )
    parser.add_argument(
        "--max-discovered-per-page",
        type=int,
        default=2,
        help="Maximum same-host links to enqueue from each fetched page when --discover-links is set.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.delay < 2.0:
        raise SystemExit("--delay must be at least 2 seconds")
    if args.max_urls is not None and args.max_urls < 0:
        raise SystemExit("--max-urls must not be negative")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be greater than 0")
    if args.max_discovered_per_page < 0:
        raise SystemExit("--max-discovered-per-page must not be negative")

    init_db()
    with SessionLocal() as db:
        pipeline = WebCrawlIngestionPipeline.from_db(
            db=db,
            seed_csv=args.seed_csv,
            results_csv=args.results_csv,
            output_dir=args.output_dir,
            delay_seconds=args.delay,
            timeout_seconds=args.timeout,
        )
        results = pipeline.run(
            max_urls=args.max_urls,
            dry_run=args.dry_run,
            discover_links=args.discover_links,
            max_discovered_per_page=args.max_discovered_per_page,
        )
        if not args.quiet:
            for result in results:
                detail = f" document_id={result.document_id}" if result.document_id else ""
                print(f"{result.status}: {result.url}{detail}")

        if args.rebuild_index and not args.dry_run:
            provider = create_embedding_provider(provider_name="deterministic")
            index_result = VectorIndexService(db, provider).build_index()
            print(
                "index rebuilt: "
                f"total={index_result.total_chunks} "
                f"indexed={index_result.indexed_chunks} "
                f"updated={index_result.updated_chunks} "
                f"skipped={index_result.skipped_chunks}"
            )

    print(f"processed={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
