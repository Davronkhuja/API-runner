"""Ichki ma'lumot modeli — Postman Collection v2.1 ning superseti.

Workspace → Collection → (ichma-ich) Folder → Request (+ Examples), Environment, Globals.
Qo'shimcha maydonlar `x-apirunner` kaliti ostida (Postman ularni e'tiborsiz qoldiradi).
"""
import uuid

POSTMAN_SCHEMA = "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
MODEL_VERSION = 1


def new_id():
    return str(uuid.uuid4())


def new_collection(name, cid=None):
    cid = cid or new_id()
    return {
        "info": {"_postman_id": cid, "name": name, "schema": POSTMAN_SCHEMA},
        "item": [],
        "auth": None,
        "variable": [],
        "event": [],
        "x-apirunner": {"version": MODEL_VERSION, "description": ""},
    }


def collection_id(col):
    return col["info"]["_postman_id"]


def new_folder(name, fid=None, expanded=True, legacy=None):
    ext = {"expanded": expanded}
    if legacy is not None:
        ext["legacy"] = legacy
    return {"id": fid or new_id(), "name": name, "item": [], "x-apirunner": ext}


def is_folder(item):
    return "item" in item


def new_environment(name, eid=None, values=None):
    return {"id": eid or new_id(), "name": name, "values": values or [],
            "_postman_variable_scope": "environment"}


def new_globals(values=None):
    return {"values": values or [], "_postman_variable_scope": "globals"}


# ── Eski (legacy) so'rov formati <-> Postman so'rovi ───────────────────────
# Eski UI shu formatda ishlaydi: {id,name,url,method,params,headers,body,body_type,
# content_type,authorization,folder_id,...}. To'liq nusxa `x-apirunner.legacy` da
# saqlanadi (yo'qotishsiz), Postman maydonlari esa undan hosil qilinadi.

def legacy_to_request_item(legacy):
    headers = [{"key": h.get("name", ""), "value": h.get("value", "")}
               for h in legacy.get("headers", []) if h.get("name")]
    auth = (legacy.get("authorization") or "").strip()
    req = {"method": legacy.get("method", "GET"),
           "header": headers,
           "url": {"raw": legacy.get("url", ""),
                   "query": [{"key": p.get("name", ""), "value": p.get("value", "")}
                             for p in legacy.get("params", []) if p.get("name")]}}
    if auth.lower().startswith("bearer "):
        req["auth"] = {"type": "bearer", "bearer": [{"key": "token", "value": auth[7:]}]}
    elif auth:
        req["header"].append({"key": "Authorization", "value": auth})
    bt = legacy.get("body_type", "raw")
    if bt == "multipart":
        req["body"] = {"mode": "formdata", "formdata": [
            {"key": f.get("name", ""), "value": f.get("value", ""), "type": "text"}
            for f in legacy.get("multipart_fields", [])]}
    elif legacy.get("body"):
        req["body"] = {"mode": "raw", "raw": legacy["body"],
                       "options": {"raw": {"language": "json" if bt == "json" else "text"}}}
    return {
        "id": legacy["id"],
        "name": legacy.get("name", ""),
        "request": req,
        "response": [],                       # Examples
        "x-apirunner": {"legacy": legacy},
    }


def request_item_to_legacy(item, folder_id=None):
    legacy = dict(item.get("x-apirunner", {}).get("legacy") or {})
    legacy["id"] = item["id"]
    if folder_id is not None or "folder_id" in legacy:   # asl yozuvdagi kalitlar aynan saqlanadi
        legacy["folder_id"] = folder_id
    return legacy


def iter_requests(items, folder_id=None):
    """Daraxtni tekislab (item, ota_papka_id) juftliklarini beradi."""
    for it in items:
        if is_folder(it):
            yield from iter_requests(it["item"], it["id"])
        else:
            yield it, folder_id
