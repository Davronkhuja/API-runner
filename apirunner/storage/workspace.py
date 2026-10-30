"""Workspace — diskdagi papka (git-friendly JSON fayllar):

    workspace/
      workspace.json
      collections/<id>.json
      environments/<id>.json
      globals.json
      state.db            (SQLite: tarix va h.k.)
      imports/            (localStorage importining xom nusxalari)
"""
import json
import os
import re

from . import model
from .atomic import atomic_write_json
from .lock import WorkspaceLock

CURRENT_SCHEMA = 2

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class NotFound(KeyError):
    pass


class Conflict(RuntimeError):
    """Boshqa tab/jarayon ma'lumotni o'zgartirgan (rev mos kelmaydi)."""


class Workspace:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)
        self.lock = WorkspaceLock(os.path.join(self.root, ".lock"))
        for sub in ("collections", "environments", "imports"):
            os.makedirs(os.path.join(self.root, sub), exist_ok=True)
        if not os.path.exists(self._p("workspace.json")):
            # yangi workspace — hozirgi sxema; mavjud (eski) workspace.json'da schemaVersion yo'q = 1
            self._write(self._p("workspace.json"), {"version": model.MODEL_VERSION, "schemaVersion": CURRENT_SCHEMA})
        if not os.path.exists(self._p("globals.json")):
            self._write(self._p("globals.json"), model.new_globals())

    # ── yordamchi ──
    def _p(self, *parts):
        return os.path.join(self.root, *parts)

    @staticmethod
    def _check_id(i):
        if not isinstance(i, str) or not _SAFE_ID.match(i):
            raise NotFound(i)
        return i

    @staticmethod
    def _write(path, data):
        atomic_write_json(path, data)   # tmp -> fsync -> os.replace (yarim yozilgan fayl qolmaydi)

    @staticmethod
    def _read(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ── meta ──
    def meta(self):
        with self.lock:
            return self._read(self._p("workspace.json"))

    def schema_version(self):
        return int(self.meta().get("schemaVersion", 1))

    def update_meta(self, **kw):
        with self.lock:
            m = self.meta()
            m.update(kw)
            self._write(self._p("workspace.json"), m)

    # ── collections ──
    def list_collections(self):
        with self.lock:
            out = []
            for fn in sorted(os.listdir(self._p("collections"))):
                if fn.endswith(".json"):
                    c = self._read(self._p("collections", fn))
                    out.append({"id": model.collection_id(c), "name": c["info"]["name"],
                                "requests": sum(1 for _ in model.iter_requests(c["item"]))})
            return out

    def get_collection(self, cid):
        path = self._p("collections", self._check_id(cid) + ".json")
        with self.lock:
            if not os.path.exists(path):
                raise NotFound(cid)
            col = self._read(path)
            col.setdefault("x-apirunner", {}).setdefault("rev", 0)      # rev'siz eski fayl = 0
            return col

    def _bump_rev(self, path, doc, expected_rev, holder):
        """Optimistik versiya tekshiruvi: expected_rev berilgan va diskdagiga teng bo'lmasa — Conflict."""
        cur = 0
        if os.path.exists(path):
            try:
                cur = (self._read(path).get(holder) or {}).get("rev", 0) if holder else self._read(path).get("rev", 0)
            except (json.JSONDecodeError, OSError):
                cur = 0
        if expected_rev is not None and expected_rev != cur:
            raise Conflict(f"rev {expected_rev} != {cur}")
        if holder:
            doc.setdefault(holder, {})["rev"] = cur + 1
        else:
            doc["rev"] = cur + 1

    def save_collection(self, col, expected_rev=None):
        cid = self._check_id(model.collection_id(col))
        path = self._p("collections", cid + ".json")
        with self.lock:
            self._bump_rev(path, col, expected_rev, "x-apirunner")
            self._write(path, col)
        return cid

    def delete_collection(self, cid):
        path = self._p("collections", self._check_id(cid) + ".json")
        with self.lock:
            if not os.path.exists(path):
                raise NotFound(cid)
            os.remove(path)

    # ── environments ──
    def list_environments(self):
        with self.lock:
            out = [self._read(self._p("environments", fn))
                   for fn in sorted(os.listdir(self._p("environments"))) if fn.endswith(".json")]
            for e in out:
                e.setdefault("rev", 0)
            return out

    def get_environment(self, eid):
        path = self._p("environments", self._check_id(eid) + ".json")
        with self.lock:
            if not os.path.exists(path):
                raise NotFound(eid)
            env = self._read(path)
            env.setdefault("rev", 0)
            return env

    def save_environment(self, env, expected_rev=None):
        eid = self._check_id(env["id"])
        path = self._p("environments", eid + ".json")
        with self.lock:
            self._bump_rev(path, env, expected_rev, None)
            self._write(path, env)
        return eid

    def delete_environment(self, eid):
        path = self._p("environments", self._check_id(eid) + ".json")
        with self.lock:
            if not os.path.exists(path):
                raise NotFound(eid)
            os.remove(path)

    # ── globals ──
    def get_globals(self):
        with self.lock:
            g = self._read(self._p("globals.json"))
            g.setdefault("rev", 0)
            return g

    def save_globals(self, g, expected_rev=None):
        with self.lock:
            self._bump_rev(self._p("globals.json"), g, expected_rev, None)
            self._write(self._p("globals.json"), g)

    # ── UI holati ──
    def get_ui_state(self):
        path = self._p("ui_state.json")
        with self.lock:
            if not os.path.exists(path):
                return {}
            try:
                return self._read(path)
            except json.JSONDecodeError:
                return {}

    def save_ui_state(self, state):
        with self.lock:
            self._write(self._p("ui_state.json"), state)
