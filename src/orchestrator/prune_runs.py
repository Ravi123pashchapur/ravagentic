import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prune old artifacts/runs entries.")
    parser.add_argument("--keep", type=int, default=20, help="How many newest runs to keep.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletion. Without this flag, prints a dry-run preview.",
    )
    return parser.parse_args()


def load_index(index_path: Path) -> List[Dict[str, Any]]:
    if not index_path.exists():
        return []
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def normalize_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for entry in entries:
        artifacts_dir = str(entry.get("artifacts_dir", "")).strip()
        if not artifacts_dir:
            continue
        normalized.append(
            {
                "timestamp_utc": str(entry.get("timestamp_utc", "")),
                "session_id": str(entry.get("session_id", "")),
                "artifacts_dir": artifacts_dir,
                "theme_name": str(entry.get("theme_name", "")),
                "validation_status": str(entry.get("validation_status", "not_run")),
                "context_version": str(entry.get("context_version", "")),
            }
        )
    return normalized


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    runs_dir = root / "artifacts" / "runs"
    index_path = runs_dir / "index.json"

    entries = normalize_entries(load_index(index_path))
    keep_count = max(args.keep, 0)
    keep_entries = entries[:keep_count]
    drop_entries = entries[keep_count:]

    print(f"Total indexed runs: {len(entries)}")
    print(f"Keeping newest: {len(keep_entries)}")
    print(f"Pruning: {len(drop_entries)}")

    for entry in drop_entries:
        print(f"- {entry['artifacts_dir']}")

    if not args.apply:
        print("Dry run only. Use --apply to delete and rewrite index.")
        return

    for entry in drop_entries:
        run_path = Path(entry["artifacts_dir"])
        if run_path.exists() and run_path.is_dir():
            shutil.rmtree(run_path)

    runs_dir.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(keep_entries, indent=2), encoding="utf-8")
    print(f"Updated index: {index_path}")


if __name__ == "__main__":
    main()
