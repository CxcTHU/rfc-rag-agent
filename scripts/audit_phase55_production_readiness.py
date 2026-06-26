from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "evaluation" / "phase55_production_readiness_audit.csv"

FIELDS = [
    "requirement_id",
    "area",
    "status",
    "evidence",
    "next_action",
]


@dataclass(frozen=True)
class AuditRow:
    requirement_id: str
    area: str
    status: str
    evidence: str
    next_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "requirement_id": self.requirement_id,
            "area": self.area,
            "status": self.status,
            "evidence": self.evidence,
            "next_action": self.next_action,
        }


def main() -> None:
    args = parse_args()
    rows = build_audit_rows(ROOT)
    output = Path(args.output)
    write_csv(output, rows)
    counts = summarize(rows)
    print(
        "phase55_production_readiness_audit "
        f"complete={counts['complete']} partial={counts['partial']} "
        f"missing={counts['missing']} manual_required={counts['manual_required']}"
    )
    print(f"wrote {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit Phase 55 production-readiness artifacts without reading secrets."
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def build_audit_rows(root: Path) -> list[AuditRow]:
    compose = read_text(root / "docker-compose.prod.yml")
    runbook = read_text(root / "docs" / "phase55_production_readiness.md")
    smoke = read_text(root / "scripts" / "run_production_smoke.py")
    runtime_check = read_text(root / "scripts" / "check_phase55_runtime_readiness.py")
    deployment_guide = read_text(root / "docs" / "deployment_guide.md")
    data_sources = read_text(root / "docs" / "data_sources.md")
    completion_audit = read_text(root / "docs" / "phase55_completion_audit.md")

    return [
        check_contains(
            "compose_auth_enabled",
            "config",
            compose,
            ["AUTH_ENABLED: \"true\"", "JWT_SECRET_KEY"],
            "docker-compose.prod.yml forces production auth and JWT secret injection.",
            "Keep AUTH_ENABLED=true in production compose.",
        ),
        check_contains(
            "compose_pgvector_redis",
            "config",
            compose,
            ["pgvector/pgvector:pg16", "redis/redis-stack-server:latest", "REDIS_PASSWORD"],
            "docker-compose.prod.yml uses pgvector PostgreSQL and Redis Stack.",
            "Keep DB/Redis private and password protected.",
        ),
        check_contains(
            "compose_placeholder_config_documented",
            "config",
            runbook,
            ["docker compose -f docker-compose.prod.yml", "placeholder-db-password", "config --quiet"],
            "Phase 55 runbook includes value-blind compose config smoke.",
            "Run the command on the operator machine before launch.",
        ),
        check_contains(
            "bge_cpu_to_gpu_topology",
            "reranker",
            runbook,
            ["CPU server", "GPU server", "Inside Docker, `127.0.0.1` means the app container itself"],
            "Runbook documents CPU Docker app to separate GPU reranker topology.",
            "Set RERANKING_BASE_URL to a container-reachable private route.",
        ),
        check_contains(
            "bge_container_health_smoke",
            "reranker",
            runbook,
            ["RERANKING_BASE_URL", "/health", "docker compose -f docker-compose.prod.yml"],
            "Runbook includes app-container reranker /health smoke.",
            "Run from the app container after GPU/private route is configured.",
        ),
        check_contains(
            "runtime_asset_integrity",
            "data",
            runbook,
            ["check_phase55_runtime_readiness.py", "data/images", "data/faiss", "data/knowledge_graph/domain_graph.json", "pg_extension"],
            "Runbook includes database, pgvector, images, FAISS, and graph asset checks.",
            "Record actual server counts in launch evidence.",
        ),
        check_contains(
            "runtime_readiness_script",
            "data",
            runtime_check,
            ["phase55_runtime_readiness", "chunk_embeddings", "pgvector_extension", "reranker_health"],
            "Runtime readiness script checks DB, assets, pgvector, and optional reranker health.",
            "Run inside the production app container after compose startup.",
        ),
        check_contains(
            "auth_enabled_smoke_script",
            "smoke",
            smoke,
            ["--auth-enabled", "auth_login_smoke_user", "agent_query_unauthenticated_401"],
            "Production smoke supports AUTH_ENABLED=true login/token flow and unauthenticated 401 check.",
            "Run with --execute --auth-enabled against the production base URL.",
        ),
        check_contains(
            "auth_enabled_smoke_runbook",
            "smoke",
            runbook,
            ["--auth-enabled", "unauthenticated /agent/query returns 401", "/auth/login"],
            "Runbook documents auth-enabled smoke expectations.",
            "Do not paste returned tokens into logs or docs.",
        ),
        check_contains(
            "backup_restore_runbook",
            "ops",
            runbook,
            ["pg_dump", "pg_restore", "data/images data/faiss data/knowledge_graph"],
            "Runbook includes PostgreSQL and runtime asset backup/restore commands.",
            "Rehearse restore on a non-production target before official launch.",
        ),
        check_contains(
            "security_exposure_checklist",
            "security",
            runbook,
            ["DB, Redis, and BGE private", "only app HTTP port", "AUTH_ENABLED=true"],
            "Runbook includes public exposure and auth security checklist.",
            "Keep domain/HTTPS as the remaining separate launch blocker.",
        ),
        check_contains(
            "deployment_guide_links_phase55",
            "docs",
            deployment_guide,
            ["Phase 55", "phase55_production_readiness.md"],
            "Deployment guide links to the Phase 55 readiness runbook.",
            "Update docs/deployment_guide.md to point operators at Phase 55.",
        ),
        check_contains(
            "data_sources_phase55_note",
            "docs",
            data_sources,
            ["Phase 55", "production readiness"],
            "Data sources doc records that Phase 55 adds operational artifacts only.",
            "Update docs/data_sources.md with the Phase 55 data boundary.",
        ),
        check_contains(
            "completion_audit_traceability",
            "docs",
            completion_audit,
            ["Requirement Traceability", "manual_required", "1275 passed, 1 skipped"],
            "Completion audit maps Phase 55 requirements to evidence and the remaining manual runtime gate.",
            "Keep docs/phase55_completion_audit.md aligned with final validation results.",
        ),
        AuditRow(
            requirement_id="server_runtime_smoke",
            area="manual",
            status="manual_required",
            evidence="Requires running production stack on CPU server with local-only .env.prod.",
            next_action="Run auth-enabled production smoke and BGE/data checks on the server before official launch.",
        ),
    ]


def check_contains(
    requirement_id: str,
    area: str,
    text: str,
    needles: list[str],
    complete_evidence: str,
    next_action: str,
) -> AuditRow:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        return AuditRow(
            requirement_id=requirement_id,
            area=area,
            status="missing",
            evidence=f"missing markers: {', '.join(missing)}",
            next_action=next_action,
        )
    return AuditRow(
        requirement_id=requirement_id,
        area=area,
        status="complete",
        evidence=complete_evidence,
        next_action=next_action,
    )


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def summarize(rows: list[AuditRow]) -> dict[str, int]:
    counts = {"complete": 0, "partial": 0, "missing": 0, "manual_required": 0}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return counts


def write_csv(path: Path, rows: list[AuditRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(row.as_dict() for row in rows)


if __name__ == "__main__":
    main()
