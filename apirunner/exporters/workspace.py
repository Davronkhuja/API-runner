"""Butun workspace zaxirasi (zip): collection'lar, muhitlar, globals, sozlamalar, biriktirilgan fayllar, (ixtiyoriy) tarix/javoblar bazasi.

Zip ichida `manifest.json` bor — import shu orqali tanib oladi. Muhit qiymatlari AYNAN saqlanganidek (Initial va Current, secret'lar bilan) ketadi:
bu zaxira, Postman eksporti emas; faylni begonalarga bermang.
"""
import io
import json
import os
import sqlite3
import tempfile
import time
import zipfile

from .. import __version__

KIND = "api-runner-workspace"


def export_zip(ws, include_state=True):
    """Qaytaradi: (bytes, manifest)."""
    buf = io.BytesIO()
    counts = {"collections": 0, "environments": 0, "files": 0}
    with ws.lock, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(ws._p("collections"))):
            if fn.endswith(".json"):
                z.write(ws._p("collections", fn), f"collections/{fn}")
                counts["collections"] += 1
        for fn in sorted(os.listdir(ws._p("environments"))):
            if fn.endswith(".json"):
                z.write(ws._p("environments", fn), f"environments/{fn}")
                counts["environments"] += 1
        for name in ("globals.json", "workspace.json"):
            if os.path.exists(ws._p(name)):
                z.write(ws._p(name), name)
        fdir = ws._p("files")
        if os.path.isdir(fdir):
            for root, _d, names in os.walk(fdir):
                for n in names:
                    if n.endswith(".part"):
                        continue
                    full = os.path.join(root, n)
                    z.write(full, os.path.relpath(full, ws.root).replace(os.sep, "/"))
                    counts["files"] += 1
        state = ws._p("state.db")
        if include_state and os.path.exists(state):
            with tempfile.TemporaryDirectory() as td:
                snap = os.path.join(td, "state.db")
                src, dst = sqlite3.connect(state), sqlite3.connect(snap)
                try:
                    src.backup(dst)                                    # izchil snapshot (WAL ham hisobga olinadi)
                finally:
                    dst.close(); src.close()
                z.write(snap, "state.db")
        manifest = {"kind": KIND, "app_version": __version__, "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "includes_state": bool(include_state), **counts}
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buf.getvalue(), manifest


def read_zip(data):
    """zip bytes -> {manifest, collections[], environments[], globals, files{name: bytes}}. Noto'g'ri zip — ValueError."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ValueError("Zip fayl buzuq") from e
    names = set(z.namelist())
    if "manifest.json" not in names:
        raise ValueError("Bu API Runner workspace zaxirasi emas (manifest.json yo'q)")
    try:
        manifest = json.loads(z.read("manifest.json"))
    except ValueError as e:
        raise ValueError("manifest.json buzuq") from e
    if manifest.get("kind") != KIND:
        raise ValueError("Bu API Runner workspace zaxirasi emas")
    total = sum(i.file_size for i in z.infolist())
    if total > 500 * 1024 * 1024:
        raise ValueError("Zip juda katta (500 MB dan ortiq ochilgan hajm)")

    def load(prefix):
        out = []
        for n in sorted(names):
            if n.startswith(prefix) and n.endswith(".json") and ".." not in n:
                out.append(json.loads(z.read(n)))
        return out
    g = json.loads(z.read("globals.json")) if "globals.json" in names else None
    files = {n: z.read(n) for n in names if n.startswith("files/") and not n.endswith("/") and ".." not in n}
    return {"manifest": manifest, "collections": load("collections/"), "environments": load("environments/"), "globals": g, "files": files}
