"""Probe Phase 65 runtime cancel/resume behavior through the real API surface.

The summary is intentionally narrow: component pass/fail categories and bounded
counters only. It must not persist auth tokens, run ids, answers, source text,
provider payloads, prompts, or secrets.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings
from app.db.session import create_database_engine
from scripts.verify_phase65_production_topology import (
    http_json_request,
    join_url,
    probe_auth,
)


ComponentStatus = Literal["pass", "fail", "skip"]
HttpJsonFn = Callable[[str, str, dict[str, object] | None, str | None], dict[str, object]]
CancelSseFn = Callable[[str, str, int], set[str]]
CollectSseFn = Callable[[str, str, dict[str, object]], dict[str, object]]
StoppedRunLookup = Callable[[int], str]
CheckpointInserter = Callable[[int], str]


@dataclass(frozen=True)
class RecoveryProbeResult:
    status: ComponentStatus
    category: str = "ok"

    def safe_detail(self) -> dict[str, str]:
        return {
            "status": normalize_status(self.status),
            "category": safe_category(self.category),
        }


def normalize_status(value: str | None) -> ComponentStatus:
    if value == "pass":
        return "pass"
    if value == "skip":
        return "skip"
    return "fail"


def safe_category(value: str | None) -> str:
    candidate = "".join(
        char
        for char in str(value or "unknown").lower()
        if char.isalnum() or char in {"_", "-"}
    )
    return candidate[:80] or "unknown"


def build_recovery_summary(
    *,
    cancel: RecoveryProbeResult,
    resume: RecoveryProbeResult,
) -> dict[str, object]:
    components = {
        "sse_cancel_marks_stopped": normalize_status(cancel.status),
        "resume_sse_from_checkpoint": normalize_status(resume.status),
    }
    failed = [name for name, status in components.items() if status != "pass"]
    return {
        "schema_version": "phase65-runtime-recovery-v1",
        "gate": "pass" if not failed else "blocked",
        "components": components,
        "failed_required": failed,
        "details": {
            "sse_cancel_marks_stopped": cancel.safe_detail(),
            "resume_sse_from_checkpoint": resume.safe_detail(),
        },
    }


def probe_cancel_marks_stopped_run(
    *,
    base_url: str,
    token: str,
    http_json: HttpJsonFn = http_json_request,
    cancel_sse: CancelSseFn | None = None,
    latest_stopped_run: StoppedRunLookup,
) -> RecoveryProbeResult:
    base = base_url.strip()
    if not base:
        return RecoveryProbeResult("skip", "missing_base_url")
    if not token.strip():
        return RecoveryProbeResult("skip", "missing_auth_token")
    conversation = http_json(
        "POST",
        join_url(base, "/conversations"),
        {"title": "Phase65 runtime recovery smoke"},
        token,
    )
    if int(conversation.get("status_code", 0) or 0) != 200:
        return RecoveryProbeResult("fail", "conversation_create_failed")
    payload = conversation.get("json", {})
    conversation_id = int(payload.get("id", 0) or 0) if isinstance(payload, dict) else 0
    if conversation_id <= 0:
        return RecoveryProbeResult("fail", "conversation_id_missing")
    try:
        cancel = cancel_sse or cancel_sse_after_first_event
        event_names = cancel(base, token, conversation_id)
    except Exception:
        return RecoveryProbeResult("fail", "cancel_sse_failed")
    if not event_names:
        return RecoveryProbeResult("fail", "cancel_sse_no_events")
    stopped_run_id = latest_stopped_run(conversation_id)
    if not stopped_run_id:
        return RecoveryProbeResult("fail", "cancel_stopped_run_missing")
    return RecoveryProbeResult("pass")


def probe_resume_sse_from_checkpoint(
    *,
    base_url: str,
    token: str,
    conversation_id: int,
    insert_checkpoint: CheckpointInserter,
    collect_sse: CollectSseFn | None = None,
) -> RecoveryProbeResult:
    base = base_url.strip()
    if not base:
        return RecoveryProbeResult("skip", "missing_base_url")
    if not token.strip():
        return RecoveryProbeResult("skip", "missing_auth_token")
    if conversation_id <= 0:
        return RecoveryProbeResult("fail", "conversation_id_missing")
    try:
        run_id = insert_checkpoint(conversation_id)
    except Exception:
        return RecoveryProbeResult("fail", "checkpoint_insert_failed")
    if not run_id:
        return RecoveryProbeResult("fail", "checkpoint_run_missing")
    payload: dict[str, object] = {
        "question": "继续",
        "conversation_id": conversation_id,
        "resume_run_id": run_id,
        "resume_policy": "force",
        "max_tool_calls": 2,
    }
    try:
        collect = collect_sse or collect_resume_sse
        stream = collect(base, token, payload)
    except Exception:
        return RecoveryProbeResult("fail", "resume_sse_failed")
    event_names = stream.get("event_names", set())
    if not isinstance(event_names, set) or "done" not in event_names:
        return RecoveryProbeResult("fail", "resume_done_missing")
    metadata = stream.get("metadata", {})
    if not isinstance(metadata, dict) or not metadata:
        return RecoveryProbeResult("fail", "resume_metadata_missing")
    trace = metadata.get("latency_trace", {})
    if not isinstance(trace, dict) or trace.get("runtime_resumed") is not True:
        return RecoveryProbeResult("fail", "resume_not_reported")
    if int(trace.get("executed_tool_call_count", -1) or 0) != 0:
        return RecoveryProbeResult("fail", "resume_replayed_tool_execution")
    return RecoveryProbeResult("pass")


def cancel_sse_after_first_event(
    base_url: str,
    token: str,
    conversation_id: int,
    *,
    timeout_seconds: float = 30.0,
) -> set[str]:
    payload = {
        "question": "堆石混凝土有哪些优势？",
        "conversation_id": conversation_id,
        "max_tool_calls": 2,
        "resume_policy": "never",
        "evaluation_run_namespace": f"phase65-recovery-cancel-{uuid.uuid4().hex[:12]}",
    }
    request = urllib.request.Request(
        join_url(base_url, "/agent/query/stream"),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    event_names: set[str] = set()
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("event:"):
                continue
            event_name = line.partition(":")[2].strip()
            if event_name:
                event_names.add(event_name)
            if event_names:
                return event_names
    return event_names


def collect_resume_sse(
    base_url: str,
    token: str,
    payload: dict[str, object],
    *,
    timeout_seconds: float = 45.0,
) -> dict[str, object]:
    request = urllib.request.Request(
        join_url(base_url, "/agent/query/stream"),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    event_names: set[str] = set()
    current_event = ""
    metadata: dict[str, object] = {}
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if line.startswith("event:"):
                current_event = line.partition(":")[2].strip()
                if current_event:
                    event_names.add(current_event)
                if current_event == "done":
                    break
            elif line.startswith("data:") and current_event == "metadata":
                parsed = json.loads(line.partition(":")[2].strip() or "{}")
                if isinstance(parsed, dict):
                    metadata = parsed
    return {"event_names": event_names, "metadata": metadata}


def latest_stopped_run_lookup(
    *,
    database_url: str,
    timeout_seconds: float = 10.0,
) -> StoppedRunLookup:
    def lookup(conversation_id: int) -> str:
        engine = create_database_engine(database_url)
        deadline = time.monotonic() + max(0.1, timeout_seconds)
        while time.monotonic() <= deadline:
            with engine.begin() as connection:
                run_id = connection.execute(
                    text(
                        "SELECT run_id FROM agent_runtime_runs "
                        "WHERE conversation_id=:conversation_id AND status='stopped' "
                        "ORDER BY updated_at DESC, id DESC LIMIT 1"
                    ),
                    {"conversation_id": conversation_id},
                ).scalar()
            if run_id:
                return str(run_id)
            time.sleep(0.25)
        return ""

    return lookup


def synthetic_checkpoint_inserter(*, database_url: str) -> CheckpointInserter:
    def insert(conversation_id: int) -> str:
        run_id = f"phase65-recovery-{uuid.uuid4().hex}"
        state = {
            "sources": [
                {
                    "source_id": "phase65-recovery-source",
                    "title": "Phase65 synthetic recovery evidence",
                    "source_type": "synthetic",
                    "document_id": 0,
                    "chunk_id": 0,
                    "chunk_index": 0,
                    "content": "Synthetic checkpoint evidence for runtime recovery smoke.",
                    "score": 1.0,
                }
            ],
            "workflow_steps": [
                {
                    "tool_name": "hybrid_search_knowledge",
                    "input_summary": "checkpoint",
                    "output_summary": "synthetic stopped checkpoint",
                    "succeeded": True,
                    "error": None,
                }
            ],
        }
        engine = create_database_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO agent_runtime_runs "
                    "(conversation_id,run_id,status,current_node,last_completed_node,"
                    "resume_token_hash,request_question,canonical_task,state_json,"
                    "created_at,updated_at,expires_at) "
                    "VALUES (:conversation_id,:run_id,'stopped','stopped',"
                    "'tool_execution_completed',:resume_token_hash,:request_question,"
                    ":canonical_task,:state_json,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,"
                    ":expires_at)"
                ),
                {
                    "conversation_id": conversation_id,
                    "run_id": run_id,
                    "resume_token_hash": uuid.uuid4().hex,
                    "request_question": "继续",
                    "canonical_task": "phase65 runtime recovery smoke",
                    "state_json": json.dumps(state, ensure_ascii=False, sort_keys=True),
                    "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                },
            )
        return run_id

    return insert


def write_summary(path: Path, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--database-url", default=settings.database_url)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("output/phase65/runtime-recovery-smoke.json"),
    )
    args = parser.parse_args(argv)
    auth_state: dict[str, str] = {}
    auth = probe_auth(base_url=args.base_url, token_sink=auth_state)
    token = auth_state.get("token", "")
    if auth.status != "pass":
        summary = build_recovery_summary(
            cancel=RecoveryProbeResult("fail", "auth_failed"),
            resume=RecoveryProbeResult("fail", "auth_failed"),
        )
    else:
        cancel = probe_cancel_marks_stopped_run(
            base_url=args.base_url,
            token=token,
            latest_stopped_run=latest_stopped_run_lookup(database_url=args.database_url),
        )
        conversation = http_json_request(
            "POST",
            join_url(args.base_url, "/conversations"),
            {"title": "Phase65 runtime resume smoke"},
            token,
        )
        conversation_json = conversation.get("json", {})
        conversation_id = (
            int(conversation_json.get("id", 0) or 0)
            if isinstance(conversation_json, dict)
            else 0
        )
        resume = probe_resume_sse_from_checkpoint(
            base_url=args.base_url,
            token=token,
            conversation_id=conversation_id,
            insert_checkpoint=synthetic_checkpoint_inserter(
                database_url=args.database_url
            ),
        )
        summary = build_recovery_summary(cancel=cancel, resume=resume)
    write_summary(args.out, summary)
    print(
        "gate={gate} failed_required={failed_required}".format(**summary)
    )
    return 0 if summary["gate"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
