import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "crawl_and_ingest.py"


def load_cli_module():
    spec = importlib.util.spec_from_file_location("crawl_and_ingest_cli", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parse_args_defaults() -> None:
    cli = load_cli_module()

    args = cli.parse_args([])

    assert args.seed_csv == "data/crawl/seed_urls.csv"
    assert args.output_dir == "data/raw/web_crawl"
    assert args.results_csv == "data/crawl/crawl_results.csv"
    assert args.delay == 2.0
    assert args.timeout == 20.0
    assert args.max_urls is None
    assert args.rebuild_index is False
    assert args.quiet is False
    assert args.discover_links is False
    assert args.max_discovered_per_page == 2


def test_parse_args_accepts_stage28_options() -> None:
    cli = load_cli_module()

    args = cli.parse_args(
        [
            "--seed-csv",
            "custom.csv",
            "--output-dir",
            "out",
            "--results-csv",
            "results.csv",
            "--delay",
            "3",
            "--timeout",
            "7",
            "--max-urls",
            "5",
            "--dry-run",
            "--quiet",
            "--rebuild-index",
            "--discover-links",
            "--max-discovered-per-page",
            "4",
        ]
    )

    assert args.seed_csv == "custom.csv"
    assert args.output_dir == "out"
    assert args.results_csv == "results.csv"
    assert args.delay == 3.0
    assert args.timeout == 7.0
    assert args.max_urls == 5
    assert args.dry_run is True
    assert args.quiet is True
    assert args.rebuild_index is True
    assert args.discover_links is True
    assert args.max_discovered_per_page == 4
