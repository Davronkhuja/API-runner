"""Ichki model -> Postman Collection v2.1 / environment / globals. Ichki kalitlar (`x-apirunner`) olib tashlanadi; tavsif `description` ga qaytadi."""
import copy
import time

from ..importers.common import parts_from_url, split_url
from ..storage import files as filestore
from ..storage import model

SCHEMA = model.POSTMAN_SCHEMA


def _url(u):
    u = copy.deepcopy(u or {})
    raw = u.get("raw", "")
    base, pairs = split_url(raw)
    for k in ("protocol", "host", "port", "path"):                       # raw — yagona manba; eskirgan qismlar qayta hisoblanadi
        u.pop(k, None)
    u.update(parts_from_url(raw))
    if "query" not in u and pairs:
        u["query"] = [{"key": k, "value": v} for k, v in pairs]
    return u


def _body(b):
    b = copy.deepcopy(b)
    if b.get("mode") == "formdata":
        for r in b.get("formdata") or []:
            if r.get("type") == "file":
                src = r.get("src")
                names = [(filestore.parse_ref(s) or (None, None, s))[2] for s in (src if isinstance(src, list) else [src] if src else [])]     # ichki havola → faqat fayl nomi
                r["src"] = [n for n in names if n] if len(names) != 1 else names[0]
    if b.get("mode") == "file" and isinstance(b.get("file"), dict):
        src = b["file"].get("src")
        if isinstance(src, str) and filestore.REF_RE.match(src):
            b["file"]["src"] = b["file"].get("name") or filestore.parse_ref(src)[2]
    return b


def _request(r):
    r = copy.deepcopy(r)
    r["url"] = _url(r.get("url"))
    if "body" in r:
        r["body"] = _body(r["body"])
    if not r.get("description"):
        r.pop("description", None)
    r.pop("x-apirunner", None)
    return r


def _clean_vars(vs, strip_secrets):
    out = []
    for v in vs or []:
        v = {k: x for k, x in v.items() if k not in ("current",)}
        v["type"] = "secret" if v.get("type") == "secret" else "string"
        if strip_secrets and v["type"] == "secret":
            v["value"] = ""
        out.append(v)
    return out


def _item(n, strip):
    out = {k: copy.deepcopy(v) for k, v in n.items() if k not in ("x-apirunner",)}
    ext = n.get("x-apirunner") or {}
    if model.is_folder(n):
        out["item"] = [_item(c, strip) for c in n["item"]]
        if ext.get("description"):
            out["description"] = ext["description"]
    else:
        out["request"] = _request(n.get("request") or {})
        out["response"] = [_example(e) for e in n.get("response") or []]
    if out.get("variable"):
        out["variable"] = _clean_vars(out["variable"], strip)
    for k in ("auth", "event", "variable"):
        if k in out and not out[k]:
            out.pop(k)
    return out


def _example(e):
    e = {k: copy.deepcopy(v) for k, v in e.items() if k != "id"}
    if "originalRequest" in e:
        e["originalRequest"] = _request(e["originalRequest"])
    e.setdefault("cookie", [])
    return e


def export_collection(col, strip_secrets=True):
    """Postman v2.1 (dict)."""
    info = {"_postman_id": model.collection_id(col), "name": col["info"]["name"], "schema": SCHEMA}
    if col["info"].get("version"):
        info["version"] = col["info"]["version"]
    desc = (col.get("x-apirunner") or {}).get("description")
    if desc:
        info["description"] = desc
    out = {"info": info, "item": [_item(n, strip_secrets) for n in col.get("item") or []]}
    if col.get("auth"):
        out["auth"] = copy.deepcopy(col["auth"])
    if col.get("event"):
        out["event"] = copy.deepcopy(col["event"])
    if col.get("variable"):
        out["variable"] = _clean_vars(col["variable"], strip_secrets)
    for k, v in col.items():
        if k not in ("info", "item", "auth", "event", "variable", "x-apirunner"):
            out[k] = copy.deepcopy(v)
    return out


def _stamp():
    from .. import __version__
    return {"_postman_exported_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()), "_postman_exported_using": f"API Runner/{__version__}"}


def _env_values(values):
    """Faqat Initial qiymat (`value`); Current (`current`) ketmaydi; secret'lar bo'sh."""
    out = []
    for v in values or []:
        if not v.get("key"):
            continue
        secret = v.get("type") == "secret"
        out.append({"key": v["key"], "value": "" if secret else (v.get("value") or ""), "type": "secret" if secret else "default", "enabled": v.get("enabled", True) is not False})
    return out


def export_environment(env):
    return {"id": env.get("id") or model.new_id(), "name": env.get("name", ""), "values": _env_values(env.get("values")), "_postman_variable_scope": "environment", **_stamp()}


def export_globals(g):
    return {"id": model.new_id(), "name": "Globals", "values": _env_values(g.get("values") if isinstance(g, dict) else g), "_postman_variable_scope": "globals", **_stamp()}
