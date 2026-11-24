import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlcipher

from app.backend.history import HistoryStore
from app.backend.history_key import load_or_create_key


@unittest.skipUnless(os.name == "nt", "Windows DPAPI is required")
class EncryptedHistoryTests(unittest.TestCase):
    def test_existing_plaintext_history_is_migrated_without_losing_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "history.sqlite3"
            key_path = root / "history-key.dpapi"
            with closing(sqlite3.connect(db_path)) as legacy:
                legacy.execute(
                    "CREATE TABLE migration_probe (value TEXT NOT NULL)"
                )
                legacy.execute(
                    "INSERT INTO migration_probe (value) VALUES (?)",
                    ("synthetic migration check",),
                )
                legacy.commit()

            store = HistoryStore(db_path, key_path=key_path)

            self.assertNotEqual(db_path.read_bytes()[:16], b"SQLite format 3\x00")
            self.assertNotIn(b"synthetic migration check", db_path.read_bytes())
            with closing(store._connect()) as encrypted:
                row = encrypted.execute(
                    "SELECT value FROM migration_probe"
                ).fetchone()
            self.assertEqual(row["value"], "synthetic migration check")
            with self.assertRaises(sqlite3.DatabaseError):
                with closing(sqlite3.connect(db_path)) as plaintext:
                    plaintext.execute(
                        "SELECT value FROM migration_probe"
                    ).fetchone()

            reopened = HistoryStore(db_path, key_path=key_path)
            self.assertIsNotNone(reopened)

    def test_wrong_dpapi_key_does_not_overwrite_encrypted_database(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "history.sqlite3"
            HistoryStore(db_path, key_path=root / "first-key.dpapi")
            before = db_path.read_bytes()

            with self.assertRaises(sqlcipher.Error):
                HistoryStore(db_path, key_path=root / "different-key.dpapi")

            self.assertEqual(db_path.read_bytes(), before)

    def test_dpapi_key_is_reused_and_not_stored_as_plaintext(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = Path(temp_dir) / "history-key.dpapi"

            first = load_or_create_key(key_path)
            protected = key_path.read_bytes()
            second = load_or_create_key(key_path)

            self.assertEqual(len(first), 32)
            self.assertEqual(first, second)
            self.assertNotEqual(protected, first)


if __name__ == "__main__":
    unittest.main()
