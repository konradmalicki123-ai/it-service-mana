# ai-generated: 90% - assistant drafted SQLite persistence so tickets survive a container restart (R-23)
"""Ticket store. One JSON document per ticket, in a file the compose file mounts as a named volume."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path


class TicketStore:
    def __init__(self, path: str) -> None:
        self._lock = threading.Lock()
        location = Path(path)
        location.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(location, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        self._conn.commit()

    def insert(self, ticket: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO tickets (id, data) VALUES (?, ?)",
                (ticket["id"], json.dumps(ticket)),
            )
            self._conn.commit()

    def get(self, ticket_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT data FROM tickets WHERE id = ?", (ticket_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, ticket: dict) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE tickets SET data = ? WHERE id = ?",
                (json.dumps(ticket), ticket["id"]),
            )
            self._conn.commit()

    def list_all(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT data FROM tickets").fetchall()
        return [json.loads(row[0]) for row in rows]


_store: TicketStore | None = None


def get_store() -> TicketStore:
    global _store
    if _store is None:
        path = os.environ.get("SVCDESK_DB", "/data/svcdesk.db")
        _store = TicketStore(path)
    return _store
