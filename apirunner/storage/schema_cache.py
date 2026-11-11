"""GraphQL sxema keshi (workspace/schemas/<sha256(kalit)>.json): qayta yaratish mumkin bo'lgan kesh, foydalanuvchi ma'lumoti emas."""
import hashlib
import json
import os
import time

from .atomic import atomic_write_json


def _path(ws_root, key):
    d = os.path.join(ws_root, "schemas")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, hashlib.sha256(key.encode("utf-8")).hexdigest()[:32] + ".json")


def get(ws_root, key):
    try:
        with open(_path(ws_root, key), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def put(ws_root, key, introspection):
    atomic_write_json(_path(ws_root, key), {"key": key, "fetched_at": time.time(), "introspection": introspection})


def delete(ws_root, key):
    try:
        os.remove(_path(ws_root, key))
    except FileNotFoundError:
        pass
