import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.backend.history import HistoryStore
from app.backend.uploads import purge_expired_uploads


class UploadRetentionTests(unittest.TestCase):
    def test_only_orphan_csv_files_older_than_48_hours_are_removed(self):
        now = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            upload_dir = root / "uploads"
            upload_dir.mkdir()
            history = HistoryStore(
                root / "history.sqlite3",
                key_path=root / "history-key.dpapi",
            )

            active_id = "a" * 64
            active = upload_dir / f"{active_id}.csv"
            old_orphan = upload_dir / f'{"b" * 64}.csv'
            recent_orphan = upload_dir / f'{"c" * 64}.csv'
            for path in (active, old_orphan, recent_orphan):
                path.write_text("value\n1\n", encoding="utf-8")

            history.attach_dataset(
                conversation_id="active",
                dataset_id=active_id,
                dataset_name="active.csv",
                harness="streamlit",
                now=now - timedelta(hours=47),
            )
            old_time = (now - timedelta(hours=49)).timestamp()
            recent_time = (now - timedelta(hours=47)).timestamp()
            os.utime(old_orphan, (old_time, old_time))
            os.utime(recent_orphan, (recent_time, recent_time))

            removed = purge_expired_uploads(upload_dir, history, now=now)

            self.assertEqual(removed, 1)
            self.assertTrue(active.exists())
            self.assertFalse(old_orphan.exists())
            self.assertTrue(recent_orphan.exists())


if __name__ == "__main__":
    unittest.main()
