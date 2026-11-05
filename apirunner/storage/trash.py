"""Savat (Trash): o'chirilgan so'rov/papka/collection/muhit `workspace/trash/` da 30 kun saqlanadi va tiklanadi.

Tartib xavfsizligi: avval savatga YOZILADI (atomik), keyin asl element o'chiriladi — savatga yozilmasa o'chirish bekor.
"""
import os
import time
import uuid

from . import model, tree_ops
from .atomic import atomic_write_json  # noqa: F401  (workspace bilan bir xil yozuv)

RETENTION_DAYS = 30
KINDS = ("item", "collection", "environment")


class TrashError(ValueError):
    pass


def _count_requests(node):
    return sum(1 for _ in model.iter_requests(node["item"])) if model.is_folder(node) else 1


class Trash:
    def __init__(self, ws, now=time.time):
        self.ws, self.now = ws, now
        self.dir = os.path.join(ws.root, "trash")
        os.makedirs(self.dir, exist_ok=True)

    # ── yozish ──
    def _put(self, kind, name, payload, origin):
        tid = uuid.uuid4().hex
        t = self.now()
        doc = {"id": tid, "kind": kind, "name": name, "deleted_at": t, "expires_at": t + RETENTION_DAYS * 86400, "origin": origin, "payload": payload}
        atomic_write_json(os.path.join(self.dir, tid + ".json"), doc)
        return tid

    def add_item(self, col, item_id):
        """So'rov/papkani savatga qo'yadi (collection'dan O'CHIRMAYDI — chaqiruvchi o'chiradi)."""
        hit = tree_ops.find(col["item"], item_id)
        if not hit:
            raise tree_ops.TreeError("Element topilmadi")
        node, siblings, parent = hit
        origin = {"collection_id": model.collection_id(col), "collection_name": col["info"]["name"], "parent_id": parent["id"] if parent else None,
                  "parent_name": parent["name"] if parent else None, "index": siblings.index(node), "folder": model.is_folder(node), "requests": _count_requests(node)}
        return self._put("item", node.get("name", ""), node, origin)

    def add_collection(self, col):
        return self._put("collection", col["info"]["name"], col, {"collection_id": model.collection_id(col), "requests": sum(1 for _ in model.iter_requests(col["item"]))})

    def add_environment(self, env):
        return self._put("environment", env.get("name", ""), env, {"environment_id": env.get("id"), "values": len(env.get("values", []))})

    # ── o'qish ──
    def _read_all(self):
        out = []
        for fn in os.listdir(self.dir):
            if fn.endswith(".json"):
                try:
                    out.append(self.ws._read(os.path.join(self.dir, fn)))
                except (OSError, ValueError):
                    continue                                    # buzuq fayl ro'yxatni buzmasin (o'chirilmaydi)
        return out

    def purge_expired(self):
        n = 0
        for d in self._read_all():
            if d.get("expires_at", 0) < self.now():
                self._remove(d["id"])
                n += 1
        return n

    def list(self):
        self.purge_expired()
        rows = []
        for d in sorted(self._read_all(), key=lambda x: -x.get("deleted_at", 0)):
            rows.append({k: d.get(k) for k in ("id", "kind", "name", "deleted_at", "expires_at", "origin")} | {"days_left": max(0, int((d["expires_at"] - self.now()) // 86400) + (1 if (d["expires_at"] - self.now()) % 86400 else 0))})
        return rows

    def _path(self, tid):
        if not isinstance(tid, str) or not tid.isalnum():
            raise TrashError("Savat elementi topilmadi")
        return os.path.join(self.dir, tid + ".json")

    def _load(self, tid):
        p = self._path(tid)
        if not os.path.exists(p):
            raise TrashError("Savat elementi topilmadi")
        return self.ws._read(p)

    def _remove(self, tid):
        try:
            os.remove(self._path(tid))
        except FileNotFoundError:
            pass

    def delete(self, tid):
        self._load(tid)
        self._remove(tid)

    def empty(self):
        n = 0
        for d in self._read_all():
            self._remove(d["id"])
            n += 1
        return n

    # ── tiklash ──
    def restore(self, tid):
        d = self._load(tid)
        ws = self.ws
        with ws.lock:
            if d["kind"] == "item":
                res = self._restore_item(d)
            elif d["kind"] == "collection":
                col = d["payload"]
                if os.path.exists(ws._p("collections", model.collection_id(col) + ".json")):
                    col["info"]["_postman_id"] = model.new_id()                      # shu id band — yangi id bilan
                    col["info"]["name"] += " (tiklangan)"
                ws.save_collection(col)
                res = {"kind": "collection", "collection_id": model.collection_id(col)}
            else:
                env = d["payload"]
                if os.path.exists(ws._p("environments", env["id"] + ".json")):
                    env["id"] = model.new_id()
                    env["name"] += " (tiklangan)"
                ws.save_environment(env)
                res = {"kind": "environment", "environment_id": env["id"]}
            self._remove(tid)                                                         # faqat muvaffaqiyatli tiklangach
        return res

    def _restore_item(self, d):
        ws, node, o = self.ws, d["payload"], d["origin"]
        cid, created = o["collection_id"], False
        try:
            col = ws.get_collection(cid)
        except Exception:                                                              # noqa: BLE001 — collection ham o'chirilgan
            col = model.new_collection(o["collection_name"] + " (tiklangan)")
            cid, created = model.collection_id(col), True
        existing_ids = set()

        def ids(x):
            existing_ids.add(x["id"])
            for c in x.get("item", []):
                ids(c)
        for x in col["item"]:
            ids(x)
        if self._has_id(node, existing_ids):
            node = tree_ops.clone_with_new_ids(node)                                   # id to'qnashuvi (masalan nusxa olingan)
        parent_id = o.get("parent_id")
        if parent_id and not (tree_ops.find(col["item"], parent_id) and model.is_folder(tree_ops.find(col["item"], parent_id)[0])):
            parent_id = None                                                           # ota papka yo'q — ildizga
        tree_ops.add_item(col, parent_id, node, o.get("index"))
        ws.save_collection(col)
        return {"kind": "item", "collection_id": cid, "item_id": node["id"], "new_collection": created, "to_root": bool(o.get("parent_id")) and not parent_id}

    @staticmethod
    def _has_id(node, existing):
        return node["id"] in existing or any(Trash._has_id(c, existing) for c in node.get("item", []))
