import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.backend.history import HistoryStore
from app.backend.uploads import purge_expired_uploads


def main() -> int:
    parser = argparse.ArgumentParser(description="Maintain or inspect the 48-hour agent history.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("purge", help="Purge records older than 48 hours")
    show = subparsers.add_parser("show", help="Show recent records as JSON")
    show.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    store = HistoryStore()
    if args.command == "purge":
        removed = purge_expired_uploads(ROOT / "data" / "uploads", store)
        print(
            "OK: historial purgado; cargas huérfanas de más de 48 horas "
            f"eliminadas: {removed}."
        )
        return 0

    print(
        json.dumps(
            [asdict(event) for event in store.recent_events(limit=args.limit)],
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
