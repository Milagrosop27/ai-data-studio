"""Local SQLite conversation history with a strict 48-hour retention window."""

from __future__ import annotations

import gc
import os
import re
import sqlite3 as plain_sqlite
import time
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlcipher3 import dbapi2 as sqlite

from app.backend.history_key import load_or_create_key


RETENTION = timedelta(hours=48)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "output" / "agent_history.sqlite3"
EVENT_TYPES = {"user_request", "agent_response", "agent_action"}
STATUSES = {"ok", "error"}
ENCRYPTED_DB_KEY = "x'{key}'"


@dataclass(frozen=True)
class HistoryEvent:
    id: int
    conversation_id: str
    event_type: str
    timestamp_utc: str
    timestamp_local: str
    harness: str
    model: str
    status: str
    content: str


@dataclass(frozen=True)
class ConversationSummary:
    conversation_id: str
    dataset_id: str
    dataset_name: str
    last_activity_utc: str


def _aware_utc(value: datetime | None = None) -> datetime:
    value = value or datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return value.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class HistoryStore:
    """Persist encrypted conversation history and prune records older than 48 hours."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        *,
        key_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._key = load_or_create_key(key_path)
        except (OSError, RuntimeError) as error:
            raise sqlite.Error(
                "No se pudo recuperar la clave protegida por Windows; "
                "el historial no fue modificado."
            ) from error

        if self.db_path.exists():
            try:
                is_plaintext = (
                    self.db_path.read_bytes()[:16]
                ) == b"SQLite format 3\x00"
                if is_plaintext:
                    raise sqlite.Error("El archivo tiene el formato SQLite estándar.")
                self._validate_encrypted_database(self.db_path)
            except sqlite.Error as encrypted_error:
                if not self._is_valid_plaintext_database():
                    raise sqlite.Error(
                        "No se pudo abrir el historial con su clave protegida y "
                        "tampoco se reconoció como SQLite sin cifrar. La base "
                        "original se conservó sin cambios."
                    ) from encrypted_error
                self._migrate_plaintext_database()

        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL CHECK(length(conversation_id) > 0),
                    event_type TEXT NOT NULL
                        CHECK(event_type IN ('user_request', 'agent_response', 'agent_action')),
                    timestamp_utc TEXT NOT NULL,
                    timestamp_local TEXT NOT NULL,
                    harness TEXT NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('ok', 'error')),
                    content TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_events_timestamp
                ON conversation_events(timestamp_utc)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_events_conversation
                ON conversation_events(conversation_id, timestamp_utc)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_datasets (
                    conversation_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL CHECK(length(dataset_id) = 64),
                    dataset_name TEXT NOT NULL,
                    harness TEXT NOT NULL,
                    last_activity_utc TEXT NOT NULL
                )
                """
            )
            connection.commit()
        self.purge_expired()

    def _connect_path(
        self,
        path: str | Path,
        *,
        key: bytes,
    ) -> sqlite.Connection:
        connection = sqlite.connect(str(path), timeout=30)
        connection.execute(
            f'PRAGMA key = "{ENCRYPTED_DB_KEY.format(key=key.hex())}"'
        )
        if not connection.execute("PRAGMA cipher_version").fetchone():
            connection.close()
            raise sqlite.Error("La biblioteca SQLite activa no ofrece SQLCipher.")
        connection.execute("PRAGMA cipher_compatibility = 4")
        connection.row_factory = sqlite.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        connection.execute("PRAGMA secure_delete = ON")
        return connection

    def _connect(self) -> sqlite3.Connection:
        return self._connect_path(self.db_path, key=self._key)

    def _validate_encrypted_database(self, path: str | Path) -> None:
        with closing(self._connect_path(path, key=self._key)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise sqlite.Error("La comprobación de integridad del historial falló.")

    def _is_valid_plaintext_database(self) -> bool:
        if not self.db_path.is_file():
            return False
        try:
            with closing(plain_sqlite.connect(self.db_path, timeout=30)) as connection:
                result = connection.execute("PRAGMA integrity_check").fetchone()
                return bool(result and result[0] == "ok")
        except plain_sqlite.Error:
            return False

    @staticmethod
    def _data_snapshot(
        connection: sqlite.Connection | plain_sqlite.Connection,
    ) -> tuple[tuple[str, int], ...]:
        tables = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        snapshot = []
        for row in tables:
            table_name = str(row[0])
            quoted_name = table_name.replace('"', '""')
            count = connection.execute(
                f'SELECT COUNT(*) FROM "{quoted_name}"'
            ).fetchone()[0]
            snapshot.append((table_name, int(count)))
        return tuple(snapshot)

    def _migrate_plaintext_database(self) -> None:
        with closing(plain_sqlite.connect(self.db_path, timeout=30)) as source:
            checkpoint = source.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint and checkpoint[0] != 0:
                raise sqlite.Error(
                    "No se pudo bloquear y consolidar el historial para cifrarlo."
                )
            mode = source.execute("PRAGMA journal_mode = DELETE").fetchone()
            if not mode or str(mode[0]).lower() != "delete":
                raise sqlite.Error(
                    "No se pudo cerrar el diario SQLite antes de la migración."
                )
            integrity = source.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise sqlite.Error(
                    "El historial sin cifrar no pasó la comprobación de integridad."
                )
            source_snapshot = self._data_snapshot(source)

        encrypted_path = self.db_path.with_name(
            f"{self.db_path.name}.{uuid.uuid4().hex}.encrypted"
        )
        connection: sqlite.Connection | None = None
        try:
            connection = self._connect_path(encrypted_path, key=self._key)
            with closing(
                plain_sqlite.connect(self.db_path, timeout=30)
            ) as source:
                table_rows = source.execute(
                    """
                    SELECT name, sql
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name NOT LIKE 'sqlite_%'
                      AND sql IS NOT NULL
                    ORDER BY name
                    """
                ).fetchall()
                for table_name, create_sql in table_rows:
                    connection.execute(create_sql)

                for table_name, _ in table_rows:
                    quoted_name = str(table_name).replace('"', '""')
                    columns = source.execute(
                        f'PRAGMA table_info("{quoted_name}")'
                    ).fetchall()
                    column_names = [str(column[1]) for column in columns]
                    if not column_names:
                        continue
                    placeholders = ", ".join("?" for _ in column_names)
                    quoted_columns = ", ".join(
                        f'"{name.replace(chr(34), chr(34) * 2)}"'
                        for name in column_names
                    )
                    rows = source.execute(
                        f'SELECT {quoted_columns} FROM "{quoted_name}"'
                    ).fetchall()
                    if rows:
                        connection.executemany(
                            f'INSERT INTO "{quoted_name}" '
                            f'({quoted_columns}) VALUES ({placeholders})',
                            [tuple(row) for row in rows],
                        )

                auxiliary_objects = source.execute(
                    """
                    SELECT type, sql
                    FROM sqlite_master
                    WHERE sql IS NOT NULL
                      AND type IN ('index', 'trigger', 'view')
                    ORDER BY type, name
                    """
                ).fetchall()
                for _, sql in auxiliary_objects:
                    connection.execute(sql)
            connection.commit()
        except sqlite.Error:
            if connection is not None:
                connection.close()
            encrypted_path.unlink(missing_ok=True)
            raise
        else:
            connection.close()

        try:
            self._validate_encrypted_database(encrypted_path)
            with closing(
                self._connect_path(encrypted_path, key=self._key)
            ) as encrypted:
                encrypted_snapshot = self._data_snapshot(encrypted)
            if encrypted_snapshot != source_snapshot:
                raise sqlite.Error(
                    "La verificación de migración no coincide; "
                    "el historial original se conservó."
                )
            backup_path = self.db_path.with_name(
                f"{self.db_path.name}.{uuid.uuid4().hex}.plaintext-backup"
            )
            gc.collect()
            for attempt in range(10):
                try:
                    os.replace(self.db_path, backup_path)
                    break
                except PermissionError:
                    if attempt == 9:
                        raise
                    time.sleep(0.1)
            try:
                os.replace(encrypted_path, self.db_path)
            except Exception:
                if backup_path.exists():
                    os.replace(backup_path, self.db_path)
                raise
            if backup_path.exists():
                try:
                    size = backup_path.stat().st_size
                    with backup_path.open("r+b", buffering=0) as backup:
                        backup.write(os.urandom(size))
                        backup.flush()
                    backup_path.unlink()
                except OSError:
                    backup_path.unlink(missing_ok=True)
        finally:
            encrypted_path.unlink(missing_ok=True)
            Path(f"{encrypted_path}-wal").unlink(missing_ok=True)
            Path(f"{encrypted_path}-shm").unlink(missing_ok=True)

    def purge_expired(self, now: datetime | None = None) -> int:
        cutoff = _format_utc(_aware_utc(now) - RETENTION)
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM conversation_events WHERE timestamp_utc < ?",
                (cutoff,),
            )
            connection.execute(
                "DELETE FROM conversation_datasets WHERE last_activity_utc < ?",
                (cutoff,),
            )
            return cursor.rowcount

    def attach_dataset(
        self,
        *,
        conversation_id: str,
        dataset_id: str,
        dataset_name: str,
        harness: str = "streamlit",
        now: datetime | None = None,
    ) -> None:
        if not conversation_id.strip():
            raise ValueError("conversation_id must not be empty")
        if not re.fullmatch(r"[a-f0-9]{64}", dataset_id):
            raise ValueError("dataset_id must be a SHA-256 hexadecimal digest")
        if not dataset_name.strip() or not harness.strip():
            raise ValueError("dataset_name and harness must not be empty")

        timestamp = _format_utc(_aware_utc(now))
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO conversation_datasets (
                    conversation_id, dataset_id, dataset_name, harness,
                    last_activity_utc
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    dataset_id = excluded.dataset_id,
                    dataset_name = excluded.dataset_name,
                    harness = excluded.harness,
                    last_activity_utc = excluded.last_activity_utc
                """,
                (conversation_id, dataset_id, dataset_name, harness, timestamp),
            )

    def conversation_dataset(
        self,
        conversation_id: str,
        *,
        harness: str | None = None,
        now: datetime | None = None,
    ) -> ConversationSummary | None:
        self.purge_expired(now)
        query = """
            SELECT conversation_id, dataset_id, dataset_name, last_activity_utc
            FROM conversation_datasets
            WHERE conversation_id = ?
        """
        parameters: list[object] = [conversation_id]
        if harness is not None:
            query += " AND harness = ?"
            parameters.append(harness)
        with closing(self._connect()) as connection:
            row = connection.execute(query, parameters).fetchone()
        return ConversationSummary(**dict(row)) if row else None

    def delete_conversation(
        self,
        conversation_id: str,
        *,
        harness: str | None = None,
        now: datetime | None = None,
    ) -> str | None:
        if not conversation_id.strip():
            raise ValueError("conversation_id must not be empty")

        attachment = self.conversation_dataset(
            conversation_id,
            harness=harness,
            now=now,
        )
        dataset_id = attachment.dataset_id if attachment else None
        with closing(self._connect()) as connection, connection:
            if harness is None:
                connection.execute(
                    "DELETE FROM conversation_events WHERE conversation_id = ?",
                    (conversation_id,),
                )
                connection.execute(
                    "DELETE FROM conversation_datasets WHERE conversation_id = ?",
                    (conversation_id,),
                )
            else:
                connection.execute(
                    "DELETE FROM conversation_events "
                    "WHERE conversation_id = ? AND harness = ?",
                    (conversation_id, harness),
                )
                connection.execute(
                    "DELETE FROM conversation_datasets "
                    "WHERE conversation_id = ? AND harness = ?",
                    (conversation_id, harness),
                )
        return dataset_id

    def recent_conversations(
        self,
        *,
        harness: str,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[ConversationSummary]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        self.purge_expired(now)
        cutoff = _format_utc(_aware_utc(now) - RETENTION)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT conversation_id, dataset_id, dataset_name, last_activity_utc
                FROM conversation_datasets
                WHERE harness = ? AND last_activity_utc >= ?
                ORDER BY last_activity_utc DESC
                LIMIT ?
                """,
                (harness, cutoff, limit),
            ).fetchall()
        return [ConversationSummary(**dict(row)) for row in rows]

    def active_dataset_ids(
        self,
        *,
        now: datetime | None = None,
    ) -> set[str]:
        self.purge_expired(now)
        cutoff = _format_utc(_aware_utc(now) - RETENTION)
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT dataset_id FROM conversation_datasets
                WHERE last_activity_utc >= ?
                """,
                (cutoff,),
            ).fetchall()
        return {str(row["dataset_id"]) for row in rows}

    def record_event(
        self,
        *,
        conversation_id: str,
        event_type: str,
        content: str,
        harness: str,
        model: str,
        status: str,
        now: datetime | None = None,
    ) -> int:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unsupported event_type: {event_type}")
        if status not in STATUSES:
            raise ValueError(f"Unsupported status: {status}")
        if not conversation_id.strip():
            raise ValueError("conversation_id must not be empty")
        if not harness.strip() or not model.strip():
            raise ValueError("harness and model must not be empty")
        if not isinstance(content, str):
            raise TypeError("content must be a string")

        timestamp = _aware_utc(now)
        timestamp_utc = _format_utc(timestamp)
        timestamp_local = timestamp.astimezone().isoformat(timespec="microseconds")
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "DELETE FROM conversation_events WHERE timestamp_utc < ?",
                (_format_utc(timestamp - RETENTION),),
            )
            connection.execute(
                "DELETE FROM conversation_datasets WHERE last_activity_utc < ?",
                (_format_utc(timestamp - RETENTION),),
            )
            cursor = connection.execute(
                """
                INSERT INTO conversation_events (
                    conversation_id, event_type, timestamp_utc, timestamp_local,
                    harness, model, status, content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    event_type,
                    timestamp_utc,
                    timestamp_local,
                    harness,
                    model,
                    status,
                    content,
                ),
            )
            connection.execute(
                """
                UPDATE conversation_datasets
                SET last_activity_utc = ?
                WHERE conversation_id = ? AND harness = ?
                """,
                (timestamp_utc, conversation_id, harness),
            )
            return int(cursor.lastrowid)

    def recent_events(
        self,
        *,
        limit: int = 100,
        harness: str | None = None,
        now: datetime | None = None,
    ) -> list[HistoryEvent]:
        if limit < 1:
            raise ValueError("limit must be greater than zero")
        self.purge_expired(now)
        cutoff = _format_utc(_aware_utc(now) - RETENTION)
        query = """
            SELECT * FROM conversation_events
            WHERE timestamp_utc >= ?
        """
        parameters: list[object] = [cutoff]
        if harness is not None:
            query += " AND harness = ?"
            parameters.append(harness)
        query += " ORDER BY timestamp_utc DESC, id DESC LIMIT ?"
        parameters.append(limit)
        with closing(self._connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [HistoryEvent(**dict(row)) for row in reversed(rows)]

    def latest_conversation_id(
        self,
        *,
        harness: str | None = None,
        now: datetime | None = None,
    ) -> str | None:
        self.purge_expired(now)
        cutoff = _format_utc(_aware_utc(now) - RETENTION)
        query = """
            SELECT conversation_id FROM conversation_events
            WHERE timestamp_utc >= ?
        """
        parameters: list[object] = [cutoff]
        if harness is not None:
            query += " AND harness = ?"
            parameters.append(harness)
        query += " ORDER BY timestamp_utc DESC, id DESC LIMIT 1"
        with closing(self._connect()) as connection:
            row = connection.execute(query, parameters).fetchone()
        return str(row["conversation_id"]) if row else None

    def conversation_events(
        self,
        conversation_id: str,
        *,
        harness: str | None = None,
        now: datetime | None = None,
    ) -> list[HistoryEvent]:
        self.purge_expired(now)
        cutoff = _format_utc(_aware_utc(now) - RETENTION)
        query = """
            SELECT * FROM conversation_events
            WHERE conversation_id = ? AND timestamp_utc >= ?
        """
        parameters: list[object] = [conversation_id, cutoff]
        if harness is not None:
            query += " AND harness = ?"
            parameters.append(harness)
        query += " ORDER BY timestamp_utc, id"
        with closing(self._connect()) as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [HistoryEvent(**dict(row)) for row in rows]
