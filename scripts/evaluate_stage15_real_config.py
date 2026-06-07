from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings, get_settings  # noqa: E402
from scripts.evaluate_model_configs import is_deterministic  # noqa: E402
from scripts.evaluate_stage14_embedding_comparison import (  # noqa: E402
    build_embedding_comparison,
    write_results as write_embedding_comparison,
)


DEFAULT_OUTPUT_DIR = Path("data/evaluation/stage14_real")
DEFAULT_COMPARISON_OUT = Path("data/evaluation/stage14_embedding_comparison.csv")

STATUS_FIELDS = [
    "suite",
    "status",
    "output_file",
    "embedding_provider",
    "embedding_model_name",
    "embedding_dimension",
    "chat_provider",
    "chat_model_name",
    "skipped_reason",
    "error_summary",
    "notes",
]


@dataclass(frozen=True)
class SuiteSpec:
    name: str
    output_filename: str
    requires_embedding: bool
    requires_chat: bool


@dataclass(frozen=True)
class RealConfigStatus:
    suite: str
    status: str
    output_file: str
    embedding_provider: str
    embedding_model_name: str
    embedding_dimension: int | None
    chat_provider: str
    chat_model_name: str
    skipped_reason: str = ""
    error_summary: str = ""
    notes: str = ""

    def to_row(self) -> dict[str, str]:
        return {
            "suite": self.suite,
            "status": self.status,
            "output_file": self.output_file,
            "embedding_provider": self.embedding_provider,
            "embedding_model_name": self.embedding_model_name,
            "embedding_dimension": "" if self.embedding_dimension is None else str(self.embedding_dimension),
            "chat_provider": self.chat_provider,
            "chat_model_name": self.chat_model_name,
            "skipped_reason": self.skipped_reason,
            "error_summary": self.error_summary,
            "notes": self.notes,
        }


SUITES = [
    SuiteSpec("vector", "vector_results.csv", requires_embedding=True, requires_chat=False),
    SuiteSpec("hybrid", "hybrid_results.csv", requires_embedding=True, requires_chat=False),
    SuiteSpec("user_questions", "user_question_results.csv", requires_embedding=True, requires_chat=True),
    SuiteSpec("decompose", "stage13_decompose_results.csv", requires_embedding=True, requires_chat=True),
    SuiteSpec("chat", "chat_results.csv", requires_embedding=True, requires_chat=True),
    SuiteSpec("agent", "agent_results.csv", requires_embedding=True, requires_chat=True),
    SuiteSpec("brain_workflow", "brain_workflow_results.csv", requires_embedding=True, requires_chat=True),
]

Runner = Callable[[list[str], int], subprocess.CompletedProcess[str]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate stage-15 real config rerun readiness and outputs.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--status-out", default="")
    parser.add_argument("--comparison-out", default=str(DEFAULT_COMPARISON_OUT))
    parser.add_argument("--run-real", action="store_true", help="Actually call configured real providers.")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--skip-comparison-update", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    output_dir = Path(args.out_dir)
    status_path = Path(args.status_out) if args.status_out else output_dir / "real_config_status.csv"
    statuses = evaluate_real_config(
        settings=settings,
        output_dir=output_dir,
        run_real=args.run_real,
        timeout_seconds=args.timeout_seconds,
        batch_size=args.batch_size,
        status_path=status_path,
    )
    write_status(status_path, statuses)

    comparison_error = ""
    if not args.skip_comparison_update:
        comparison_error = update_embedding_comparison(
            settings=settings,
            output_dir=output_dir,
            comparison_out=Path(args.comparison_out),
            statuses=statuses,
        )

    print_summary(statuses, status_path, comparison_error=comparison_error)


def evaluate_real_config(
    *,
    settings: Settings,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    run_real: bool = False,
    timeout_seconds: int = 900,
    batch_size: int = 32,
    runner: Runner | None = None,
    python_executable: str | None = None,
    status_path: Path | None = None,
) -> list[RealConfigStatus]:
    output_dir.mkdir(parents=True, exist_ok=True)
    runner = runner or run_subprocess
    python_executable = python_executable or sys.executable
    statuses: list[RealConfigStatus] = []
    for suite in SUITES:
        output_path = output_dir / suite.output_filename
        status = evaluate_suite(
            suite=suite,
            settings=settings,
            output_path=output_path,
            output_dir=output_dir,
            run_real=run_real,
            timeout_seconds=timeout_seconds,
            batch_size=batch_size,
            runner=runner,
            python_executable=python_executable,
        )
        statuses.append(status)
        if status_path is not None:
            write_status(status_path, statuses)
    return statuses


def evaluate_suite(
    *,
    suite: SuiteSpec,
    settings: Settings,
    output_path: Path,
    output_dir: Path,
    run_real: bool,
    timeout_seconds: int,
    batch_size: int,
    runner: Runner,
    python_executable: str,
) -> RealConfigStatus:
    base_kwargs = status_identity_kwargs(suite, settings, output_path)
    if output_path.exists():
        return RealConfigStatus(
            **base_kwargs,
            status="completed",
            notes="Existing real config result file found; no provider call was made.",
        )

    skipped_reason = skipped_reason_for_suite(suite, settings, run_real)
    if skipped_reason:
        return RealConfigStatus(
            **base_kwargs,
            status="skipped",
            skipped_reason=skipped_reason,
            notes="Skipped with explicit status so real_config is not mistaken for deterministic baseline.",
        )

    command = command_for_suite(
        suite=suite,
        settings=settings,
        output_path=output_path,
        output_dir=output_dir,
        python_executable=python_executable,
        batch_size=batch_size,
    )
    try:
        completed = runner(command, timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - external provider failures need a compact status row
        return RealConfigStatus(
            **base_kwargs,
            status="error",
            error_summary=redact_sensitive_text(str(exc), settings),
            notes="Real config command failed before returning a process result.",
        )

    if completed.returncode != 0:
        return RealConfigStatus(
            **base_kwargs,
            status="error",
            error_summary=redact_sensitive_text((completed.stderr or completed.stdout or "").strip(), settings),
            notes=f"Command failed with exit code {completed.returncode}.",
        )
    if not output_path.exists():
        return RealConfigStatus(
            **base_kwargs,
            status="error",
            error_summary=f"Command succeeded but output file was not created: {output_path}",
            notes="No fake result file was generated.",
        )
    return RealConfigStatus(
        **base_kwargs,
        status="completed",
        notes="Real config command completed and wrote a result file.",
    )


def status_identity_kwargs(suite: SuiteSpec, settings: Settings, output_path: Path) -> dict[str, object]:
    return {
        "suite": suite.name,
        "output_file": str(output_path),
        "embedding_provider": settings.embedding_provider,
        "embedding_model_name": settings.embedding_model_name,
        "embedding_dimension": settings.embedding_dimension or None,
        "chat_provider": settings.chat_model_provider,
        "chat_model_name": settings.chat_model_name,
    }


def skipped_reason_for_suite(suite: SuiteSpec, settings: Settings, run_real: bool) -> str:
    missing: list[str] = []
    if suite.requires_embedding:
        missing.extend(missing_embedding_settings(settings))
    if suite.requires_chat:
        missing.extend(missing_chat_settings(settings))
    if missing:
        return "Incomplete real configuration: " + ", ".join(missing)
    if not run_real:
        return "Real configuration appears complete, but --run-real was not passed."
    return ""


def missing_embedding_settings(settings: Settings) -> list[str]:
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
    return missing


def missing_chat_settings(settings: Settings) -> list[str]:
    missing: list[str] = []
    if is_deterministic(settings.chat_model_provider):
        missing.append("CHAT_MODEL_PROVIDER")
    if not settings.chat_model_name.strip():
        missing.append("CHAT_MODEL_NAME")
    if not settings.chat_model_api_key.strip():
        missing.append("CHAT_MODEL_API_KEY")
    if not settings.chat_model_base_url.strip():
        missing.append("CHAT_MODEL_BASE_URL")
    return missing


def command_for_suite(
    *,
    suite: SuiteSpec,
    settings: Settings,
    output_path: Path,
    output_dir: Path,
    python_executable: str,
    batch_size: int,
) -> list[str]:
    embedding_provider = settings.embedding_provider
    chat_provider = settings.chat_model_provider
    if suite.name == "vector":
        return [
            python_executable,
            "scripts/evaluate_vector_search.py",
            "--provider",
            embedding_provider,
            "--batch-size",
            str(batch_size),
            "--out",
            str(output_path),
        ]
    if suite.name == "hybrid":
        return [
            python_executable,
            "scripts/evaluate_hybrid_search.py",
            "--provider",
            embedding_provider,
            "--vector-results",
            str(output_dir / "vector_results.csv"),
            "--out",
            str(output_path),
        ]
    if suite.name == "user_questions":
        return [
            python_executable,
            "scripts/evaluate_user_questions.py",
            "--embedding-provider",
            embedding_provider,
            "--chat-provider",
            chat_provider,
            "--out",
            str(output_path),
        ]
    if suite.name == "decompose":
        return [
            python_executable,
            "scripts/evaluate_decompose.py",
            "--embedding-provider",
            embedding_provider,
            "--chat-provider",
            chat_provider,
            "--include-all",
            "--out",
            str(output_path),
        ]
    if suite.name == "chat":
        return [
            python_executable,
            "scripts/evaluate_chat.py",
            "--embedding-provider",
            embedding_provider,
            "--chat-provider",
            chat_provider,
            "--out",
            str(output_path),
        ]
    if suite.name == "agent":
        return [
            python_executable,
            "scripts/evaluate_agent.py",
            "--embedding-provider",
            embedding_provider,
            "--chat-provider",
            chat_provider,
            "--out",
            str(output_path),
        ]
    if suite.name == "brain_workflow":
        return [
            python_executable,
            "scripts/evaluate_brain_workflow.py",
            "--embedding-provider",
            embedding_provider,
            "--chat-provider",
            chat_provider,
            "--out",
            str(output_path),
        ]
    raise ValueError(f"Unsupported suite: {suite.name}")


def run_subprocess(command: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )


def update_embedding_comparison(
    *,
    settings: Settings,
    output_dir: Path,
    comparison_out: Path,
    statuses: list[RealConfigStatus] | None = None,
) -> str:
    try:
        comparison = build_embedding_comparison(
            settings=settings,
            include_real_config=True,
            real_results_dir=output_dir,
        )
        if statuses:
            comparison = merge_statuses_into_comparison(comparison, statuses)
        write_embedding_comparison(comparison_out, comparison)
    except OSError as exc:
        return f"Embedding comparison update skipped: {exc}"
    return ""


def merge_statuses_into_comparison(comparison, statuses: list[RealConfigStatus]):
    status_by_suite = {status.suite: status for status in statuses}
    merged = []
    for row in comparison:
        status = status_by_suite.get(row.suite) if row.config_name == "real_config" else None
        if status and status.status != row.status:
            reason = status.error_summary if status.status == "error" else status.skipped_reason
            merged.append(
                replace(
                    row,
                    status=status.status,
                    skipped_reason=reason,
                    notes=status.notes,
                )
            )
        else:
            merged.append(row)
    return merged


def read_status(path: Path) -> list[RealConfigStatus]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [
            RealConfigStatus(
                suite=row["suite"],
                status=row["status"],
                output_file=row["output_file"],
                embedding_provider=row["embedding_provider"],
                embedding_model_name=row["embedding_model_name"],
                embedding_dimension=int(row["embedding_dimension"]) if row.get("embedding_dimension") else None,
                chat_provider=row["chat_provider"],
                chat_model_name=row["chat_model_name"],
                skipped_reason=row.get("skipped_reason", ""),
                error_summary=row.get("error_summary", ""),
                notes=row.get("notes", ""),
            )
            for row in reader
        ]


def redact_sensitive_text(text: str, settings: Settings) -> str:
    redacted = text
    for secret in [settings.embedding_api_key, settings.chat_model_api_key]:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted[:500]


def write_status(path: Path, statuses: list[RealConfigStatus]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        for status in statuses:
            writer.writerow(status.to_row())


def print_summary(statuses: list[RealConfigStatus], status_path: Path, comparison_error: str = "") -> None:
    print(f"stage 15 real config status: {len(statuses)} suites")
    for status in statuses:
        reason = status.skipped_reason or status.error_summary
        print(f"{status.suite}: {status.status}" + (f" ({reason})" if reason else ""))
    print(f"wrote status to {status_path}")
    if comparison_error:
        print(redact_sensitive_text(comparison_error, get_settings()))


if __name__ == "__main__":
    main()
