"""Import natijasini workspace'ga qo'llash: nom to'qnashuvi (birlashtirish / yangi nusxa / almashtirish / o'tkazib yuborish).

Hech narsa jimgina yo'qolmaydi: almashtirilgan collection/muhit avval SAVATGA, globals almashtirishdan oldin zaxiraga olinadi.
"""
import copy
import hashlib
import os
import re

from . import files as filestore
from . import model, tree_ops
from .workspace import NotFound

ACTIONS = ("import", "copy", "replace", "merge", "skip")


def find_collection(ws, name):
    n = (name or "").strip().lower()
    return next((c for c in ws.list_collections() if c["name"].strip().lower() == n), None)


def find_environment(ws, name):
    n = (name or "").strip().lower()
    return next((e for e in ws.list_environments() if (e.get("name") or "").strip().lower() == n), None)


def free_name(taken, name):
    names = {t.strip().lower() for t in taken}
    if name.strip().lower() not in names:
        return name
    i = 2
    while f"{name} ({i})".lower() in names:
        i += 1
    return f"{name} ({i})"


# ── collection birlashtirish ──
def _count(items):
    f = r = 0
    for it in tree_ops_walk(items):
        if model.is_folder(it):
            f += 1
        else:
            r += 1
    return f, r


def tree_ops_walk(items):
    for it in items:
        yield it
        if model.is_folder(it):
            yield from tree_ops_walk(it["item"])


def _req_key(it):
    r = it.get("request") or {}
    url = r.get("url")
    return (it.get("name"), (r.get("method") or "GET").upper(), url.get("raw") if isinstance(url, dict) else url)


def merge_collection(existing, incoming):
    """`existing` joyida to'ldiriladi. Mos kelmaganlar qo'shiladi; mosi (papka: nomi, so'rov: nom+metod+URL) o'zgarmaydi."""
    res = {"added_folders": 0, "added_requests": 0, "skipped": 0, "added_variables": 0}

    def merge_items(dst, src):
        for it in src:
            if model.is_folder(it):
                hit = next((x for x in dst if model.is_folder(x) and x["name"] == it["name"]), None)
            else:
                hit = next((x for x in dst if not model.is_folder(x) and _req_key(x) == _req_key(it)), None)
            if hit is None:
                new = tree_ops.clone_with_new_ids(it)
                dst.append(new)
                f, r = _count([new])
                res["added_folders"] += f
                res["added_requests"] += r
            elif model.is_folder(it):
                merge_items(hit["item"], it["item"])
            else:
                res["skipped"] += 1
    merge_items(existing["item"], incoming.get("item") or [])
    have = {v.get("key") for v in existing.get("variable") or []}
    for v in incoming.get("variable") or []:
        if v.get("key") and v["key"] not in have:
            existing.setdefault("variable", []).append(copy.deepcopy(v))
            res["added_variables"] += 1
    for k in ("auth", "event"):
        if not existing.get(k) and incoming.get(k):
            existing[k] = copy.deepcopy(incoming[k])
    ext = existing.setdefault("x-apirunner", {})
    if not ext.get("description") and (incoming.get("x-apirunner") or {}).get("description"):
        ext["description"] = incoming["x-apirunner"]["description"]
    return res


def merge_values(existing_values, incoming_values):
    have = {v.get("key") for v in existing_values}
    added = 0
    for v in incoming_values:
        if v.get("key") and v["key"] not in have:
            existing_values.append(copy.deepcopy(v))
            added += 1
    return added


# ── oldindan ko'rish ──
def conflict_of(ws, item):
    """{id, name, merge: {...}|None} yoki None."""
    if item["type"] == "collection":
        ex = find_collection(ws, item["name"])
        if not ex:
            return None
        dry = merge_collection(copy.deepcopy(ws.get_collection(ex["id"])), item["ref"])
        return {"id": ex["id"], "name": ex["name"], "merge": dry}
    if item["type"] == "environment":
        ex = find_environment(ws, item["name"])
        if not ex:
            return None
        vals = copy.deepcopy(ex.get("values") or [])
        return {"id": ex["id"], "name": ex["name"], "merge": {"added_variables": merge_values(vals, item["ref"].get("values") or [])}}
    g = ws.get_globals().get("values") or []
    if not g:
        return None
    vals = copy.deepcopy(g)
    return {"id": "globals", "name": "Globals", "merge": {"added_variables": merge_values(vals, item["ref"])}}


# ── qo'llash ──
def apply_item(ws, item, action, backup=None):
    """Bitta elementni qo'llaydi. Qaytaradi: natija lug'ati."""
    if action not in ACTIONS:
        raise ValueError(f"Noma'lum amal: {action}")
    t, name, ref = item["type"], item["name"], item["ref"]
    res = {"type": t, "name": name, "action": action}
    if action == "skip":
        return res
    with ws.lock:
        if t == "collection":
            ex = find_collection(ws, name)
            col = ref
            if ex and action == "merge":
                cur = ws.get_collection(ex["id"])
                res.update(merge_collection(cur, col), id=ex["id"])
                ws.save_collection(cur)
                return res
            if ex and action == "replace":
                ws.trash.add_collection(ws.get_collection(ex["id"]))                         # eskisi savatda 30 kun
                col["info"]["_postman_id"] = ex["id"]
                res.update(id=ws.save_collection(col), replaced=ex["id"])
                return res
            if ex and action == "copy":
                col["info"]["name"] = free_name([c["name"] for c in ws.list_collections()], name)
                res["name"] = col["info"]["name"]
            if _id_taken_c(ws, model.collection_id(col)):
                col["info"]["_postman_id"] = model.new_id()
            res["id"] = ws.save_collection(col)
        elif t == "environment":
            ex = find_environment(ws, name)
            env = ref
            if ex and action == "merge":
                cur = ws.get_environment(ex["id"])
                res.update(added_variables=merge_values(cur.setdefault("values", []), env.get("values") or []), id=ex["id"])
                ws.save_environment(cur)
                return res
            if ex and action == "replace":
                ws.trash.add_environment(ws.get_environment(ex["id"]))
                env["id"] = ex["id"]
                res.update(id=ws.save_environment(env), replaced=ex["id"])
                return res
            if ex and action == "copy":
                env["name"] = free_name([e.get("name", "") for e in ws.list_environments()], name)
                res["name"] = env["name"]
            if _id_taken_e(ws, env["id"]):
                env["id"] = model.new_id()
            res["id"] = ws.save_environment(env)
        else:                                                                               # globals
            cur = ws.get_globals()
            if action == "replace":
                if backup:
                    res["backup"] = backup()
                cur["values"] = copy.deepcopy(ref)
            else:
                res["added_variables"] = merge_values(cur.setdefault("values", []), ref)
            ws.save_globals(cur)
    return res


def _id_taken_c(ws, cid):
    try:
        ws.get_collection(cid)
        return True
    except (NotFound, ValueError):
        return False


def _id_taken_e(ws, eid):
    try:
        ws.get_environment(eid)
        return True
    except (NotFound, ValueError):
        return False


def restore_files(ws, files):
    """Zip'dagi `files/<sha256>` obyektlarini (hash tekshirilib) tiklaydi; mavjudiga tegilmaydi. Qaytaradi: yozilgan soni."""
    n = 0
    for name, data in (files or {}).items():
        m = re.match(r"^files/([0-9a-f]{64})$", name)
        if not m or hashlib.sha256(data).hexdigest() != m.group(1):
            continue
        dest = os.path.join(filestore.files_dir(ws.root), m.group(1))
        if not os.path.exists(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(data)
            n += 1
    return n
