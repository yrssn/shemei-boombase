import sqlite3
from contextlib import contextmanager
from datetime import datetime

from .schemas import HistoryItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    shortcode TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    caption TEXT NOT NULL DEFAULT '',
    sentiment_label TEXT NOT NULL DEFAULT '',
    operator TEXT NOT NULL DEFAULT '',
    written_to_doc INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, path: str):
        self.path = path
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add(self, *, url: str, shortcode: str, author: str, caption: str, sentiment_label: str,
            operator: str, written_to_doc: bool) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO history (url, shortcode, author, caption, sentiment_label, operator, written_to_doc, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (url, shortcode, author, caption, sentiment_label, operator, int(written_to_doc),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            return int(cur.lastrowid)

    def list(self, limit: int = 50) -> list[HistoryItem]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [HistoryItem(**{**dict(r), "written_to_doc": bool(r["written_to_doc"])}) for r in rows]
