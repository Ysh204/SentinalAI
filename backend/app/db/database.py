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
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    @property
    def lock(self) -> threading.Lock:
        return self._lock
