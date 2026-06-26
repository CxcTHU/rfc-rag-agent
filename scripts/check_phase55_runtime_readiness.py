from __future__ import annotations

import argparse
import csv
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings, get_settings  # noqa: E402
from app.db.models import Chunk, ChunkEmbedding, Conversation, Document, Message, QAFeedback, User  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "phase55_runtime_readiness.csv"
FIELDS = ["check_id", "area", "status", "value", "evidence", "next_action"]


@dataclass(frozen=True)
class RuntimeRow:
    check_id: str
    area: str
    status: str
    value: str
    evidence: str
    next_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "check_id": self.check_id,
            "area": self.area,
            "status": self.status,
            "value": self.value,
            "evidence": self.evidence,
            "next_action": self.next_action,
        }


def main() -> None:
    args = parse_args()
    settings = get_settings()
    with SessionLocal() as db:
        rows = build_runtime_rows(
            settings=settings,
            db=db,
            data_dir=Path(args.data_dir),
            check_reranker=args.check_reranker,
            urlopen_func=urllib.request.urlopen,
        )
    output = Path(args.output)
    write_csv(output, rows)
    counts = summarize(rows)
    print(
        "phase55_runtime_readiness "
        f"ok={counts['ok']} warn={counts['warn']} error={counts['error']} "
        f"manual={counts['manual']}"
    )
    print(f"wrote {output}")
    if counts["error"]:
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check production runtime readiness from inside the app container."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--data-dir", default="data")
    parser.add_argument(
        "--check-reranker",
        action="store_true",
        help="Call RERANKING_BASE_URL /health. Use only when private BGE should be reachable.",
    )
    return parser.parse_args()


def build_runtime_rows(
    *,
    settings: Settings,
    db: Session,
    data_dir: Path,
    check_reranker: bool,
    urlopen_func: Callable[..., object],
) -> list[RuntimeRow]:
    rows: list[RuntimeRow] = []
    rows.extend(config_rows(settings))
    rows.extend(database_rows(db))
    rows.extend(asset_rows(data_dir, settings))
    rows.append(pgvector_row(db))
    rows.append(reranker_row(settings, check_reranker, urlopen_func))
    return rows


def config_rows(settings: Settings) -> list[RuntimeRow]:
    return [
        bool_row(
            "app_env_production",
            "config",
            settings.app_env == "production",
            settings.app_env or "unset",
            "APP_ENV should be production in docker-compose.prod.yml.",
            "Set APP_ENV=production through production compose.",
        ),
        bool_row(
            "auth_enabled",
            "security",
            settings.auth_enabled,
            str(settings.auth_enabled).lower(),
            "AUTH_ENABLED should be true before public launch.",
            "Keep AUTH_ENABLED=true and run auth-enabled smoke.",
        ),
        bool_row(
            "jwt_secret_configured",
            "security",
            bool(settings.jwt_secret_key and len(settings.jwt_secret_key) >= 24),
            "configured" if settings.jwt_secret_key else "missing",
            "JWT secret is present and not printed.",
            "Set a long random JWT_SECRET_KEY in .env.prod.",
        ),
        bool_row(
            "embedding_dimension",
            "retrieval",
            settings.embedding_dimension == 2048,
            str(settings.embedding_dimension),
            "GLM-Embedding-3 production vector path expects 2048 dimensions.",
            "Set EMBEDDING_DIMENSION=2048 or document an intentional fallback.",
        ),
        bool_row(
            "graph_path_configured",
            "graphrag",
            bool(settings.graphrag_graph_path),
            settings.graphrag_graph_path or "missing",
            "GraphRAG path is configured.",
            "Set GRAPHRAG_GRAPH_PATH when graph search is enabled.",
        ),
    ]


def database_rows(db: Session) -> list[RuntimeRow]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - driver-specific
        return [
            RuntimeRow(
                check_id="database_connection",
                area="database",
                status="error",
                value=exc.__class__.__name__,
                evidence="Database connection failed.",
                next_action="Check DATABASE_URL, db container health, and network.",
            )
        ]

    rows = [
        count_row("documents", "database", db.query(Document).count(), minimum=1),
        count_row("chunks", "database", db.query(Chunk).count(), minimum=1),
        count_row("chunk_embeddings", "database", db.query(ChunkEmbedding).count(), minimum=1),
        count_row("users", "auth", db.query(User).count(), minimum=0),
        count_row("conversations", "auth", db.query(Conversation).count(), minimum=0),
        count_row("messages", "auth", db.query(Message).count(), minimum=0),
        count_row("qa_feedback", "feedback", db.query(QAFeedback).count(), minimum=0),
    ]
    for chunk_type, count in chunk_type_counts(db).items():
        rows.append(count_row(f"chunks_{chunk_type}", "database", count, minimum=0))
    return rows


def chunk_type_counts(db: Session) -> dict[str, int]:
    result = db.execute(text("select chunk_type, count(*) from chunks group by chunk_type"))
    return {str(chunk_type): int(count) for chunk_type, count in result}


def asset_rows(data_dir: Path, settings: Settings) -> list[RuntimeRow]:
    images_dir = data_dir / "images"
    faiss_dir = data_dir / "faiss"
    graph_path = Path(settings.graphrag_graph_path)
    if not graph_path.is_absolute():
        graph_path = data_dir.parent / graph_path
    return [
        path_row("data_images_dir", "assets", images_dir, expect_dir=True),
        path_row("data_faiss_dir", "assets", faiss_dir, expect_dir=True),
        bool_row(
            "faiss_index_files",
            "assets",
            bool(list(faiss_dir.glob("*.index"))) if faiss_dir.exists() else False,
            "present" if faiss_dir.exists() and list(faiss_dir.glob("*.index")) else "missing",
            "At least one FAISS index file exists.",
            "Rebuild FAISS from production PostgreSQL embeddings if missing.",
        ),
        path_row("graphrag_graph_file", "graphrag", graph_path, expect_dir=False),
    ]


def pgvector_row(db: Session) -> RuntimeRow:
    try:
        dialect = db.bind.dialect.name if db.bind is not None else "unknown"
        if dialect != "postgresql":
            return RuntimeRow(
                check_id="pgvector_extension",
                area="database",
                status="warn",
                value=dialect,
                evidence="Not running on PostgreSQL, so pgvector cannot be verified.",
                next_action="Production should use docker-compose.prod.yml PostgreSQL/pgvector.",
            )
        ext = db.execute(text("select extname from pg_extension where extname='vector'")).scalar()
    except Exception as exc:  # pragma: no cover - driver-specific
        return RuntimeRow(
            check_id="pgvector_extension",
            area="database",
            status="error",
            value=exc.__class__.__name__,
            evidence="pgvector extension check failed.",
            next_action="Run Alembic against pgvector/pgvector:pg16 and verify vector extension.",
        )
    return bool_row(
        "pgvector_extension",
        "database",
        ext == "vector",
        str(ext or "missing"),
        "pgvector extension is installed.",
        "Use pgvector/pgvector:pg16 and run Alembic migrations.",
    )


def reranker_row(
    settings: Settings,
    check_reranker: bool,
    urlopen_func: Callable[..., object],
) -> RuntimeRow:
    if not settings.reranking_enabled:
        return RuntimeRow(
            check_id="reranker_health",
            area="reranker",
            status="manual",
            value="disabled",
            evidence="RERANKING_ENABLED=false; BGE is intentionally off.",
            next_action="Document this as a launch fallback if BGE is not required.",
        )
    if not check_reranker:
        return RuntimeRow(
            check_id="reranker_health",
            area="reranker",
            status="manual",
            value="not_checked",
            evidence="Use --check-reranker to call private BGE /health from inside the app container.",
            next_action="Run with --check-reranker when BGE is expected.",
        )
    base = settings.reranking_base_url.rstrip("/")
    try:
        with urlopen_func(f"{base}/health", timeout=5) as response:
            status_code = int(getattr(response, "status", 200))
    except Exception as exc:  # pragma: no cover - network-specific
        return RuntimeRow(
            check_id="reranker_health",
            area="reranker",
            status="error",
            value=exc.__class__.__name__,
            evidence="Private BGE /health was not reachable from the app runtime.",
            next_action="Fix GPU private route, VPN, sidecar tunnel, or disable reranking intentionally.",
        )
    return bool_row(
        "reranker_health",
        "reranker",
        200 <= status_code < 300,
        str(status_code),
        "Private BGE /health responded from the app runtime.",
        "Inspect reranking traces and confirm reranking_fallback=false during smoke.",
    )


def bool_row(
    check_id: str,
    area: str,
    condition: bool,
    value: str,
    evidence: str,
    next_action: str,
) -> RuntimeRow:
    return RuntimeRow(
        check_id=check_id,
        area=area,
        status="ok" if condition else "error",
        value=value,
        evidence=evidence if condition else "Check did not meet launch expectation.",
        next_action="No action." if condition else next_action,
    )


def count_row(check_id: str, area: str, count: int, *, minimum: int) -> RuntimeRow:
    return RuntimeRow(
        check_id=check_id,
        area=area,
        status="ok" if count >= minimum else "error",
        value=str(count),
        evidence=f"{check_id} count={count}.",
        next_action="No action." if count >= minimum else f"Expected at least {minimum}; sync or rebuild data.",
    )


def path_row(check_id: str, area: str, path: Path, *, expect_dir: bool) -> RuntimeRow:
    exists = path.is_dir() if expect_dir else path.is_file()
    kind = "directory" if expect_dir else "file"
    return RuntimeRow(
        check_id=check_id,
        area=area,
        status="ok" if exists else "error",
        value=str(path),
        evidence=f"{kind} exists." if exists else f"{kind} is missing.",
        next_action="No action." if exists else f"Sync or rebuild {path}.",
    )


def summarize(rows: list[RuntimeRow]) -> dict[str, int]:
    counts = {"ok": 0, "warn": 0, "error": 0, "manual": 0}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return counts


def write_csv(path: Path, rows: list[RuntimeRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(row.as_dict() for row in rows)


if __name__ == "__main__":
    main()
