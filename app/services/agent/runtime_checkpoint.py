"""Compatibility exports for the Phase 65 checkpoint boundary.

New runtime code imports from :mod:`checkpoint_repository`.  This module keeps
the Phase 58 public/internal import path stable while callers migrate.
"""

from app.services.agent.checkpoint_repository import (
    AgentRuntimeRunRepository,
    ResumeDecision,
    RuntimeRunSnapshot,
    RuntimeRunStatus,
    as_utc,
    decide_resume,
    find_requested_or_latest_run,
    hash_resume_token,
    is_explicit_continue,
    load_runtime_state,
    runtime_resume_diagnostics,
    sanitize_runtime_state,
    serialize_runtime_state,
)

__all__ = [
    "AgentRuntimeRunRepository",
    "ResumeDecision",
    "RuntimeRunSnapshot",
    "RuntimeRunStatus",
    "as_utc",
    "decide_resume",
    "find_requested_or_latest_run",
    "hash_resume_token",
    "is_explicit_continue",
    "load_runtime_state",
    "runtime_resume_diagnostics",
    "sanitize_runtime_state",
    "serialize_runtime_state",
]
