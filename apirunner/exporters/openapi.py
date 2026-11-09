"""Ichki model -> OpenAPI 3.0.3 (asosiy): yo'llar, parametrlar, body sxemalari (JSON'dan), javoblar (Example'lardan), xavfsizlik sxemalari."""
import json
import re
from urllib.parse import urlsplit

import yaml

from ..importers.common import slug, split_url
from ..storage import model

SKIP_HEADERS = {"content-type", "accept", "authorization", "content-length", "host", "user-agent"}
VAR = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def infer_schema(v, depth=0):
    if depth > 6:
        return {}
    if isinstance(v, bool):
        return {"type": "boolean"}
    if isinstance(v, int):
        return {"type": "integer"}
    if isinstance(v, float):
        return {"type": "number"}
    if isinstance(v, str):
        return {"type": "string"}
    if isinstance(v, list):
        return {"type": "array", "items": infer_schema(v[0], depth + 1) if v else {}}
    if isinstance(v, dict):
        return {"type": "object", "properties": {k: infer_schema(x, depth + 1) for k, x in v.items()}}
    return {}


def _json(text):
    try:
        return json.loads(text), True
    except (TypeError, ValueError):
        return text, False


def _origin_and_path(raw, variables):
    """`raw` URL -> (server | None, '/path/{param}', [path param names])."""
    base, _ = split_url(raw)
    m = re.match(r"^\{\{\s*([^}]+?)\s*\}\}(/.*)?$", base)
    if m:
        srv = (variables.get(m.group(1)) or "").rstrip("/")
        path = m.group(2) or "/"
    else:
        u = urlsplit(base if "://" in base else "http://" + base) if re.match(r"^[\w.-]+(:\d+)?(/|$)", base) or "://" in base else None
        if u and u.netloc and "://" in base:
            srv, path = f"{u.scheme}://{u.netloc}", u.path or "/"
        else:
            srv, path = None, base if base.startswith("/") else "/" + base
    params = []

    def conv(mm):
        params.append(mm.group(1))
        return "{" + mm.group(1) + "}"
    path = re.sub(r":([A-Za-z_][\w-]*)", conv, path)
    path = re.sub(r"\{\{\s*([^}]+?)\s*\}\}", conv, path)
    return srv, path or "/", params


def _auth_scheme(a):
    """Postman auth -> (nom, OAS sxemasi) yoki None."""
    if not isinstance(a, dict):
        return None
    t = a.get("type")
    vals = {r.get("key"): r.get("value") for r in a.get(t) or [] if isinstance(r, dict)} if isinstance(a.get(t), list) else {}
    if t == "bearer":
        return "bearerAuth", {"type": "http", "scheme": "bearer"}
    if t == "basic":
        return "basicAuth", {"type": "http", "scheme": "basic"}
    if t == "digest":
        return "digestAuth", {"type": "http", "scheme": "digest"}
    if t == "apikey":
        return "apiKeyAuth", {"type": "apiKey", "name": vals.get("key") or "X-API-Key", "in": "query" if vals.get("in") == "query" else "header"}
    if t == "oauth2":
        grant = vals.get("grant_type", "client_credentials")
        scopes = {s: "" for s in (vals.get("scope") or "").split() if s}
        if grant in ("authorization_code", "authorization_code_pkce"):
            flow = {"authorizationCode": {"authorizationUrl": vals.get("authUrl") or "", "tokenUrl": vals.get("accessTokenUrl") or "", "scopes": scopes}}
        elif grant == "implicit":
            flow = {"implicit": {"authorizationUrl": vals.get("authUrl") or "", "scopes": scopes}}
        elif grant == "password":
            flow = {"password": {"tokenUrl": vals.get("accessTokenUrl") or "", "scopes": scopes}}
        else:
            flow = {"clientCredentials": {"tokenUrl": vals.get("accessTokenUrl") or "", "scopes": scopes}}
        return "oauth2Auth", {"type": "oauth2", "flows": flow}
    return None


def _walk(items, trail=()):
    for it in items or []:
        if model.is_folder(it):
            yield from _walk(it["item"], trail + (it["name"],))
        else:
            yield it, trail


def export_openapi(col):
    """OpenAPI 3.0.3 (dict)."""
    variables = {v["key"]: v.get("value", "") for v in col.get("variable") or [] if v.get("key")}
    info = {"title": col["info"]["name"], "version": col["info"].get("version") or "1.0.0"}
    desc = (col.get("x-apirunner") or {}).get("description")
    if desc:
        info["description"] = desc
    doc = {"openapi": "3.0.3", "info": info, "paths": {}}
    servers, schemes, skipped, used_ops = [], {}, [], set()
    tags_seen = []
    root = _auth_scheme(col.get("auth"))
    if root:
        schemes[root[0]] = root[1]
        doc["security"] = [{root[0]: []}]
    for it, trail in _walk(col.get("item")):
        r = it.get("request") or {}
        url = (r.get("url") or {}).get("raw", "") if isinstance(r.get("url"), dict) else str(r.get("url") or "")
        srv, path, pnames = _origin_and_path(url, variables)
        if srv and srv not in servers:
            servers.append(srv)
        method = (r.get("method") or "GET").lower()
        if method not in ("get", "put", "post", "delete", "patch", "head", "options", "trace"):
            skipped.append(it["name"]); continue
        pitem = doc["paths"].setdefault(path, {})
        if method in pitem:
            skipped.append(it["name"]); continue
        op = {"summary": it["name"]}
        d = r.get("description")
        if d:
            op["description"] = d if isinstance(d, str) else d.get("content", "")
        if trail:
            op["tags"] = [trail[0]]
            if trail[0] not in tags_seen:
                tags_seen.append(trail[0])
        base_id = slug(it["name"], method)
        oid, n = base_id, 2
        while oid in used_ops:
            oid, n = f"{base_id}_{n}", n + 1
        used_ops.add(oid)
        op["operationId"] = oid
        params = []
        pvars = {v.get("key"): v.get("value") for v in (r.get("url") or {}).get("variable") or [] if isinstance(v, dict)}
        for p in pnames:
            ex = pvars.get(p)
            params.append({"name": p, "in": "path", "required": True, "schema": {"type": "string"}, **({"example": ex} if ex else {})})
        for q in (r.get("url") or {}).get("query") or []:
            if isinstance(q, dict) and q.get("key"):
                params.append({"name": q["key"], "in": "query", "required": not q.get("disabled"), "schema": {"type": "string"}, **({"example": q["value"]} if q.get("value") else {}), **({"description": q["description"]} if q.get("description") else {})})
        for h in r.get("header") or []:
            if isinstance(h, dict) and h.get("key") and h["key"].lower() not in SKIP_HEADERS and not h.get("disabled"):
                params.append({"name": h["key"], "in": "header", "schema": {"type": "string"}, **({"example": h["value"]} if h.get("value") else {})})
        if params:
            op["parameters"] = params
        b = r.get("body") or {}
        mode = b.get("mode")
        if mode == "raw":
            lang = ((b.get("options") or {}).get("raw") or {}).get("language", "text")
            val, ok = _json(b.get("raw") or "")
            if lang == "json" or ok and isinstance(val, (dict, list)):
                op["requestBody"] = {"content": {"application/json": {"schema": infer_schema(val) if ok else {"type": "object"}, **({"example": val} if ok else {})}}}
            else:
                op["requestBody"] = {"content": {"application/xml" if lang == "xml" else "text/plain": {"schema": {"type": "string"}, "example": b.get("raw", "")}}}
        elif mode == "urlencoded":
            rows = [x for x in b.get("urlencoded") or [] if x.get("key")]
            op["requestBody"] = {"content": {"application/x-www-form-urlencoded": {"schema": {"type": "object", "properties": {x["key"]: {"type": "string"} for x in rows}}}}}
        elif mode == "formdata":
            props = {x["key"]: ({"type": "string", "format": "binary"} if x.get("type") == "file" else {"type": "string"}) for x in b.get("formdata") or [] if x.get("key")}
            op["requestBody"] = {"content": {"multipart/form-data": {"schema": {"type": "object", "properties": props}}}}
        elif mode == "graphql":
            g = b.get("graphql") or {}
            op["requestBody"] = {"content": {"application/json": {"schema": {"type": "object", "properties": {"query": {"type": "string"}, "variables": {"type": "object"}}}, "example": {"query": g.get("query", "")}}}}
        elif mode == "file":
            op["requestBody"] = {"content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}
        resp = {}
        for ex in it.get("response") or []:
            code = str(ex.get("code") or "")
            if not re.match(r"^\d{3}$", code) or code in resp:
                continue
            ct = next((h["value"] for h in ex.get("header") or [] if isinstance(h, dict) and h.get("key", "").lower() == "content-type"), "")
            entry = {"description": ex.get("status") if ex.get("status") and not ex["status"].isdigit() else ex.get("name") or code}
            if ex.get("body"):
                val, ok = _json(ex["body"])
                mt = (ct.split(";")[0].strip() or ("application/json" if ok and isinstance(val, (dict, list)) else "text/plain"))
                entry["content"] = {mt: {"schema": infer_schema(val) if ok and isinstance(val, (dict, list)) else {"type": "string"}, "example": val}}
            resp[code] = entry
        op["responses"] = resp or {"200": {"description": "OK"}}
        sch = _auth_scheme(r.get("auth")) if isinstance(r.get("auth"), dict) and r["auth"].get("type") != "noauth" else None
        if isinstance(r.get("auth"), dict) and r["auth"].get("type") == "noauth":
            op["security"] = []
        elif sch:
            schemes[sch[0]] = sch[1]
            op["security"] = [{sch[0]: []}]
        pitem[method] = op
    if servers:
        doc["servers"] = [{"url": s} for s in servers]
    if schemes:
        doc["components"] = {"securitySchemes": schemes}
    if tags_seen:
        doc["tags"] = [{"name": t} for t in tags_seen]
    if skipped:
        doc["x-skipped"] = skipped
    return doc


def to_text(doc, fmt="json"):
    if fmt == "yaml":
        return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=120)
    return json.dumps(doc, indent=2, ensure_ascii=False)
