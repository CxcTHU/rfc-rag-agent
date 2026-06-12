from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.repositories import SourceRepository  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.crawling.extractor import WebContentExtractor  # noqa: E402
from app.services.crawling.wikipedia_fetcher import WikipediaArticle, WikipediaFetcher  # noqa: E402
from app.services.ingestion.service import IngestionService  # noqa: E402
from app.services.retrieval.embedding import create_embedding_provider  # noqa: E402
from app.services.retrieval.vector_index import VectorIndexService  # noqa: E402
from app.services.source_collection import SourceCandidate, make_source_id, sanitize_filename  # noqa: E402
from app.services.source_registry import SourceRegistryService  # noqa: E402


CSV_FIELDS = ["language", "title", "category", "trust_level", "notes"]
RESULT_FIELDS = [
    "language",
    "title",
    "category",
    "status",
    "url",
    "document_id",
    "source_id",
    "content_hash",
    "error",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Wikipedia REST HTML pages and import extracted Markdown.")
    parser.add_argument("--articles-csv", default="data/crawl/wikipedia_articles.csv")
    parser.add_argument("--output-dir", default="data/raw/wikipedia")
    parser.add_argument("--results-csv", default="data/crawl/wikipedia_results.csv")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--max-articles", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--rebuild-index", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.delay < 2.0:
        raise SystemExit("--delay must be at least 2 seconds")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be greater than 0")
    if args.max_articles is not None and args.max_articles < 0:
        raise SystemExit("--max-articles must not be negative")

    articles = read_articles_csv(Path(args.articles_csv))
    if args.max_articles is not None:
        articles = articles[: args.max_articles]

    if args.dry_run:
        rows = [dry_run_row(article) for article in articles]
        write_results(Path(args.results_csv), rows)
        for row in rows:
            if not args.quiet:
                print(f"dry_run: {row['language']}:{row['title']}")
        print(f"processed={len(rows)}")
        return 0

    init_db()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fetcher = WikipediaFetcher(delay_seconds=args.delay, timeout_seconds=args.timeout)
    extractor = WebContentExtractor()
    result_rows: list[dict[str, str]] = []

    with SessionLocal() as db:
        ingestion_service = IngestionService(db)
        source_registry = SourceRegistryService(SourceRepository(db))

        for article in articles:
            row = ingest_article(
                article=article,
                fetcher=fetcher,
                extractor=extractor,
                output_dir=output_dir,
                ingestion_service=ingestion_service,
                source_registry=source_registry,
            )
            result_rows.append(row)
            if not args.quiet:
                detail = f" document_id={row['document_id']}" if row["document_id"] else ""
                print(f"{row['status']}: {article.language}:{article.title}{detail}")

        if args.rebuild_index:
            provider = create_embedding_provider(provider_name="deterministic")
            index_result = VectorIndexService(db, provider).build_index()
            print(
                "index rebuilt: "
                f"total={index_result.total_chunks} "
                f"indexed={index_result.indexed_chunks} "
                f"updated={index_result.updated_chunks} "
                f"skipped={index_result.skipped_chunks}"
            )

    write_results(Path(args.results_csv), result_rows)
    print(f"processed={len(result_rows)}")
    return 0


def read_articles_csv(path: Path) -> list[WikipediaArticle]:
    if not path.exists():
        raise FileNotFoundError(f"Wikipedia articles CSV was not found: {path}")
    articles: list[WikipediaArticle] = []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = [field for field in CSV_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Wikipedia articles CSV missing fields: {', '.join(missing)}")
        for row in reader:
            title = (row.get("title") or "").strip()
            language = (row.get("language") or "").strip()
            if not title or not language:
                continue
            articles.append(
                WikipediaArticle(
                    language=language,
                    title=title,
                    category=(row.get("category") or "").strip(),
                    trust_level=(row.get("trust_level") or "high").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return articles


def ingest_article(
    *,
    article: WikipediaArticle,
    fetcher: WikipediaFetcher,
    extractor: WebContentExtractor,
    output_dir: Path,
    ingestion_service: IngestionService,
    source_registry: SourceRegistryService,
) -> dict[str, str]:
    result = fetcher.fetch_and_extract(article, extractor)
    base_row = {
        "language": article.language,
        "title": article.title,
        "category": article.category,
        "status": result.status,
        "url": result.url,
        "document_id": "",
        "source_id": "",
        "content_hash": "",
        "error": result.error,
    }
    if result.status != "extracted" or result.extracted is None:
        return base_row

    markdown_path = write_markdown(output_dir, article, result.extracted.markdown)
    try:
        import_result = ingestion_service.import_document(
            markdown_path,
            title=result.extracted.title or article.title,
            source_path=result.url,
            file_name=markdown_path.name,
            source_type="wikipedia",
        )
        source_id = make_source_id("wikipedia", result.extracted.title or article.title, url=result.url)
        source_registry.register_candidate(
            SourceCandidate(
                source_id=source_id,
                title=result.extracted.title or article.title,
                authors=result.extracted.author,
                year=result.extracted.date[:4] if result.extracted.date else "",
                venue="Wikipedia",
                category=article.category,
                discovered_via="stage28_wikipedia_rest_api",
                url=result.url,
                abstract=result.extracted.description,
                keywords="wikipedia; encyclopedia; open web",
                language=article.language,
                source_type="wikipedia",
                access_rights="open_access",
                license_or_terms="Wikipedia REST API page HTML; extracted Markdown only",
                local_path=str(markdown_path),
                status="imported" if import_result.status != "duplicate" else "duplicate",
                notes=article.notes,
            ),
            document_id=import_result.document_id,
        )
    except Exception as exc:
        base_row["status"] = "ingest_failed"
        base_row["error"] = str(exc)
        return base_row

    base_row.update(
        {
            "status": "duplicate" if import_result.status == "duplicate" else "imported",
            "document_id": str(import_result.document_id),
            "source_id": source_id,
            "content_hash": import_result.content_hash,
            "error": "",
        }
    )
    return base_row


def write_markdown(output_dir: Path, article: WikipediaArticle, markdown: str) -> Path:
    digest = hashlib.sha1(f"{article.language}:{article.title}".encode("utf-8")).hexdigest()[:10]
    filename = f"wiki_{article.language}_{digest}_{sanitize_filename(article.title)[:80]}.md"
    path = output_dir / filename
    path.write_text(markdown, encoding="utf-8")
    return path


def dry_run_row(article: WikipediaArticle) -> dict[str, str]:
    return {
        "language": article.language,
        "title": article.title,
        "category": article.category,
        "status": "dry_run",
        "url": "",
        "document_id": "",
        "source_id": "",
        "content_hash": "",
        "error": "",
    }


def write_results(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


if __name__ == "__main__":
    raise SystemExit(main())
