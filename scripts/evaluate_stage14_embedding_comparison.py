from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings, get_settings  # noqa: E402
from scripts.evaluate_model_configs import format_pass_rate, is_deterministic  # noqa: E402


DEFAULT_EVALUATION_DIR = Path("data/evaluation")

RESULT_FIELDS = [
    "config_name",
    "suite",
    "status",
    "passed",
    "total",
    "failed",
    "pass_rate",
    "embedding_provider",
    "embedding_model_name",
    "embedding_dimension",
    "chat_provider",
    "chat_model_name",
    "source_file",
    "failed_queries",
    "skipped_reason",
    "notes",
]

SUITE_FILES = {
    "vector": "vector_results.csv",
    "hybrid": "hybrid_results.csv",
    "user_questions": "user_question_results.csv",
    "decompose": "stage13_decompose_results.csv",
    "chat": "chat_results.csv",
    "agent": "agent_results.csv",
    "brain_workflow": "brain_workflow_results.csv",
}


@dataclass(frozen=True)
class EmbeddingComparisonSummary:
    config_name: str
    suite: str
    status: str
    passed: int
    total: int
    embedding_provider: str
    embedding_model_name: str
    embedding_dimension: int | None
    chat_provider: str
    chat_model_name: str
    source_file: str
    failed_queries: tuple[str, ...] = ()
    skipped_reason: str = ""
    notes: str = ""

    def to_row(self) -> dict[str, str]:
        return {
            "config_name": self.config_name,
            "suite": self.suite,
            "status": self.status,
            "passed": str(self.passed),
            "total": str(self.total),
            "failed": str(max(self.total - self.passed, 0)),
            "pass_rate": format_pass_rate(self.passed, self.total),
            "embedding_provider": self.embedding_provider,
            "embedding_model_name": self.embedding_model_name,
            "embedding_dimension": "" if self.embedding_dimension is None else str(self.embedding_dimension),
            "chat_provider": self.chat_provider,
            "chat_model_name": self.chat_model_name,
            "source_file": self.source_file,
            "failed_queries": "|".join(self.failed_queries),
            "skipped_reason": self.skipped_reason,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build stage-14 embedding comparison summary.")
    parser.add_argument("--evaluation-dir", default=str(DEFAULT_EVALUATION_DIR))
    parser.add_argument("--out", default="data/evaluation/stage14_embedding_comparison.csv")
    parser.add_argument(
        "--include-real-config",
        action="store_true",
        help="Add rows for configured real embedding results or skipped rows when config is incomplete.",
    )
    parser.add_argument(
        "--real-results-dir",
        default="",
        help="Directory containing real embedding result CSVs. Defaults to data/evaluation/stage14_real.",
    )
    args = parser.parse_args()

    settings = get_settings()
    results = build_embedding_comparison(
        settings=settings,
        evaluation_dir=Path(args.evaluation_dir),
        include_real_config=args.include_real_config,
        real_results_dir=Path(args.real_results_dir) if args.real_results_dir else None,
    )
    write_results(Path(args.out), results)
    print_summary(results, args.out)


def build_embedding_comparison(
    *,
    settings: Settings,
    evaluation_dir: Path = DEFAULT_EVALUATION_DIR,
    include_real_config: bool = False,
    real_results_dir: Path | None = None,
) -> list[EmbeddingComparisonSummary]:
    results = summarize_embedding_config(
        config_name="deterministic_baseline",
        result_dir=evaluation_dir,
        embedding_provider="deterministic",
        embedding_model_name="hash-token-v1",
        embedding_dimension=64,
        chat_provider="deterministic",
        chat_model_name="rule-based-chat-v1",
        notes="Stable offline baseline. Real API is not required.",
    )

    if not include_real_config:
        return results

    skipped_reason = real_embedding_skipped_reason(settings)
    if skipped_reason:
        results.extend(
            skipped_embedding_results(
                config_name="real_config",
                embedding_provider=settings.embedding_provider,
                embedding_model_name=settings.embedding_model_name,
                embedding_dimension=settings.embedding_dimension or None,
                chat_provider=settings.chat_model_provider or "deterministic",
                chat_model_name=settings.chat_model_name,
                skipped_reason=skipped_reason,
            )
        )
        return results

    results.extend(
        summarize_embedding_config(
            config_name="real_config",
            result_dir=real_results_dir or evaluation_dir / "stage14_real",
            embedding_provider=settings.embedding_provider,
            embedding_model_name=settings.embedding_model_name,
            embedding_dimension=settings.embedding_dimension,
            chat_provider=settings.chat_model_provider or "deterministic",
            chat_model_name=settings.chat_model_name,
            notes="Real embedding comparison. Requires precomputed result CSVs for this provider/model/dimension.",
        )
    )
    return results


def summarize_embedding_config(
    *,
    config_name: str,
    result_dir: Path,
    embedding_provider: str,
    embedding_model_name: str,
    embedding_dimension: int | None,
    chat_provider: str,
    chat_model_name: str,
    notes: str,
) -> list[EmbeddingComparisonSummary]:
    results: list[EmbeddingComparisonSummary] = []
    for suite, filename in SUITE_FILES.items():
        path = result_dir / filename
        if not path.exists():
            results.append(
                EmbeddingComparisonSummary(
                    config_name=config_name,
                    suite=suite,
                    status="missing_results",
                    passed=0,
                    total=0,
                    embedding_provider=embedding_provider,
                    embedding_model_name=embedding_model_name,
                    embedding_dimension=embedding_dimension,
                    chat_provider=chat_provider,
                    chat_model_name=chat_model_name,
                    source_file=str(path),
                    skipped_reason=f"Missing result file: {path}",
                    notes=notes,
                )
            )
            continue

        passed, total, failed_queries = summarize_passed_csv(path)
        results.append(
            EmbeddingComparisonSummary(
                config_name=config_name,
                suite=suite,
                status="completed",
                passed=passed,
                total=total,
                embedding_provider=embedding_provider,
                embedding_model_name=embedding_model_name,
                embedding_dimension=embedding_dimension,
                chat_provider=chat_provider,
                chat_model_name=chat_model_name,
                source_file=str(path),
                failed_queries=failed_queries,
                notes=notes,
            )
        )
    return results


def skipped_embedding_results(
    *,
    config_name: str,
    embedding_provider: str,
    embedding_model_name: str,
    embedding_dimension: int | None,
    chat_provider: str,
    chat_model_name: str,
    skipped_reason: str,
) -> list[EmbeddingComparisonSummary]:
    return [
        EmbeddingComparisonSummary(
            config_name=config_name,
            suite=suite,
            status="skipped",
            passed=0,
            total=0,
            embedding_provider=embedding_provider,
            embedding_model_name=embedding_model_name,
            embedding_dimension=embedding_dimension,
            chat_provider=chat_provider,
            chat_model_name=chat_model_name,
            source_file="",
            skipped_reason=skipped_reason,
            notes="Skipped so local evaluation remains reproducible without real embedding credentials.",
        )
        for suite in SUITE_FILES
    ]


def summarize_passed_csv(path: Path) -> tuple[int, int, tuple[str, ...]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or "passed" not in reader.fieldnames:
            raise ValueError(f"{path} must include a passed column")
        rows = list(reader)

    passed = sum(1 for row in rows if parse_bool(row.get("passed", "")))
    failed_queries = tuple(
        row_identifier(index, row)
        for index, row in enumerate(rows, start=1)
        if not parse_bool(row.get("passed", ""))
    )
    return passed, len(rows), failed_queries


def row_identifier(index: int, row: dict[str, str]) -> str:
    query_id = (row.get("query_id") or row.get("case_id") or row.get("sample_id") or "").strip()
    config_name = (row.get("config_name") or "").strip()
    if query_id and config_name:
        return f"{config_name}:{query_id}"
    if query_id:
        return query_id
    return f"row_{index}"


def real_embedding_skipped_reason(settings: Settings) -> str:
    missing: list[str] = []
    if is_deterministic(settings.embedding_provider):
        missing.append("EMBEDDING_PROVIDER")
    if not settings.embedding_model_name.strip():
        missing.append("EMBEDDING_MODEL_NAME")
    if not settings.embedding_api_key.strip():
        missing.append("EMBEDDING_API_KEY")
    if not settings.embedding_base_url.strip():
        missing.append("EMBEDDING_BASE_URL")
    if settings.embedding_dimension <= 0:
        missing.append("EMBEDDING_DIMENSION")
    if missing:
        return "Incomplete real embedding configuration: " + ", ".join(missing)
    return ""


def parse_bool(value: str) -> bool:
    return value.strip().casefold() in {"yes", "true", "1", "y", "pass", "passed"}


def write_results(path: Path, results: list[EmbeddingComparisonSummary]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[EmbeddingComparisonSummary], output_path: str) -> None:
    print(f"stage 14 embedding comparison: {len(results)} rows")
    for result in results:
        if result.status == "completed":
            print(
                f"{result.config_name}/{result.suite}: "
                f"{result.passed}/{result.total} passed failed={len(result.failed_queries)}"
            )
        else:
            print(f"{result.config_name}/{result.suite}: {result.status} {result.skipped_reason}")
    print(f"wrote results to {output_path}")


if __name__ == "__main__":
    main()
