import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.backend.history import HistoryStore


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = HistoryStore(
            Path(self.temp_dir.name) / "history.sqlite3",
            key_path=Path(self.temp_dir.name) / "history-key.dpapi",
        )
        self.now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.temp_dir.cleanup()

    def record(self, content, event_type="user_request", now=None, status="ok"):
        return self.store.record_event(
            conversation_id="conversation-a",
            event_type=event_type,
            content=content,
            harness="test",
            model="test-model",
            status=status,
            now=now or self.now,
        )

    def test_expired_records_are_purged_but_exact_48_hour_boundary_remains(self):
        self.record("boundary", now=self.now - timedelta(hours=48))
        self.record("older", now=self.now - timedelta(hours=49))

        deleted = self.store.purge_expired(now=self.now)
        self.record("recent", now=self.now)
        events = self.store.recent_events(now=self.now)

        self.assertEqual(deleted, 1)
        self.assertEqual([event.content for event in events], ["boundary", "recent"])

    def test_recording_a_request_purges_expired_rows_and_preserves_metadata(self):
        self.record("old", now=self.now - timedelta(hours=49))
        self.record("request", now=self.now)
        self.record(
            "response",
            event_type="agent_response",
            now=self.now + timedelta(seconds=1),
            status="error",
        )

        events = self.store.conversation_events("conversation-a", now=self.now)

        self.assertEqual([event.content for event in events], ["request", "response"])
        self.assertEqual(events[0].status, "ok")
        self.assertEqual(events[1].status, "error")
        self.assertEqual(events[0].harness, "test")
        self.assertTrue(events[0].timestamp_local)

    def test_invalid_inputs_and_naive_timestamps_are_rejected(self):
        with self.assertRaises(ValueError):
            self.record("bad", event_type="unknown")
        with self.assertRaises(ValueError):
            self.record("bad", now=datetime(2026, 11, 18))
        with self.assertRaises(ValueError):
            self.store.recent_events(limit=0, now=self.now)

    def test_latest_conversation_is_scoped_to_harness(self):
        self.record("one")
        self.store.record_event(
            conversation_id="pi-conversation",
            event_type="user_request",
            content="two",
            harness="pi",
            model="gemma",
            status="ok",
            now=self.now + timedelta(seconds=1),
        )

        self.assertEqual(
            self.store.latest_conversation_id(harness="test", now=self.now),
            "conversation-a",
        )
        self.assertEqual(
            self.store.latest_conversation_id(harness="pi", now=self.now),
            "pi-conversation",
        )

    def test_dataset_attachment_can_be_resumed_until_48_hours_of_inactivity(self):
        dataset_id = "a" * 64
        self.store.attach_dataset(
            conversation_id="conversation-a",
            dataset_id=dataset_id,
            dataset_name="sales.csv",
            harness="streamlit",
            now=self.now,
        )
        self.record("first question", now=self.now)

        recent = self.store.recent_conversations(
            harness="streamlit",
            now=self.now + timedelta(hours=47),
        )
        expired = self.store.recent_conversations(
            harness="streamlit",
            now=self.now + timedelta(hours=48, seconds=1),
        )

        self.assertEqual(recent[0].dataset_id, dataset_id)
        self.assertEqual(recent[0].dataset_name, "sales.csv")
        self.assertEqual(expired, [])
        self.assertIsNone(
            self.store.conversation_dataset(
                "conversation-a",
                harness="streamlit",
                now=self.now + timedelta(hours=48, seconds=1),
            )
        )

    def test_dataset_id_must_be_a_sha256_digest(self):
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.store.attach_dataset(
                conversation_id="conversation-a",
                dataset_id="../secrets",
                dataset_name="sales.csv",
                now=self.now,
            )

    def test_delete_conversation_removes_events_and_dataset_attachment(self):
        dataset_id = "a" * 64
        self.store.attach_dataset(
            conversation_id="conversation-a",
            dataset_id=dataset_id,
            dataset_name="sales.csv",
            harness="streamlit",
            now=self.now,
        )
        self.record("first question", now=self.now)

        deleted_dataset_id = self.store.delete_conversation(
            "conversation-a",
            harness="streamlit",
            now=self.now,
        )

        self.assertEqual(deleted_dataset_id, dataset_id)
        self.assertEqual(
            self.store.conversation_events(
                "conversation-a",
                harness="streamlit",
                now=self.now,
            ),
            [],
        )
        self.assertIsNone(
            self.store.conversation_dataset(
                "conversation-a",
                harness="streamlit",
                now=self.now,
            )
        )


if __name__ == "__main__":
    unittest.main()
