from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.backend.history import RETENTION, HistoryStore


def purge_expired_uploads(
    upload_dir: str | Path,
    history: HistoryStore,
    *,
    now: datetime | None = None,
) -> int:
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    cutoff = current_time.timestamp() - RETENTION.total_seconds()
    active_dataset_ids = history.active_dataset_ids(now=current_time)
    directory = Path(upload_dir)
    if not directory.exists():
        return 0

    removed = 0
    for path in directory.glob("*.csv"):
        if path.stem in active_dataset_ids:
            continue
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed
