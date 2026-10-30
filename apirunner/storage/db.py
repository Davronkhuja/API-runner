"""SQLite: tarix va boshqa katta/o'sib boruvchi ma'lumotlar (workspace/state.db)."""
import json
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    kind    TEXT NOT NULL,             -- request | run | url
    ts      REAL NOT NULL,
    payload TEXT NOT NULL,
    source  TEXT NOT NULL DEFAULT 'app' -- app | localstorage
);
CREATE INDEX IF NOT EXISTS idx_history_kind_ts ON history(kind, ts);
"""


class StateDB:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def add_history(self, kind, payload, ts=None, source="app"):
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO history(kind, ts, payload, source) VALUES (?,?,?,?)",
                      (kind, ts or time.time(), json.dumps(payload, ensure_ascii=False), source))

    def list_history(self, kind=None, limit=500):
        q, args = "SELECT * FROM history", []
        if kind:
            q += " WHERE kind=?"
            args.append(kind)
        q += " ORDER BY ts DESC, id DESC LIMIT ?"
        args.append(limit)
        with self._lock, self._conn() as c:
            return [{"id": r["id"], "kind": r["kind"], "ts": r["ts"], "source": r["source"],
                     "payload": json.loads(r["payload"])} for r in c.execute(q, args)]

    def count_history(self, source=None):
        with self._lock, self._conn() as c:
            if source:
                return c.execute("SELECT COUNT(*) FROM history WHERE source=?", (source,)).fetchone()[0]
            return c.execute("SELECT COUNT(*) FROM history").fetchone()[0]

    def delete_history(self, kind=None, item_id=None):
        with self._lock, self._conn() as c:
            if item_id is not None:
                c.execute("DELETE FROM history WHERE id=?", (item_id,))
            elif kind:
                c.execute("DELETE FROM history WHERE kind=?", (kind,))
            else:
                c.execute("DELETE FROM history")
