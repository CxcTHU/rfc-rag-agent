from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings, get_settings  # noqa: E402


DEFAULT_EVALUATION_DIR = Path("data/evaluation")

RESULT_FIELDS = [
    "config_name",
    "suite",
    "status",
    "passed",
    "total",
    "failed",
    "pass_rate",
    "chat_provider",
    "chat_model_name",
    "embedding_provider",
    "embedding_model_name",
    "embedding_dimension",
    "source_file",
    "skipped_reason",
    "notes",
]

SUITE_FILES = {
    "keyword": "keyword_results.csv",
    "vector": "vector_results.csv",
    "hybrid": "hybrid_results.csv",
    "chat": "chat_results.csv",
    "agent": "agent_results.csv",
    "brain_workflow": "brain_workflow_results.csv",
}


@dataclass(frozen=True)
class ModelConfigSummary:
    config_name: str
    suite: str
    status: str
    passed: int
    total: int
    chat_provider: str
    chat_model_name: str
    embedding_provider: str
    embedding_model_name: str
    embedding_dimension: int | None
    source_file: str
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
            "chat_provider": self.chat_provider,
            "chat_model_name": self.chat_model_name,
            "embedding_provider": self.embedding_provider,
            "embedding_model_name": self.embedding_model_name,
            "embedding_dimension": "" if self.embedding_dimension is None else str(self.embedding_dimension),
            "source_file": self.source_file,
            "skipped_reason": self.skipped_reason,
            "notes": self.notes,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize model configuration evaluation results.")
    parser.add_argument("--evaluation-dir", default=str(DEFAULT_EVALUATION_DIR))
    parser.add_argument("--out", default="data/evaluation/model_config_results.csv")
    parser.add_argument(
        "--include-real-config",
        action="store_true",
        help="Add rows for configured real model results or skipped rows when config is incomplete.",
    )
    parser.add_argument(
        "--real-results-dir",
        default="",
        help="Directory containing real model result CSVs. Defaults to data/evaluation/real when included.",
    )
    args = parser.parse_args()

    settings = get_settings()
    evaluation_dir = Path(args.evaluation_dir)
    results = build_model_config_summaries(
        settings=settings,
        evaluation_dir=evaluation_dir,
        include_real_config=args.include_real_config,
        real_results_dir=Path(args.real_results_dir) if args.real_results_dir else None,
    )

    write_results(Path(args.out), results)
    print_summary(results, args.out)


def build_model_config_summaries(
    settings: Settings,
    evaluation_dir: Path = DEFAULT_EVALUATION_DIR,
    include_real_config: bool = False,
    real_results_dir: Path | None = None,
) -> list[ModelConfigSummary]:
    results = summarize_config_results(
        config_name="deterministic_baseline",
        result_dir=evaluation_dir,
        chat_provider="deterministic",
        chat_model_name="rule-based-chat-v1",
        embedding_provider="deterministic",
        embedding_model_name="hash-token-v1",
        embedding_dimension=64,
        notes="Stable offline baseline. Does not require API keys.",
    )

    if not include_real_config:
        return results

    skipped_reason = real_config_skipped_reason(settings)
    if skipped_reason:
        results.extend(
            skipped_config_results(
                config_name="real_config",
                chat_provider=settings.chat_model_provider,
                chat_model_name=settings.chat_model_name,
                embedding_provider=settings.embedding_provider,
                embedding_model_name=settings.embedding_model_name,
                embedding_dimension=settings.embedding_dimension or None,
                skipped_reason=skipped_reason,
            )
        )
        return results

    results.extend(
        summarize_config_results(
            config_name="real_config",
            result_dir=real_results_dir or evaluation_dir / "real",
            chat_provider=settings.chat_model_provider,
            chat_model_name=settings.chat_model_name,
            embedding_provider=settings.embedding_provider,
            embedding_model_name=settings.embedding_model_name,
            embedding_dimension=settings.embedding_dimension,
            notes="Real model configuration. Requires precomputed result CSVs in the real results directory.",
        )
    )
    return results


def summarize_config_results(
    *,
    config_name: str,
    result_dir: Path,
    chat_provider: str,
    chat_model_name: str,
    embedding_provider: str,
    embedding_model_name: str,
    embedding_dimension: int | None,
    notes: str,
) -> list[ModelConfigSummary]:
    results: list[ModelConfigSummary] = []
    for suite, filename in SUITE_FILES.items():
        path = result_dir / filename
        if not path.exists():
            results.append(
                ModelConfigSummary(
                    config_name=config_name,
                    suite=suite,
                    status="missing_results",
                    passed=0,
                    total=0,
                    chat_provider=chat_provider,
                    chat_model_name=chat_model_name,
                    embedding_provider=embedding_provider,
                    embedding_model_name=embedding_model_name,
                    embedding_dimension=embedding_dimension,
                    source_file=str(path),
                    skipped_reason=f"Missing result file: {path}",
                    notes=notes,
                )
            )
            continue

        passed, total = summarize_passed_csv(path)
        results.append(
            ModelConfigSummary(
                config_name=config_name,
                suite=suite,
                status="completed",
                passed=passed,
                total=total,
                chat_provider=chat_provider,
                chat_model_name=chat_model_name,
                embedding_provider=embedding_provider,
                embedding_model_name=embedding_model_name,
                embedding_dimension=embedding_dimension,
                source_file=str(path),
                notes=notes,
            )
        )
    return results


def skipped_config_results(
    *,
    config_name: str,
    chat_provider: str,
    chat_model_name: str,
    embedding_provider: str,
    embedding_model_name: str,
    embedding_dimension: int | None,
    skipped_reason: str,
) -> list[ModelConfigSummary]:
    return [
        ModelConfigSummary(
            config_name=config_name,
            suite=suite,
            status="skipped",
            passed=0,
            total=0,
            chat_provider=chat_provider,
            chat_model_name=chat_model_name,
            embedding_provider=embedding_provider,
            embedding_model_name=embedding_model_name,
            embedding_dimension=embedding_dimension,
            source_file="",
            skipped_reason=skipped_reason,
            notes="Skipped so local evaluation remains reproducible without real API credentials.",
        )
        for suite in SUITE_FILES
    ]


def summarize_passed_csv(path: Path) -> tuple[int, int]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames or "passed" not in reader.fieldnames:
            raise ValueError(f"{path} must include a passed column")
        rows = list(reader)

    passed = sum(1 for row in rows if parse_bool(row.get("passed", "")))
    return passed, len(rows)


def format_pass_rate(passed: int, total: int) -> str:
    if total <= 0:
        return ""
    return f"{passed / total:.3f}"


def real_config_skipped_reason(settings: Settings) -> str:
    missing: list[str] = []
    if is_deterministic(settings.chat_model_provider):
        missing.append("CHAT_MODEL_PROVIDER")
    if not settings.chat_model_name.strip():
        missing.append("CHAT_MODEL_NAME")
    if not settings.chat_model_api_key.strip():
        missing.append("CHAT_MODEL_API_KEY")
    if not settings.chat_model_base_url.strip():
        missing.append("CHAT_MODEL_BASE_URL")
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
        return "Incomplete real model configuration: " + ", ".join(missing)
    return ""


def is_deterministic(provider_name: str | None) -> bool:
    provider = (provider_name or "").strip().casefold()
    return provider in {"", "deterministic", "fake", "local"}


def parse_bool(value: str) -> bool:
    return value.strip().casefold() in {"yes", "true", "1", "y"}


def write_results(path: Path, results: list[ModelConfigSummary]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_row())


def print_summary(results: list[ModelConfigSummary], output_path: str) -> None:
    print(f"model config evaluation: {len(results)} rows")
    for result in results:
        if result.status == "completed":
            print(f"{result.config_name}/{result.suite}: {result.passed}/{result.total} passed")
        else:
            print(f"{result.config_name}/{result.suite}: {result.status} {result.skipped_reason}")
    print(f"wrote results to {output_path}")


if __name__ == "__main__":
    main()
