"""Sxema migratsiyalari (schemaVersion) va xavfsiz ishga tushirish.

Tartib: kutilayotgan ish bormi? -> to'liq zaxira -> oldingi sonlar -> migratsiya -> keyingi sonlar ->
nomuvofiqlik/xato bo'lsa zaxiradan ROLLBACK. Har qadam idempotent (qayta ishga tushsa dublikat/yo'qotish yo'q).
Asl saved_requests.json hech qachon o'zgartirilmaydi yoki o'chirilmaydi.
"""
import json
import os
import sqlite3

from . import backup as bk
from . import model
from .db import connect, entry_hash
from .migrate import legacy_to_collection, migrate_saved_requests
from .workspace import CURRENT_SCHEMA


class MigrationError(RuntimeError):
    pass


def count_workspace(ws):
    """Papkalar, so'rovlar, env'lar, collection'lar soni (verifikatsiya uchun)."""
    folders = requests = 0

    def walk(items):
        nonlocal folders, requests
        for it in items:
            if model.is_folder(it):
                folders += 1
                walk(it["item"])
            else:
                requests += 1
    cols = ws.list_collections()
    for c in cols:
        walk(ws.get_collection(c["id"])["item"])
    return {"collections": len(cols), "folders": folders, "requests": requests,
            "environments": len(ws.list_environments())}


def count_legacy(data):
    if isinstance(data, list):
        data = {"folders": [], "requests": data}
    return {"collections": 1, "folders": len(data.get("folders", [])), "requests": len(data.get("requests", [])),
            "environments": 0}


def _add(a, b):
    return {k: a.get(k, 0) + b.get(k, 0) for k in set(a) | set(b)}


# ── sxema qadamlari: {versiya: fn(ws)} — fn versiya -> versiya+1 ga o'tkazadi, idempotent bo'lishi shart ──
def step_1_to_2(ws):
    """SQLite tarixiga `hash` ustuni + dedupe indeksi; mavjud localStorage yozuvlari uchun xesh to'ldiriladi.

    Mavjud ma'lumot o'chirilmaydi: takroriy xeshli qatorlar xeshsiz (NULL) qoladi.
    """
    db = os.path.join(ws.root, "state.db")
    c = connect(db)
    try:
        c.execute("PRAGMA journal_mode=WAL")
        exists = c.execute("SELECT 1 FROM sqlite_master WHERE name='history'").fetchone()
        if not exists:
            return
        cols = [r[1] for r in c.execute("PRAGMA table_info(history)")]
        if "hash" not in cols:
            c.execute("ALTER TABLE history ADD COLUMN hash TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_history_dedupe ON history(source, kind, hash) WHERE hash IS NOT NULL")
        rows = c.execute("SELECT id, source, kind, payload FROM history WHERE hash IS NULL AND source='localstorage'").fetchall()
        for r in rows:
            try:
                h = entry_hash(json.loads(r["payload"]))
            except json.JSONDecodeError:
                continue
            try:
                c.execute("UPDATE history SET hash=? WHERE id=?", (h, r["id"]))
            except sqlite3.IntegrityError:
                pass                                   # takroriy — xeshsiz qoladi, o'chirilmaydi
        c.commit()
    finally:
        c.close()


STEPS = {1: step_1_to_2}


def restore_workspace(backup_path, ws_root):
    """Zaxiradan workspace'ni joyiga qaytaradi (rollback). Qaytishdan oldin joriy holat o'chirilmaydi — almashtiriladi."""
    from .restore import swap_workspace
    swap_workspace(backup_path, ws_root)


def run_all(ws, saved_file, backup_dir, version, steps=None, current=None):
    """Qaytaradi: {status, legacy, message, backup, before, after}.

    status: nothing | ok | rolled_back.  legacy: nothing | skipped | migrated | corrupt | failed
    """
    steps = STEPS if steps is None else steps
    current = CURRENT_SCHEMA if current is None else current
    res = {"status": "nothing", "legacy": "nothing", "message": "", "backup": None, "before": None, "after": None}

    # 1) nima kutilmoqda
    legacy_counts = None
    if ws.meta().get("legacy_migrated"):
        res["legacy"] = "skipped"
    elif saved_file and os.path.isfile(saved_file):
        try:
            with open(saved_file, "r", encoding="utf-8") as f:
                legacy_counts = count_legacy(json.load(f))
            res["legacy"] = "pending"
        except (json.JSONDecodeError, OSError):
            res["legacy"] = "corrupt"                 # tegmaymiz; keyingi ishga tushishda qayta uriniladi
    schema_pending = ws.schema_version() < current
    if res["legacy"] != "pending" and not schema_pending:
        return res

    # 2) HAR QANDAY o'zgarishdan oldin to'liq zaxira
    res["backup"] = bk.create_backup(ws.root, saved_file, version, backup_dir)
    before = count_workspace(ws)
    expected = _add(before, legacy_counts) if legacy_counts else dict(before)
    res["before"] = before
    try:
        if res["legacy"] == "pending":
            outcome = migrate_saved_requests(ws, saved_file)
            if outcome != "migrated":
                raise MigrationError(f"legacy import natijasi: {outcome}")
            res["legacy"] = "migrated"
        v = ws.schema_version()
        while v < current:
            if v not in steps:
                raise MigrationError(f"{v} -> {v + 1} uchun migratsiya yo'q")
            steps[v](ws)
            v += 1
            ws.update_meta(schemaVersion=v)
        after = count_workspace(ws)
        res["after"] = after
        for k in ("folders", "requests", "environments"):
            if after[k] != expected[k]:
                raise MigrationError(f"{k} soni mos emas: kutilgan {expected[k]}, bor {after[k]}")
        res["status"] = "ok"
    except Exception as exc:                            # noqa: BLE001 — har qanday xatoda rollback
        restore_workspace(res["backup"], ws.root)
        res.update(status="rolled_back", legacy="failed" if res["legacy"] in ("pending", "migrated") else res["legacy"],
                   message=f"Migratsiya bekor qilindi va zaxiradan tiklandi: {exc}")
    return res
