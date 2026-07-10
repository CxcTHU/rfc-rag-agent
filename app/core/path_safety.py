from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]


def resolve_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT_DIR / candidate
    return candidate.resolve()


def parse_allowed_roots(value: str) -> list[Path]:
    roots: list[Path] = []
    for item in value.split(";"):
        cleaned = item.strip()
        if cleaned:
            roots.append(resolve_project_path(cleaned))
    return roots or [resolve_project_path("data")]


def ensure_path_within_allowed_roots(path: str | Path, allowed_roots: list[Path]) -> Path:
    resolved = resolve_project_path(path)
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    allowed = ", ".join(root.as_posix() for root in allowed_roots)
    raise ValueError(f"path is outside allowed roots: {allowed}")


def ensure_child_path(path: str | Path, parent: str | Path) -> Path:
    return ensure_path_within_allowed_roots(path, [resolve_project_path(parent)])
