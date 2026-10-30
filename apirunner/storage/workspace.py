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
import threading

from . import model

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class NotFound(KeyError):
    pass


class Workspace:
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.lock = threading.RLock()
        for sub in ("collections", "environments", "imports"):
            os.makedirs(os.path.join(self.root, sub), exist_ok=True)
        if not os.path.exists(self._p("workspace.json")):
            self._write(self._p("workspace.json"), {"version": model.MODEL_VERSION})
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
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)          # atomik: yarim yozilgan fayl qolmaydi

    @staticmethod
    def _read(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ── meta ──
    def meta(self):
        with self.lock:
            return self._read(self._p("workspace.json"))

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
            return self._read(path)

    def save_collection(self, col):
        cid = self._check_id(model.collection_id(col))
        with self.lock:
            self._write(self._p("collections", cid + ".json"), col)
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
            return [self._read(self._p("environments", fn))
                    for fn in sorted(os.listdir(self._p("environments"))) if fn.endswith(".json")]

    def get_environment(self, eid):
        path = self._p("environments", self._check_id(eid) + ".json")
        with self.lock:
            if not os.path.exists(path):
                raise NotFound(eid)
            return self._read(path)

    def save_environment(self, env):
        eid = self._check_id(env["id"])
        with self.lock:
            self._write(self._p("environments", eid + ".json"), env)
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
            return self._read(self._p("globals.json"))

    def save_globals(self, g):
        with self.lock:
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
