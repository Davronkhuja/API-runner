"""SQLite: tarix va boshqa o'sib boruvchi ma'lumotlar (workspace/state.db). WAL rejimida."""
import hashlib
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
    source  TEXT NOT NULL DEFAULT 'app', -- app | localstorage
    hash    TEXT
);
CREATE INDEX IF NOT EXISTS idx_history_kind_ts ON history(kind, ts);
"""
HASH_INDEX = ("CREATE UNIQUE INDEX IF NOT EXISTS idx_history_dedupe ON history(source, kind, hash) "
              "WHERE hash IS NOT NULL")


def entry_hash(payload):
    """Yozuvning barqaror xeshi — localStorage importi dublikat yaratmasligi uchun."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def connect(path):
    c = sqlite3.connect(path, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=15000")
    return c


class StateDB:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        c = connect(path)
        try:
            c.execute("PRAGMA journal_mode=WAL")           # doimiy; bir vaqtda o'qish/yozish xavfsiz
            if self._fresh(c):
                c.executescript(SCHEMA)               # yangi baza: hash ustuni bilan (schema 2)
            c.commit()
            cols = [r[1] for r in c.execute("PRAGMA table_info(history)")]
            self.has_hash = "hash" in cols
            if self.has_hash:
                c.execute(HASH_INDEX)
            c.commit()
        finally:
            c.close()

    @staticmethod
    def _fresh(c):
        return c.execute("SELECT name FROM sqlite_master WHERE name='history'").fetchone() is None

    def journal_mode(self):
        c = connect(self.path)
        try:
            return c.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            c.close()

    def add_history(self, kind, payload, ts=None, source="app", dedupe=False):
        """Qo'shilgan bo'lsa True. dedupe=True: bir xil (source, kind, mazmun) yozuv qayta qo'shilmaydi."""
        h = entry_hash(payload) if (dedupe and self.has_hash) else None
        with self._lock:
            c = connect(self.path)
            try:
                with c:
                    if self.has_hash:
                        cur = c.execute("INSERT OR IGNORE INTO history(kind, ts, payload, source, hash) VALUES (?,?,?,?,?)",
                                        (kind, ts or time.time(), json.dumps(payload, ensure_ascii=False), source, h))
                    else:
                        cur = c.execute("INSERT INTO history(kind, ts, payload, source) VALUES (?,?,?,?)",
                                        (kind, ts or time.time(), json.dumps(payload, ensure_ascii=False), source))
                    return cur.rowcount > 0
            finally:
                c.close()

    def list_history(self, kind=None, limit=500):
        q, args = "SELECT * FROM history", []
        if kind:
            q += " WHERE kind=?"
            args.append(kind)
        q += " ORDER BY ts DESC, id DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            c = connect(self.path)
            try:
                return [{"id": r["id"], "kind": r["kind"], "ts": r["ts"], "source": r["source"],
                         "payload": json.loads(r["payload"])} for r in c.execute(q, args)]
            finally:
                c.close()

    def count_history(self, source=None):
        with self._lock:
            c = connect(self.path)
            try:
                if source:
                    return c.execute("SELECT COUNT(*) FROM history WHERE source=?", (source,)).fetchone()[0]
                return c.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            finally:
                c.close()

    def delete_history(self, kind=None, item_id=None):
        with self._lock:
            c = connect(self.path)
            try:
                with c:
                    if item_id is not None:
                        c.execute("DELETE FROM history WHERE id=?", (item_id,))
                    elif kind:
                        c.execute("DELETE FROM history WHERE kind=?", (kind,))
                    else:
                        c.execute("DELETE FROM history")
            finally:
                c.close()
