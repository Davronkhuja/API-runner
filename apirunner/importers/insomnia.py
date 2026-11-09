"""Insomnia v4 eksporti (`_type: export`, `__export_format: 4`) -> collection(lar) + muhitlar.

Workspace -> collection; request_group -> papka; request -> so'rov; Base environment -> collection o'zgaruvchilari,
sub-environment -> alohida muhit. `{{ _.nom }}` -> `{{nom}}`.
"""
import json
import re

from ..storage import model
from .common import ImportErr

TAG = re.compile(r"\{\{\s*_\.([\w.\-]+)\s*\}\}")


def looks_like_insomnia(doc):
    return isinstance(doc, dict) and doc.get("_type") == "export" and isinstance(doc.get("resources"), list)


def _t(s, warn=None):
    if not isinstance(s, str):
        return s
    out = TAG.sub(lambda m: "{{" + m.group(1) + "}}", s)
    if warn is not None and re.search(r"\{%.*?%\}", out):
        warn.append("Insomnia shablon teglari ({% ... %}) qo'llab-quvvatlanmaydi — matnda qoldi")
    return out


def _flat(data, prefix=""):
    out = []
    for k, v in (data or {}).items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and v:
            out += _flat(v, key + ".")
        else:
            out.append((key, v if isinstance(v, str) else json.dumps(v) if isinstance(v, (dict, list)) else str(v).lower() if isinstance(v, bool) else "" if v is None else str(v)))
    return out


def _auth(a, warn):
    if not isinstance(a, dict) or not a.get("type") or a.get("disabled"):
        return None
    t = a["type"]
    if t == "bearer":
        return {"type": "bearer", "bearer": [{"key": "token", "value": _t(a.get("token", "")), "type": "string"}]}
    if t == "basic":
        return {"type": "basic", "basic": [{"key": "username", "value": _t(a.get("username", "")), "type": "string"}, {"key": "password", "value": _t(a.get("password", "")), "type": "string"}]}
    if t == "digest":
        return {"type": "digest", "digest": [{"key": "username", "value": _t(a.get("username", "")), "type": "string"}, {"key": "password", "value": _t(a.get("password", "")), "type": "string"}]}
    if t == "apikey":
        return {"type": "apikey", "apikey": [{"key": "key", "value": _t(a.get("key", "")), "type": "string"}, {"key": "value", "value": _t(a.get("value", "")), "type": "string"},
                                              {"key": "in", "value": "query" if a.get("addTo") == "queryParams" else "header", "type": "string"}]}
    if t == "oauth2":
        grant = a.get("grantType", "client_credentials")
        rows = {"grant_type": grant if grant != "authorization_code" else "authorization_code", "accessTokenUrl": _t(a.get("accessTokenUrl", "")), "authUrl": _t(a.get("authorizationUrl", "")),
                "clientId": _t(a.get("clientId", "")), "clientSecret": _t(a.get("clientSecret", "")), "scope": a.get("scope", ""), "client_authentication": "header", "addTokenTo": "header", "headerPrefix": "Bearer", "tokenName": "Token"}
        return {"type": "oauth2", "oauth2": [{"key": k, "value": v, "type": "string"} for k, v in rows.items() if v != ""]}
    warn.append(f"Insomnia auth turi qo'llab-quvvatlanmaydi: {t}")
    return None


def _request(r, warn):
    headers = [{"key": _t(h.get("name", "")), "value": _t(h.get("value", "")), **({"disabled": True} if h.get("disabled") else {})} for h in r.get("headers") or [] if h.get("name")]
    query = [{"key": _t(p.get("name", "")), "value": _t(p.get("value", "")), **({"disabled": True} if p.get("disabled") else {})} for p in r.get("parameters") or [] if p.get("name")]
    url = _t(r.get("url", ""), warn)
    raw = url + ("" if "?" in url or not [q for q in query if not q.get("disabled")] else "?" + "&".join(f"{q['key']}={q['value']}" for q in query if not q.get("disabled")))
    req = {"method": (r.get("method") or "GET").upper(), "header": headers, "url": {"raw": raw}}
    if query:
        req["url"]["query"] = query
    body = r.get("body") or {}
    mt = (body.get("mimeType") or "").lower()
    if mt == "application/x-www-form-urlencoded" and body.get("params"):
        req["body"] = {"mode": "urlencoded", "urlencoded": [{"key": _t(p.get("name", "")), "value": _t(p.get("value", "")), **({"disabled": True} if p.get("disabled") else {})} for p in body["params"]]}
    elif mt == "multipart/form-data" and body.get("params"):
        req["body"] = {"mode": "formdata", "formdata": [{"key": _t(p.get("name", "")), "type": "file", "src": []} if p.get("type") == "file" else {"key": _t(p.get("name", "")), "value": _t(p.get("value", "")), "type": "text"} for p in body["params"]]}
    elif mt == "application/graphql" and body.get("text"):
        try:
            g = json.loads(body["text"])
            req["body"] = {"mode": "graphql", "graphql": {"query": g.get("query", ""), "variables": json.dumps(g.get("variables")) if g.get("variables") else ""}}
        except json.JSONDecodeError:
            req["body"] = {"mode": "raw", "raw": _t(body["text"]), "options": {"raw": {"language": "text"}}}
    elif body.get("text"):
        req["body"] = {"mode": "raw", "raw": _t(body["text"], warn), "options": {"raw": {"language": "json" if "json" in mt else "xml" if "xml" in mt else "text"}}}
    a = _auth(r.get("authentication"), warn)
    if a:
        req["auth"] = a
    if r.get("description"):
        req["description"] = r["description"]
    return req


def import_insomnia(doc, warnings=None):
    """Qaytaradi: ([collection...], [environment...])."""
    warn = warnings if warnings is not None else []
    if not looks_like_insomnia(doc):
        raise ImportErr("Insomnia eksporti emas")
    res = [r for r in doc["resources"] if isinstance(r, dict)]
    by_parent = {}
    for r in res:
        by_parent.setdefault(r.get("parentId"), []).append(r)
    for lst in by_parent.values():
        lst.sort(key=lambda x: (x.get("metaSortKey") or 0, x.get("name") or ""))
    workspaces = [r for r in res if r.get("_type") == "workspace"]
    if not workspaces:
        raise ImportErr("Insomnia eksportida workspace yo'q")

    def build(parent):
        out = []
        for r in by_parent.get(parent, []):
            t = r.get("_type")
            if t == "request_group":
                f = model.new_folder(r.get("name") or "Papka")
                if r.get("description"):
                    f["x-apirunner"]["description"] = r["description"]
                f["item"] = build(r["_id"])
                out.append(f)
            elif t == "request":
                out.append({"id": model.new_id(), "name": r.get("name") or "So'rov", "request": _request(r, warn), "response": []})
        return out
    cols, envs = [], []
    for w in workspaces:
        col = model.new_collection(w.get("name") or "Insomnia")
        col["x-apirunner"]["source"] = {"kind": "insomnia"}
        if w.get("description"):
            col["x-apirunner"]["description"] = w["description"]
        col["item"] = build(w["_id"])
        for e in by_parent.get(w["_id"], []):
            if e.get("_type") == "environment":
                col["variable"] = [{"key": k, "value": _t(v), "type": "default"} for k, v in _flat(e.get("data"))]
                for sub in by_parent.get(e["_id"], []):
                    if sub.get("_type") == "environment":
                        envs.append(model.new_environment(f"{w.get('name') or 'Insomnia'} · {sub.get('name') or 'Env'}", values=[{"key": k, "value": _t(v), "enabled": True, "type": "default"} for k, v in _flat(sub.get("data"))]))
        cols.append(col)
    return cols, envs
