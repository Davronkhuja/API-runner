"""Workspace'lar ro'yxati (`workspaces.json`): bir nechta alohida workspace papkasi, faolini eslab qolish.

Sukut workspace ("Shaxsiy workspace") — mavjud `workspace/` papkasi (o'zgarishsiz). Yangilari `<ildiz>/workspaces/<id>/` da; o'chirilganlari
`<ildiz>/workspaces/.trash/` ga ko'chiriladi va Savat orqali tiklanadi.
"""
import json
import os
import re
import shutil
import threading
import time
import uuid

from .atomic import atomic_write_json

DEFAULT_ID = "default"
DEFAULT_NAME = "Shaxsiy workspace"


class RegistryError(ValueError):
    pass


class WorkspaceRegistry:
    def __init__(self, path, default_dir):
        self.path = path
        self.default_dir = os.path.abspath(default_dir)
        self.root = os.path.join(os.path.dirname(os.path.abspath(path)), "workspaces")
        self.lock = threading.RLock()
        self.data = self._load()

    def _load(self):
        d = {}
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            d = {}
        items = [i for i in d.get("items", []) if isinstance(i, dict) and i.get("id") and i["id"] != DEFAULT_ID]
        names = {i["id"]: i.get("name") for i in d.get("items", []) if isinstance(i, dict)}
        d = {"active": d.get("active") or DEFAULT_ID, "default_name": names.get(DEFAULT_ID) or DEFAULT_NAME, "items": items}
        if d["active"] != DEFAULT_ID and not any(i["id"] == d["active"] for i in items):
            d["active"] = DEFAULT_ID
        return d

    def _save(self):
        atomic_write_json(self.path, self.data)

    def _dir(self, item_id):
        return self.default_dir if item_id == DEFAULT_ID else os.path.join(self.root, item_id)

    def list(self):
        with self.lock:
            out = [{"id": DEFAULT_ID, "name": self.data["default_name"], "default": True, "active": self.data["active"] == DEFAULT_ID, "path": self.default_dir}]
            for i in self.data["items"]:
                out.append({"id": i["id"], "name": i["name"], "default": False, "active": self.data["active"] == i["id"], "path": self._dir(i["id"]), "created": i.get("created")})
            return out

    def get(self, item_id):
        return next((i for i in self.list() if i["id"] == item_id), None)

    @property
    def active(self):
        return self.data["active"]

    def active_dir(self):
        return self._dir(self.data["active"])

    @staticmethod
    def _check_name(name):
        n = (name or "").strip()
        if not n:
            raise RegistryError("Workspace nomi bo'sh bo'lmasin")
        if len(n) > 60:
            raise RegistryError("Nom 60 belgidan oshmasin")
        return n

    def _unique(self, name):
        if name.lower() in {i["name"].lower() for i in self.list()}:
            raise RegistryError(f"«{name}» nomli workspace bor")

    def create(self, name):
        with self.lock:
            n = self._check_name(name)
            self._unique(n)
            wid = uuid.uuid4().hex[:10]
            os.makedirs(self._dir(wid), exist_ok=True)
            self.data["items"].append({"id": wid, "name": n, "created": time.time()})
            self._save()
            return wid

    def rename(self, item_id, name):
        with self.lock:
            n = self._check_name(name)
            if any(i["name"].lower() == n.lower() and i["id"] != item_id for i in self.list()):
                raise RegistryError(f"«{n}» nomli workspace bor")
            if item_id == DEFAULT_ID:
                self.data["default_name"] = n
            else:
                it = next((i for i in self.data["items"] if i["id"] == item_id), None)
                if not it:
                    raise RegistryError("Workspace topilmadi")
                it["name"] = n
            self._save()

    def set_active(self, item_id):
        with self.lock:
            if not self.get(item_id):
                raise RegistryError("Workspace topilmadi")
            self.data["active"] = item_id
            self._save()

    def remove(self, item_id):
        """Papkani `.trash/` ga ko'chiradi (o'chirmaydi). Qaytaradi: (item, ko'chirilgan yo'l)."""
        with self.lock:
            if item_id == DEFAULT_ID:
                raise RegistryError("Sukut workspace'ni o'chirib bo'lmaydi")
            if item_id == self.data["active"]:
                raise RegistryError("Faol workspace'ni o'chirib bo'lmaydi — avval boshqasiga o'ting")
            it = next((i for i in self.data["items"] if i["id"] == item_id), None)
            if not it:
                raise RegistryError("Workspace topilmadi")
            dest = os.path.join(self.root, ".trash", f"{item_id}-{int(time.time())}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.isdir(self._dir(item_id)):
                shutil.move(self._dir(item_id), dest)
            self.data["items"] = [i for i in self.data["items"] if i["id"] != item_id]
            self._save()
            return it, dest

    def restore(self, item, moved_to):
        with self.lock:
            if not re.fullmatch(r"[0-9a-f]{10}", item["id"]) or not os.path.isdir(moved_to):
                raise RegistryError("Workspace papkasi topilmadi (Savatdan o'chirilgan)")
            wid = item["id"] if not self.get(item["id"]) else uuid.uuid4().hex[:10]
            name = item["name"]
            if name.lower() in {i["name"].lower() for i in self.list()}:
                name += " (tiklangan)"
            os.makedirs(self.root, exist_ok=True)
            shutil.move(moved_to, self._dir(wid))
            self.data["items"].append({"id": wid, "name": name, "created": item.get("created")})
            self._save()
            return wid
