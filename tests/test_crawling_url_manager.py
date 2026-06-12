import csv

from app.services.crawling.url_manager import CrawlUrlManager


def test_url_manager_reads_unique_seeds_and_pending_rows(tmp_path) -> None:
    seed_csv = tmp_path / "seed_urls.csv"
    seed_csv.write_text(
        "url,category,trust_level,notes\n"
        "https://example.org/a,百科词条,medium,note a\n"
        "https://example.org/a,百科词条,medium,duplicate\n"
        "https://example.org/b,高校机构,high,note b\n",
        encoding="utf-8",
    )
    results_csv = tmp_path / "crawl_results.csv"
    manager = CrawlUrlManager(seed_csv, results_csv)

    seeds = manager.read_seeds()
    manager.upsert_result({"url": "https://example.org/a", "status": "imported"})
    pending = manager.pending_seeds()

    assert [seed.url for seed in seeds] == ["https://example.org/a", "https://example.org/b"]
    assert [seed.url for seed in pending] == ["https://example.org/b"]


def test_url_manager_upserts_results_with_stable_header(tmp_path) -> None:
    seed_csv = tmp_path / "seed_urls.csv"
    seed_csv.write_text("url,category,trust_level,notes\n", encoding="utf-8")
    results_csv = tmp_path / "crawl_results.csv"
    manager = CrawlUrlManager(seed_csv, results_csv)

    manager.upsert_result(
        {
            "url": "https://example.org/page",
            "category": "开放论文",
            "trust_level": "high",
            "status": "imported",
            "document_id": 42,
        }
    )
    manager.upsert_result(
        {
            "url": "https://example.org/page",
            "category": "开放论文",
            "trust_level": "high",
            "status": "duplicate",
            "document_id": 42,
        }
    )

    with results_csv.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["status"] == "duplicate"
    assert rows[0]["document_id"] == "42"
