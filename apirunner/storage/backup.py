"""Zaxira nusxalar: backups/<sana-vaqt>_v<versiya>/ (saved_requests.json + workspace/ + SQLite).

Qoidalar: avval to'liq nusxa (.partial -> rename), oxirgi 20 tasi saqlanadi, eskilari faqat yangisi
muvaffaqiyatli yaratilgandan keyin o'chiriladi; faqat shu papkadagi nom andozasiga mos kataloglar o'chiriladi.
"""
import json
import os
import re
import shutil
import sqlite3
import time

KEEP = 20
NAME_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?_v[\w.\-]+$")
DB_NAME = "state.db"
SKIP = {DB_NAME, DB_NAME + "-wal", DB_NAME + "-shm", ".lock"}


def _ignore(_dir, names):
    return [n for n in names if n in SKIP or n.endswith(".tmp")]


def _copy_db(src, dst):
    """SQLite'ni (WAL bilan ham) izchil nusxalaydi — oddiy fayl nusxasi -wal ni o'tkazib yuborishi mumkin."""
    s = sqlite3.connect(src)
    try:
        d = sqlite3.connect(dst)
        try:
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()


def create_backup(ws_root, saved_file, version, backup_dir, suffix="", keep=KEEP):
    os.makedirs(backup_dir, exist_ok=True)
    base = time.strftime("%Y%m%d-%H%M%S") + "_v" + str(version) + (("_" + suffix) if suffix else "")
    name, n = base, 1
    while os.path.exists(os.path.join(backup_dir, name)):
        n += 1
        name = time.strftime("%Y%m%d-%H%M%S") + f"-{n}_v{version}" + (("_" + suffix) if suffix else "")
    final = os.path.join(backup_dir, name)
    part = os.path.join(backup_dir, "." + name + ".partial")
    try:
        os.makedirs(part)
        has_saved = bool(saved_file) and os.path.isfile(saved_file)
        if has_saved:
            shutil.copy2(saved_file, os.path.join(part, "saved_requests.json"))
        if os.path.isdir(ws_root):
            shutil.copytree(ws_root, os.path.join(part, "workspace"), ignore=_ignore)
            db = os.path.join(ws_root, DB_NAME)
            if os.path.isfile(db):
                _copy_db(db, os.path.join(part, "workspace", DB_NAME))
        with open(os.path.join(part, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"version": str(version), "created": time.time(), "suffix": suffix,
                       "has_saved_requests": has_saved, "workspace": os.path.abspath(ws_root)}, f, indent=2)
        os.rename(part, final)
    except BaseException:
        shutil.rmtree(part, ignore_errors=True)          # faqat o'z .partial papkamiz
        raise
    prune(backup_dir, keep)
    return final


def list_backups(backup_dir):
    if not os.path.isdir(backup_dir):
        return []
    out = []
    for n in sorted(os.listdir(backup_dir), reverse=True):
        p = os.path.join(backup_dir, n)
        if NAME_RE.match(n) and os.path.isdir(p) and not os.path.islink(p):
            try:
                with open(os.path.join(p, "manifest.json"), encoding="utf-8") as f:
                    m = json.load(f)
            except (OSError, json.JSONDecodeError):
                m = {}
            out.append({"name": n, "path": p, "version": m.get("version"), "created": m.get("created"),
                        "suffix": m.get("suffix", ""), "has_saved_requests": m.get("has_saved_requests", False)})
    return out


def prune(backup_dir, keep=KEEP):
    """Oxirgi `keep` tasini qoldiradi. Faqat nom andozasiga mos, symlink bo'lmagan kataloglar o'chiriladi."""
    items = list_backups(backup_dir)          # yangidan eskiga
    for old in items[keep:]:
        real = os.path.realpath(old["path"])
        if os.path.dirname(real) == os.path.realpath(backup_dir):
            shutil.rmtree(real)
