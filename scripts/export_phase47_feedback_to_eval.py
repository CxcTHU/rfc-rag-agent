from __future__ import annotations

import argparse
from pathlib import Path

from app.db.session import SessionLocal
from app.services.feedback.exporter import DEFAULT_OUTPUT_PATH, export_feedback_to_eval


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export positive Phase 47 feedback into evaluation CSV.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--since-days", type=int, default=None)
    parser.add_argument("--min-length", type=int, default=50)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    with SessionLocal() as db:
        result = export_feedback_to_eval(
            db,
            output_path=args.output,
            min_length=args.min_length,
            since_days=args.since_days,
            dry_run=args.dry_run,
        )
    action = "would export" if result.dry_run else "exported"
    print(
        f"feedback export {action}: candidates={result.candidates} "
        f"exported={result.exported} skipped_sensitive={result.skipped_sensitive} "
        f"skipped_duplicate={result.skipped_duplicate} output={result.output_path}"
    )


if __name__ == "__main__":
    main()
