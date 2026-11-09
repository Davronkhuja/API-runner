"""Postman Collection v2.0/v2.1, environment va globals -> ichki model (v2.1 superseti).

Saqlanadi: ichma-ich papkalar, auth, event (skriptlar), variable, description, response (Example'lar), `protocolProfileBehavior` va boshqa noma'lum kalitlar.
Normallashtiriladi: v2.0 shakllari (url/header satr, auth obyekti), description obyekti -> matn, id'lar yagona, Example'larga id.
"""
import copy
import json
import time

from ..storage import model
from .common import ImportErr, ensure_unique_ids, parts_from_url, split_url


def looks_like_postman(doc):
    return isinstance(doc, dict) and isinstance(doc.get("item"), list) and isinstance(doc.get("info"), dict)


def _text(d):
    if isinstance(d, dict):
        return str(d.get("content") or "")
    return d if isinstance(d, str) else ""


def _auth(a):
    if not isinstance(a, dict) or not a.get("type"):
        return a
    a = copy.deepcopy(a)
    t = a["type"]
    v = a.get(t)
    if isinstance(v, dict):                                    # v2.0: {"bearer": {"token": "x"}}
        a[t] = [{"key": k, "value": x, "type": "string"} for k, x in v.items()]
    return a


def _kv_list(v, sep=":"):
    """header/query: satr ("A: b\\nC: d") yoki ro'yxat -> [{key,value,...}]."""
    if isinstance(v, str):
        out = []
        for line in v.splitlines():
            if sep in line:
                k, _, val = line.partition(sep)
                out.append({"key": k.strip(), "value": val.strip()})
        return out
    out = []
    for r in v or []:
        if isinstance(r, dict):
            r = dict(r)
            if r.get("value") is None and r.get("type") != "file":
                r["value"] = ""
            if "description" in r:
                r["description"] = _text(r["description"])
            out.append(r)
    return out


def _build_raw(u):
    host = u.get("host")
    host = ".".join(host) if isinstance(host, list) else (host or "")
    path = u.get("path")
    path = "/".join(str(p) if not isinstance(p, dict) else str(p.get("value", "")) for p in path) if isinstance(path, list) else (path or "")
    raw = (f"{u['protocol']}://" if u.get("protocol") and host else "") + host + (f":{u['port']}" if u.get("port") else "") + ("/" + path.lstrip("/") if path else "")
    q = [q for q in u.get("query") or [] if isinstance(q, dict) and not q.get("disabled")]
    if q:
        raw += "?" + "&".join(f"{x.get('key', '')}={x.get('value') or ''}" for x in q)
    return raw


def _url(u):
    if isinstance(u, str):
        return _url({"raw": u})
    if u is None:
        return {"raw": ""}
    u = copy.deepcopy(u)
    if not u.get("raw"):
        u["raw"] = _build_raw(u)
    if u.get("query"):
        u["query"] = _kv_list(u["query"], "=")
    elif "?" in u["raw"]:                                                         # query raw'dan hosil qilinadi (Params jadvali uchun)
        u["query"] = [{"key": k, "value": v} for k, v in split_url(u["raw"])[1]]
    if u.get("variable"):
        u["variable"] = _kv_list(u["variable"], "=")
    return u


def _body(b):
    if not isinstance(b, dict):
        return None
    b = copy.deepcopy(b)
    mode = b.get("mode")
    if mode in ("urlencoded", "formdata"):
        b[mode] = _kv_list(b.get(mode), "=")
    return b if mode else None


def _request(req):
    if isinstance(req, str):                                   # v2.0: "request": "http://..."
        return {"method": "GET", "header": [], "url": {"raw": req}}
    r = copy.deepcopy(req or {})
    r["url"] = _url(r.get("url"))
    r["method"] = (r.get("method") or "GET").upper()
    r["header"] = _kv_list(r.get("header"))
    if "description" in r:
        r["description"] = _text(r["description"])
    if "auth" in r:
        r["auth"] = _auth(r["auth"])
    if "body" in r:
        b = _body(r["body"])
        if b:
            r["body"] = b
        else:
            r.pop("body")
    return r


def _events(ev):
    out = []
    for e in ev or []:
        if not isinstance(e, dict) or "listen" not in e:
            continue
        e = copy.deepcopy(e)
        sc = e.get("script") or {}
        ex = sc.get("exec")
        if isinstance(ex, str):
            sc["exec"] = ex.split("\n")
        elif ex is None and not sc.get("src"):
            sc["exec"] = []
        sc.setdefault("type", "text/javascript")
        e["script"] = sc
        out.append(e)
    return out


def _variables(v):
    out = []
    for x in v or []:
        if not isinstance(x, dict):
            continue
        x = dict(x)
        if "key" not in x and "id" in x:
            x["key"] = x.pop("id")
        if x.get("value") is None:
            x["value"] = ""
        elif not isinstance(x["value"], str):
            x["value"] = json.dumps(x["value"]) if isinstance(x["value"], (dict, list)) else str(x["value"]).lower() if isinstance(x["value"], bool) else str(x["value"])
        if x.get("type") in (None, "any", "string"):
            x["type"] = "default"
        out.append(x)
    return out


def _example(ex):
    e = copy.deepcopy(ex)
    e.setdefault("id", "ex" + model.new_id()[:12])
    e["header"] = _kv_list(e.get("header"))
    body = e.get("body")
    if body is not None and not isinstance(body, str):
        e["body"] = json.dumps(body, indent=2)
    if "originalRequest" in e:
        e["originalRequest"] = _request(e["originalRequest"])
    e.setdefault("name", "Example")
    return e


def _walk(items, warn):
    out = []
    for it in items or []:
        n = copy.deepcopy(it)
        n.setdefault("name", "")
        desc = n.pop("description", None) if "item" in n else None
        if "item" in n:
            n["item"] = _walk(n["item"], warn)
            ext = n.setdefault("x-apirunner", {})
            if desc:
                ext["description"] = _text(desc)
        else:
            if "request" not in n:
                warn.append(f"«{n['name']}»: request yo'q — bo'sh so'rov sifatida olindi")
            n["request"] = _request(n.get("request"))
            n["response"] = [_example(x) for x in n.get("response") or [] if isinstance(x, dict)]
            if "description" in n:                                                   # (kam uchraydi) item.description -> request.description
                n["request"].setdefault("description", _text(n.pop("description")))
        if "auth" in n:
            n["auth"] = _auth(n["auth"])
        if "event" in n:
            n["event"] = _events(n["event"])
        if "variable" in n:
            n["variable"] = _variables(n["variable"])
        out.append(n)
    return out


def import_postman(doc, warnings=None):
    warn = warnings if warnings is not None else []
    if not looks_like_postman(doc):
        raise ImportErr("Postman collection emas (info va item kerak)")
    info = doc["info"]
    schema = str(info.get("schema", ""))
    if "v1" in schema or "/collection/v1" in schema:
        raise ImportErr("Postman Collection v1 qo'llab-quvvatlanmaydi (v2.0/v2.1 kerak)")
    col = model.new_collection(info.get("name") or "Import")
    if info.get("version"):
        col["info"]["version"] = info["version"]
    col["x-apirunner"]["source"] = {"kind": "postman", "id": info.get("_postman_id") or info.get("id"), "schema": schema or None}
    if doc.get("auth") is not None:
        col["auth"] = _auth(doc["auth"])
    col["variable"] = _variables(doc.get("variable"))
    col["event"] = _events(doc.get("event"))
    for k, v in doc.items():                                                      # noma'lum yuqori daraja kalitlari (protocolProfileBehavior ...)
        if k not in ("info", "item", "auth", "variable", "event"):
            col[k] = copy.deepcopy(v)
    desc = _text(info.get("description"))
    if desc:
        col["x-apirunner"]["description"] = desc
    col["item"] = ensure_unique_ids(_walk(doc.get("item"), warn))
    return col


def _values(doc):
    out, seen = [], set()
    for v in doc.get("values") or []:
        if not isinstance(v, dict) or not v.get("key") or v["key"] in seen:
            continue
        seen.add(v["key"])
        val = v.get("value")
        out.append({"key": v["key"], "value": "" if val is None else (val if isinstance(val, str) else json.dumps(val) if isinstance(val, (dict, list)) else str(val)),
                    "enabled": v.get("enabled", True) is not False, "type": "secret" if v.get("type") == "secret" else "default"})
    return out


def import_postman_env(doc):
    if not isinstance(doc, dict) or not isinstance(doc.get("values"), list):
        raise ImportErr("Postman environment emas")
    env = model.new_environment(doc.get("name") or "Import muhiti", values=_values(doc))
    return env


def import_postman_globals(doc):
    return _values(doc)


# ── tarkibni solishtirish uchun kanonik ko'rinish (round-trip testlari) ──
def _strip_url(r):
    return {**r, "url": {k: v for k, v in r["url"].items() if k not in ("protocol", "host", "port", "path")}}


def _canon_example(e):
    e = {k: v for k, v in e.items() if k != "id" and not (k == "cookie" and not v)}
    if "originalRequest" in e:
        e["originalRequest"] = _strip_url(e["originalRequest"])
    return e


def canonical(col):
    """Id'lar va vaqtinchalik maydonlarsiz, taqqoslash uchun barqaror ko'rinish."""
    def strip(n):
        n = {k: v for k, v in n.items() if k not in ("id", "x-apirunner")}
        if "request" in n:                                                    # url qismlari raw'dan hosil qilinadi; bo'sh tavsif — tavsifsiz
            n["request"] = {**n["request"], "url": {k: v for k, v in n["request"]["url"].items() if k not in ("protocol", "host", "port", "path")}}
            if not n["request"].get("description"):
                n["request"].pop("description", None)
        if "item" in n:
            n["item"] = [strip(x) for x in n["item"]]
        if "response" in n:
            n["response"] = [_canon_example(e) for e in n["response"]]
        return n
    c = {k: v for k, v in col.items() if k not in ("x-apirunner",)}
    c["info"] = {k: v for k, v in col["info"].items() if k != "_postman_id"}
    c["item"] = [strip(x) for x in col["item"]]
    c["description"] = col.get("x-apirunner", {}).get("description", "")
    return c


__all__ = ["import_postman", "import_postman_env", "import_postman_globals", "looks_like_postman", "canonical", "parts_from_url", "split_url", "time"]
