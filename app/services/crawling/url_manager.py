from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


SEED_FIELDS = ["url", "category", "trust_level", "notes"]
RESULT_FIELDS = [
    "url",
    "category",
    "trust_level",
    "status",
    "http_status",
    "title",
    "document_id",
    "source_id",
    "content_hash",
    "fetched_at",
    "error",
]


@dataclass(frozen=True)
class CrawlSeed:
    url: str
    category: str
    trust_level: str
    notes: str = ""


class CrawlUrlManager:
    def __init__(self, seed_csv: str | Path, results_csv: str | Path) -> None:
        self.seed_csv = Path(seed_csv)
        self.results_csv = Path(results_csv)

    def read_seeds(self) -> list[CrawlSeed]:
        with self.seed_csv.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            missing = [field for field in SEED_FIELDS if field not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"Seed CSV missing required columns: {', '.join(missing)}")

            seeds: list[CrawlSeed] = []
            seen: set[str] = set()
            for row in reader:
                url = (row.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                seeds.append(
                    CrawlSeed(
                        url=url,
                        category=(row.get("category") or "").strip(),
                        trust_level=(row.get("trust_level") or "unknown").strip(),
                        notes=(row.get("notes") or "").strip(),
                    )
                )
            return seeds

    def read_results(self) -> dict[str, dict[str, str]]:
        if not self.results_csv.exists():
            return {}
        with self.results_csv.open("r", encoding="utf-8-sig", newline="") as file:
            return {
                row["url"]: {field: row.get(field, "") for field in RESULT_FIELDS}
                for row in csv.DictReader(file)
                if row.get("url")
            }

    def pending_seeds(self, max_urls: int | None = None) -> list[CrawlSeed]:
        completed_statuses = {"imported", "duplicate", "skipped_robots", "source_registered"}
        results = self.read_results()
        pending = [
            seed
            for seed in self.read_seeds()
            if results.get(seed.url, {}).get("status") not in completed_statuses
        ]
        if max_urls is not None:
            if max_urls < 0:
                raise ValueError("max_urls must not be negative")
            pending = pending[:max_urls]
        return pending

    def upsert_result(self, row: dict[str, str | int | None]) -> None:
        self.results_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = self.read_results()
        url = str(row.get("url") or "").strip()
        if not url:
            raise ValueError("result row must include url")
        rows[url] = {field: stringify(row.get(field, "")) for field in RESULT_FIELDS}
        with self.results_csv.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
            writer.writeheader()
            for result_row in sorted(rows.values(), key=lambda item: item["url"]):
                writer.writerow(result_row)


def stringify(value: str | int | None) -> str:
    if value is None:
        return ""
    return str(value)
