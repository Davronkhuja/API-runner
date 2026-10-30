"""Migratsiyalar.

1) saved_requests.json -> workspace (bir martalik, avval .bak nusxa; asl fayl TEGILMAYDI).
2) localStorage -> workspace (UI'dagi tugma POST qiladi; idempotent).
"""
import json
import os
import shutil
import time

from . import model

LEGACY_COLLECTION_ID = "saved"
LEGACY_COLLECTION_NAME = "Saqlangan so'rovlar"


def _backup(path):
    bak = path + ".bak"
    if os.path.exists(bak):
        bak = f"{path}.{time.strftime('%Y%m%d-%H%M%S')}.bak"
    shutil.copy2(path, bak)
    return bak


def legacy_to_collection(data):
    """{'folders': [...], 'requests': [...]} (yoki eski ro'yxat formati) -> collection."""
    if isinstance(data, list):
        data = {"folders": [], "requests": data}
    col = model.new_collection(LEGACY_COLLECTION_NAME, LEGACY_COLLECTION_ID)
    folders = {}
    for f in data.get("folders", []):
        f = dict(f)
        f.setdefault("id", model.new_id())          # id'siz yozuv tashlab yuborilmaydi (ma'lumot yo'qotilmasin)
        node = model.new_folder(f.get("name", ""), f["id"], f.get("expanded", True), legacy=f)
        folders[f["id"]] = node
        col["item"].append(node)
    for r in data.get("requests", []):
        r = dict(r)
        r.setdefault("id", model.new_id())
        item = model.legacy_to_request_item(r)
        parent = folders.get(r.get("folder_id"))
        (parent["item"] if parent else col["item"]).append(item)
    return col


def migrate_saved_requests(ws, saved_file):
    """Qaytaradi: 'migrated' | 'skipped' | 'nothing' | 'corrupt'."""
    if ws.meta().get("legacy_migrated"):
        return "skipped"
    if not saved_file or not os.path.isfile(saved_file):
        return "nothing"
    try:
        with open(saved_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return "corrupt"                      # tegmaymiz, keyingi ishga tushishda qayta urinamiz
    bak = _backup(saved_file)
    ws.save_collection(legacy_to_collection(data))
    ws.update_meta(legacy_migrated=True, legacy_source=os.path.abspath(saved_file), legacy_backup=bak)
    return "migrated"


def _loads(v, default):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            return default
    return v if v is not None else default


def _as_list(v):
    v = _loads(v, [])
    return v if isinstance(v, list) else []


def _kv(vars_):
    if isinstance(vars_, dict):
        return [{"key": k, "value": str(v), "enabled": True, "type": "default"} for k, v in vars_.items()]
    return [{"key": x.get("key", x.get("name", "")), "value": str(x.get("value", x.get("val", ""))),
             "enabled": x.get("enabled", True), "type": "default"}
            for x in (vars_ or []) if isinstance(x, dict)]


def _merge_into_globals(ws, values):
    """Globals'ga qo'shadi; mavjud kalitlar o'zgarmaydi (idempotent). Qo'shilganlar sonini qaytaradi."""
    g = ws.get_globals()
    have = {v.get("key") for v in g["values"]}
    new = [v for v in values if v["key"] and v["key"] not in have]
    if new:
        g["values"] = g["values"] + new
        ws.save_globals(g)
    return len(new)


def import_localstorage(ws, db, dump):
    """`dump` — {kalit: matn} (localStorage nusxasi). localStorage'dan hech narsa O'CHIRILMAYDI (faqat o'qiladi).

    Idempotent: env'lar id bo'yicha, tarix yozuvlari mazmun xeshi bo'yicha, globals kalit bo'yicha.
    "Default" nomli env va eski yagona o'zgaruvchilar Globals'ga ko'chadi.
    """
    with ws.lock:
        raw_path = os.path.join(ws.root, "imports", f"localstorage-{time.strftime('%Y%m%d-%H%M%S')}.json")
        from .atomic import atomic_write_json
        atomic_write_json(raw_path, dump)             # xom nusxa — ma'lumot yo'qolmasligi uchun

        stats = {"environments": 0, "globals": 0, "history": 0, "run_history": 0, "url_history": 0,
                 "default_to_globals": False, "raw": raw_path}
        existing = {e["id"] for e in ws.list_environments()}

        for e in _as_list(dump.get("apiRunnerEnvs")):
            if not isinstance(e, dict):
                continue
            values = _kv(e.get("vars", e.get("variables", e.get("values", {}))))
            if str(e.get("name", "")).strip().lower() == "default":
                n = _merge_into_globals(ws, values)
                stats["globals"] += n
                stats["default_to_globals"] = True
                continue
            if not e.get("id") or e["id"] in existing:
                continue
            env = model.new_environment(e.get("name", "Environment"), e["id"], values)
            env["x-apirunner"] = {"source": "localstorage"}
            ws.save_environment(env)
            stats["environments"] += 1

        legacy_vars = _loads(dump.get("apiRunnerEnvVars"), {})
        if isinstance(legacy_vars, dict) and legacy_vars:
            stats["globals"] += _merge_into_globals(ws, _kv(legacy_vars))
            stats["default_to_globals"] = True

        active = dump.get("apiRunnerActiveEnvId")
        if active and any(e["id"] == active for e in ws.list_environments()):
            ws.update_meta(active_environment_id=active)
        if stats["default_to_globals"]:
            ws.update_meta(legacy_default_migrated=True)

        for kind, key, stat in (("request", "apiRunnerHistory", "history"),
                                ("run", "apiRunnerRunHistory", "run_history"),
                                ("url", "apiRunnerUrlHistory", "url_history")):
            for entry in _as_list(dump.get(key)):
                ts = entry.get("timestamp") if isinstance(entry, dict) else None
                if db.add_history(kind, entry, ts=(ts / 1000 if ts and ts > 1e11 else ts), source="localstorage", dedupe=True):
                    stats[stat] += 1
        return stats
