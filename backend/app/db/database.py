"""SQLite connection helpers."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.OperationalError:
            pass
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            conn = self.connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS incidents (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        error_message TEXT NOT NULL,
                        stack_trace TEXT NOT NULL,
                        repository_path TEXT,
                        status TEXT NOT NULL,
                        root_cause_analysis TEXT,
                        proposed_patch TEXT,
                        validation_results TEXT,
                        approval TEXT,
                        history TEXT NOT NULL DEFAULT '[]',
                        details TEXT NOT NULL DEFAULT '{}',
                        fingerprint TEXT,
                        version INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                self._ensure_column(conn, "incidents", "details", "TEXT NOT NULL DEFAULT '{}'")
                self._ensure_column(conn, "incidents", "fingerprint", "TEXT")
                self._ensure_column(conn, "incidents", "version", "INTEGER NOT NULL DEFAULT 1")
                try:
                    # Databases created before the column existed keep the value inside the JSON blob.
                    conn.execute(
                        "UPDATE incidents SET fingerprint = json_extract(details, '$.fingerprint') "
                        "WHERE fingerprint IS NULL AND json_extract(details, '$.fingerprint') IS NOT NULL"
                    )
                except sqlite3.OperationalError:
                    pass  # SQLite built without JSON1: old rows simply will not group with new alerts
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_incidents_fingerprint ON incidents(fingerprint)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at)"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        incident_id TEXT,
                        actor TEXT NOT NULL,
                        action TEXT NOT NULL,
                        detail TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, spec: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        names = {row["name"] for row in rows}
        if column not in names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {spec}")

    @property
    def lock(self) -> threading.Lock:
        return self._lock
