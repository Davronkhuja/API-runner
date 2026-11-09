"""OpenAPI 3.x / Swagger 2.0 (JSON/YAML) -> collection.

Papkalar — birinchi tag bo'yicha; `{{baseUrl}}` collection o'zgaruvchisi serverdan; path parametrlari `:id` (+ `url.variable`);
so'rov body'si misol yoki sxemadan hosil qilinadi; javoblar Example'larga; xavfsizlik sxemalari collection/so'rov auth'iga.
Faqat lokal `$ref` (#/...) yechiladi.
"""
import json
import re

from ..storage import model
from .common import ImportErr

METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
MAX_DEPTH = 6


def looks_like_openapi(doc):
    return isinstance(doc, dict) and ("openapi" in doc or "swagger" in doc) and isinstance(doc.get("paths"), dict)


class Resolver:
    def __init__(self, doc, warn):
        self.doc, self.warn, self._bad = doc, warn, set()

    def ref(self, node, _seen=()):
        while isinstance(node, dict) and "$ref" in node:
            r = node["$ref"]
            if not isinstance(r, str) or not r.startswith("#/"):
                if r not in self._bad:
                    self._bad.add(r)
                    self.warn.append(f"Tashqi/noto'g'ri $ref yechilmadi: {r}")
                return {}
            if r in _seen:
                return {}                                           # aylanma havola
            cur = self.doc
            for part in r[2:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                cur = cur.get(part) if isinstance(cur, dict) else None
                if cur is None:
                    self.warn.append(f"$ref topilmadi: {r}")
                    return {}
            _seen = _seen + (r,)
            node = cur
        return node if isinstance(node, dict) else {}

    def example(self, schema, depth=0):
        s = self.ref(schema)
        if depth > MAX_DEPTH or not s:
            return None
        for k in ("example", "default"):
            if k in s:
                return s[k]
        if s.get("enum"):
            return s["enum"][0]
        for k in ("oneOf", "anyOf"):
            if s.get(k):
                return self.example(s[k][0], depth + 1)
        if s.get("allOf"):
            merged = {}
            for sub in s["allOf"]:
                v = self.example(sub, depth + 1)
                if isinstance(v, dict):
                    merged.update(v)
            return merged
        t = s.get("type") or ("object" if s.get("properties") else None)
        if t == "object":
            return {k: self.example(v, depth + 1) for k, v in (s.get("properties") or {}).items()}
        if t == "array":
            v = self.example(s.get("items") or {}, depth + 1)
            return [] if v is None else [v]
        if t == "integer":
            return s.get("minimum", 0)
        if t == "number":
            return s.get("minimum", 0)
        if t == "boolean":
            return True
        if t == "string" or t is None:
            f = s.get("format")
            return {"date-time": "2024-01-01T00:00:00Z", "date": "2024-01-01", "uuid": "00000000-0000-0000-0000-000000000000", "email": "user@example.com",
                    "uri": "https://example.com", "binary": "", "byte": ""}.get(f, "string" if t else None)
        return None


def _server(doc, warn):
    if doc.get("servers"):
        srv = doc["servers"][0]
        url = srv.get("url", "")
        for k, v in (srv.get("variables") or {}).items():
            url = url.replace("{" + k + "}", str(v.get("default", "")))
        if len(doc["servers"]) > 1:
            warn.append("Bir nechta server bor: birinchisi `baseUrl` ga olindi (" + ", ".join(s.get("url", "") for s in doc["servers"][1:4]) + ")")
        return url.rstrip("/")
    if doc.get("host"):
        scheme = (doc.get("schemes") or ["https"])[0]
        return f"{scheme}://{doc['host']}{doc.get('basePath', '')}".rstrip("/")
    warn.append("Server (servers/host) ko'rsatilmagan: `baseUrl` bo'sh")
    return ""


def _val(p, R):
    sch = R.ref(p.get("schema") or {})
    for src in (p, sch):
        for k in ("example", "default"):
            if k in src and src[k] is not None:
                v = src[k]
                return v if isinstance(v, str) else json.dumps(v) if isinstance(v, (dict, list)) else str(v).lower() if isinstance(v, bool) else str(v)
        if src.get("enum"):
            return str(src["enum"][0])
    return ""


def _body(op, ops_consumes, doc, R, params):
    """Qaytaradi (body, content_type) yoki (None, None)."""
    if "requestBody" in op:
        content = R.ref(op["requestBody"]).get("content") or {}
        order = [m for m in content if m.lower().endswith("json")] + [m for m in content if m == "application/x-www-form-urlencoded"] + [m for m in content if m == "multipart/form-data"] + list(content)
        if not order:
            return None, None
        mt = order[0]
        spec = content[mt] or {}
        sch = R.ref(spec.get("schema") or {})
        if mt.lower().endswith("json") or mt in ("application/xml", "text/plain") or mt.startswith("text/"):
            if "example" in spec:
                ex = spec["example"]
            elif spec.get("examples"):
                ex = R.ref(next(iter(spec["examples"].values()))).get("value")
            else:
                ex = R.example(sch)
            raw = ex if isinstance(ex, str) else json.dumps(ex if ex is not None else {}, indent=2, ensure_ascii=False)
            lang = "json" if mt.lower().endswith("json") else "xml" if "xml" in mt else "text"
            return {"mode": "raw", "raw": raw, "options": {"raw": {"language": lang}}}, mt
        props = sch.get("properties") or {}
        if mt == "application/x-www-form-urlencoded":
            return {"mode": "urlencoded", "urlencoded": [{"key": k, "value": _val({"schema": v}, R)} for k, v in props.items()]}, mt
        if mt == "multipart/form-data":
            rows = []
            for k, v in props.items():
                v = R.ref(v)
                rows.append({"key": k, "type": "file", "src": []} if v.get("format") == "binary" or (v.get("type") == "array" and R.ref(v.get("items") or {}).get("format") == "binary")
                            else {"key": k, "value": _val({"schema": v}, R), "type": "text"})
            return {"mode": "formdata", "formdata": rows}, mt
        return {"mode": "raw", "raw": "", "options": {"raw": {"language": "text"}}}, mt
    # Swagger 2.0
    body_p = next((p for p in params if p.get("in") == "body"), None)
    form = [p for p in params if p.get("in") == "formData"]
    consumes = op.get("consumes") or ops_consumes or ["application/json"]
    if body_p:
        ex = R.example(body_p.get("schema") or {})
        return {"mode": "raw", "raw": json.dumps(ex if ex is not None else {}, indent=2, ensure_ascii=False), "options": {"raw": {"language": "json"}}}, consumes[0]
    if form:
        if "multipart/form-data" in consumes or any(p.get("type") == "file" for p in form):
            return {"mode": "formdata", "formdata": [{"key": p["name"], "type": "file", "src": []} if p.get("type") == "file" else {"key": p["name"], "value": _val(p, R), "type": "text"} for p in form]}, "multipart/form-data"
        return {"mode": "urlencoded", "urlencoded": [{"key": p["name"], "value": _val(p, R)} for p in form]}, "application/x-www-form-urlencoded"
    return None, None


def _schemes(doc):
    sec = (doc.get("components") or {}).get("securitySchemes") or doc.get("securityDefinitions") or {}
    return {k: v for k, v in sec.items() if isinstance(v, dict)}


def _auth_for(req_names, schemes, variables):
    """Birinchi qo'llab-quvvatlanadigan sxema bo'yicha Postman auth va kerakli o'zgaruvchilar."""
    for name in req_names:
        s = schemes.get(name) or {}
        t, scheme = s.get("type"), (s.get("scheme") or "").lower()
        if t == "http" and scheme == "bearer" or t == "oauth2" and False:
            variables.setdefault("token", "")
            return {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}]}
        if t == "http" and scheme == "basic" or t == "basic":
            variables.setdefault("username", ""); variables.setdefault("password", "")
            return {"type": "basic", "basic": [{"key": "username", "value": "{{username}}", "type": "string"}, {"key": "password", "value": "{{password}}", "type": "string"}]}
        if t == "apiKey":
            variables.setdefault("apiKey", "")
            return {"type": "apikey", "apikey": [{"key": "key", "value": s.get("name", "X-API-Key"), "type": "string"}, {"key": "value", "value": "{{apiKey}}", "type": "string"},
                                                  {"key": "in", "value": "query" if s.get("in") == "query" else "header", "type": "string"}]}
        if t == "oauth2":
            flows = s.get("flows") or {}
            flow_name = next((f for f in ("clientCredentials", "password", "authorizationCode", "implicit") if f in flows), None)
            f = flows.get(flow_name, {}) if flow_name else {"accessTokenUrl": s.get("tokenUrl", ""), "authorizationUrl": s.get("authorizationUrl", "")}
            grant = {"clientCredentials": "client_credentials", "password": "password", "authorizationCode": "authorization_code", "implicit": "implicit"}.get(flow_name) or \
                {"application": "client_credentials", "password": "password", "accessCode": "authorization_code", "implicit": "implicit"}.get(s.get("flow"), "client_credentials")
            variables.setdefault("clientId", ""); variables.setdefault("clientSecret", "")
            rows = {"grant_type": grant, "accessTokenUrl": f.get("tokenUrl") or f.get("accessTokenUrl", ""), "authUrl": f.get("authorizationUrl", ""), "clientId": "{{clientId}}", "clientSecret": "{{clientSecret}}",
                    "scope": " ".join((f.get("scopes") or s.get("scopes") or {}).keys()) if isinstance(f.get("scopes") or s.get("scopes") or {}, dict) else "", "client_authentication": "header", "addTokenTo": "header", "headerPrefix": "Bearer", "tokenName": "Token"}
            return {"type": "oauth2", "oauth2": [{"key": k, "value": v, "type": "string"} for k, v in rows.items() if v != ""]}
    return None


def _req_security(op, doc):
    """Operatsiya xavfsizligi: None = meros; [] = noauth; [names] = o'zi."""
    if "security" not in op:
        return None
    return [n for req in op["security"] for n in req] if op["security"] else []


def import_openapi(doc, warnings=None):
    warn = warnings if warnings is not None else []
    if not looks_like_openapi(doc):
        raise ImportErr("OpenAPI/Swagger hujjati emas (openapi/swagger va paths kerak)")
    R = Resolver(doc, warn)
    info = doc.get("info") or {}
    col = model.new_collection(info.get("title") or "OpenAPI")
    if info.get("version"):
        col["info"]["version"] = str(info["version"])
    if info.get("description"):
        col["x-apirunner"]["description"] = str(info["description"])
    col["x-apirunner"]["source"] = {"kind": "openapi", "version": str(doc.get("openapi") or doc.get("swagger"))}
    base = _server(doc, warn)
    variables = {"baseUrl": base}
    schemes = _schemes(doc)
    global_sec = [n for req in doc.get("security") or [] for n in req]
    col["auth"] = _auth_for(global_sec, schemes, variables)
    tag_desc = {t.get("name"): t.get("description", "") for t in doc.get("tags") or [] if isinstance(t, dict)}
    folders, used_names = {}, {}
    for path, ops in doc["paths"].items():
        ops = R.ref(ops)
        if not isinstance(ops, dict):
            continue
        for m in METHODS:
            op = ops.get(m)
            if not isinstance(op, dict):
                continue
            params = [R.ref(p) for p in (ops.get("parameters") or []) + (op.get("parameters") or [])]
            seen_p, plist = set(), []
            for p in reversed(params):                                            # operatsiya parametri path-darajadagidan ustun
                key = (p.get("in"), p.get("name"))
                if key not in seen_p and p.get("name"):
                    seen_p.add(key)
                    plist.append(p)
            plist.reverse()
            query = [{"key": p["name"], "value": _val(p, R), **({} if p.get("required") else {"disabled": True}), **({"description": p["description"]} if p.get("description") else {})} for p in plist if p.get("in") == "query"]
            headers = [{"key": p["name"], "value": _val(p, R)} for p in plist if p.get("in") == "header"]
            pvars = [{"key": p["name"], "value": _val(p, R) or "1", **({"description": p["description"]} if p.get("description") else {})} for p in plist if p.get("in") == "path"]
            full = "{{baseUrl}}" + re.sub(r"\{([^}/]+)\}", r":\1", path)
            raw = full + ("?" + "&".join(f"{q['key']}={q['value']}" for q in query if not q.get("disabled")) if any(not q.get("disabled") for q in query) else "")
            url = {"raw": raw}
            if query:
                url["query"] = query
            if pvars:
                url["variable"] = pvars
            req = {"method": m.upper(), "header": headers, "url": url}
            desc = "\n\n".join(x for x in (op.get("summary"), op.get("description")) if x)
            if op.get("deprecated"):
                desc = "**Deprecated.**\n\n" + desc
            if desc:
                req["description"] = desc
            body, ctype = _body(op, doc.get("consumes"), doc, R, plist)
            if body:
                req["body"] = body
                if ctype and not ctype.lower().endswith("json") and ctype != "multipart/form-data" and ctype != "application/x-www-form-urlencoded":
                    req["header"] = headers + [{"key": "Content-Type", "value": ctype}]
            sec = _req_security(op, doc)
            if sec is not None:
                req["auth"] = _auth_for(sec, schemes, variables) if sec else {"type": "noauth"}
            name = op.get("summary") or op.get("operationId") or f"{m.upper()} {path}"
            item = {"id": model.new_id(), "name": name, "request": req, "response": []}
            for code, resp in (op.get("responses") or {}).items():
                resp = R.ref(resp)
                if not re.match(r"^\d{3}$", str(code)):
                    continue
                content = resp.get("content") or {}
                if content:
                    mt = next((x for x in content if x.lower().endswith("json")), next(iter(content)))
                    spec = content[mt] or {}
                    ex = spec.get("example") if "example" in spec else (R.ref(next(iter(spec["examples"].values()))).get("value") if spec.get("examples") else R.example(spec.get("schema") or {}))
                elif resp.get("schema"):                                           # Swagger 2.0
                    mt, ex = "application/json", R.example(resp["schema"])
                else:
                    mt, ex = None, None
                bodytxt = "" if ex is None else (ex if isinstance(ex, str) else json.dumps(ex, indent=2, ensure_ascii=False))
                item["response"].append({"id": "ex" + model.new_id()[:12], "name": f"{code} {resp.get('description', '')}".strip()[:80], "originalRequest": json.loads(json.dumps(req)), "status": resp.get("description") or str(code), "code": int(code),
                                         "header": [{"key": "Content-Type", "value": mt}] if mt else [], "body": bodytxt, "_postman_previewlanguage": "json" if mt and mt.lower().endswith("json") else "text"})
            tags = op.get("tags") or []
            if tags:
                t = str(tags[0])
                if t not in folders:
                    folders[t] = model.new_folder(t)
                    if tag_desc.get(t):
                        folders[t]["x-apirunner"]["description"] = tag_desc[t]
                    col["item"].append(folders[t])
                folders[t]["item"].append(item)
            else:
                col["item"].append(item)
    col["variable"] = [{"key": k, "value": v, "type": "default"} for k, v in variables.items()]
    return col
