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
        node = model.new_folder(f.get("name", ""), f["id"], f.get("expanded", True), legacy=f)
        folders[f["id"]] = node
        col["item"].append(node)
    for r in data.get("requests", []):
        if not r.get("id"):
            continue
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


def import_localstorage(ws, db, dump):
    """`dump` — {kalit: matn} (localStorage nusxasi). Bir xil id'li env qayta yozilmaydi (idempotent).

    Qaytaradi: import statistikasi.
    """
    # xom nusxa — ma'lumot yo'qolmasligi uchun
    raw_path = os.path.join(ws.root, "imports", f"localstorage-{time.strftime('%Y%m%d-%H%M%S')}.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(dump, f, ensure_ascii=False, indent=2)

    stats = {"environments": 0, "history": 0, "run_history": 0, "url_history": 0, "raw": raw_path}
    existing = {e["id"] for e in ws.list_environments()}

    # Nomlangan environment'lar: [{id,name,vars|variables|values}]
    for e in _as_list(dump.get("apiRunnerEnvs")):
        if not isinstance(e, dict) or not e.get("id") or e["id"] in existing:
            continue
        raw_vars = e.get("vars", e.get("variables", e.get("values", {})))
        if isinstance(raw_vars, dict):
            values = [{"key": k, "value": str(v), "enabled": True, "type": "default"}
                      for k, v in raw_vars.items()]
        else:
            values = [{"key": x.get("key", x.get("name", "")), "value": str(x.get("value", "")),
                       "enabled": x.get("enabled", True), "type": "default"}
                      for x in (raw_vars or []) if isinstance(x, dict)]
        env = model.new_environment(e.get("name", "Environment"), e["id"], values)
        env["x-apirunner"] = {"source": "localstorage"}
        ws.save_environment(env)
        stats["environments"] += 1

    # Eski yagona "global" env o'zgaruvchilari -> globals (bo'sh bo'lsa)
    legacy_vars = _loads(dump.get("apiRunnerEnvVars"), {})
    g = ws.get_globals()
    if isinstance(legacy_vars, dict) and legacy_vars and not g["values"]:
        g["values"] = [{"key": k, "value": str(v), "enabled": True, "type": "default"}
                       for k, v in legacy_vars.items()]
        ws.save_globals(g)

    active = dump.get("apiRunnerActiveEnvId")
    if active:
        ws.update_meta(active_environment_id=active)

    if db.count_history(source="localstorage") == 0:       # qayta bosilsa ikkilanmasin
        for kind, key, stat in (("request", "apiRunnerHistory", "history"),
                                ("run", "apiRunnerRunHistory", "run_history"),
                                ("url", "apiRunnerUrlHistory", "url_history")):
            for entry in _as_list(dump.get(key)):
                ts = entry.get("timestamp") if isinstance(entry, dict) else None
                db.add_history(kind, entry, ts=(ts / 1000 if ts and ts > 1e11 else ts), source="localstorage")
                stats[stat] += 1
    return stats
