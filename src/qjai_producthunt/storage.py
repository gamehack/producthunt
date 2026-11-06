"""SQLite checkpoints for deterministic, resumable content production."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StepStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._initialize()

    def _db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _initialize(self) -> None:
        with self._db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS steps (
                run_id TEXT NOT NULL,
                step TEXT NOT NULL,
                payload TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                PRIMARY KEY (run_id, step)
            )""")
    def read(self, run_id: str, step: str) -> Any | None:
        with self._db() as db:
            row = db.execute("SELECT payload FROM steps WHERE run_id=? AND step=?", (run_id, step)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, run_id: str, step: str, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._db() as db:
            db.execute("""INSERT INTO steps (run_id, step, payload, completed_at)
                VALUES (?, ?, ?, ?) ON CONFLICT(run_id, step) DO NOTHING""",
                (run_id, step, body, datetime.now(timezone.utc).isoformat()))

