"""Skriptli bajarish: pre-request → so'rov → tests, o'zgaruvchi scope'lari (Global/Collection/Environment/Data/Local),
o'zgarishlarni workspace'ga YOZISH (skript emas, shu modul yozadi), pm.sendRequest (engine orqali).

`run_item()` — yagona kirish: `/run_one`, batch (`/run`) va kolleksiya oqimi (`flow.py`) shundan o'tadi.
"""
import base64
import http
import json
import re
import threading
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, unquote, urlsplit

from . import scripting
from .engine import ExecContext, execute
from .variables import replace_variables, resolve_form_body
from .scripting.sandbox import Limits, ScriptSession, ScriptSource

SCOPES = ("globals", "collection", "environment", "data", "local")


@dataclass
class Services:
    ws: object = None                    # Workspace (None: faqat xotirada, saqlanmaydi)
    cookies: object = None               # CookieStore | None
    allowed_file_roots: tuple = ()
    allowed_files: frozenset = frozenset()


def _phrase(code):
    try:
        return http.HTTPStatus(int(code)).phrase
    except (ValueError, TypeError):
        return ""


def _s(v):
    return v if isinstance(v, str) else (json.dumps(v) if isinstance(v, (dict, list)) else ("" if v is None else str(v)))


# ───────────────────────── scriptlar zanjiri ─────────────────────────
def _event_scripts(node, kind, scope, name, nid):
    out = []
    for ev in (node.get("event") or node.get("events") or []):
        if ev.get("listen") != kind:
            continue
        ex = (ev.get("script") or {}).get("exec")
        src = "\n".join(ex) if isinstance(ex, list) else (ex or "")
        if src.strip():
            out.append(ScriptSource(src, kind, scope, name, nid))
    return out


def find_path(items, item_id, trail=()):
    for it in items:
        if it.get("id") == item_id:
            return list(trail), it
        if "item" in it:
            r = find_path(it["item"], item_id, trail + (it,))
            if r:
                return r
    return None


def scripts_chain(col, item_id):
    """collection → papkalar (tashqaridan ichkariga) → so'rov. Postman tartibi."""
    path, item = find_path(col["item"], item_id) or ([], None)
    nodes = [("collection", col["info"]["name"], col["info"]["_postman_id"], col)] + [("folder", f["name"], f["id"], f) for f in path] + ([("request", item["name"], item["id"], item)] if item else [])
    return {k: [s for scope, name, nid, node in nodes for s in _event_scripts(node, k, scope, name, nid)] for k in ("prerequest", "test")}


# ───────────────────────── scope'lar ─────────────────────────
def effective(row):
    """Muhit/globals qatori: Joriy qiymat (faqat shu kompyuterda) bor bo'lsa u, aks holda Boshlang'ich (`value`)."""
    cur = row.get("current")
    return row.get("value", "") if cur is None else cur


def _vars_of(rows):
    return {r["key"]: effective(r) for r in (rows or []) if r.get("key") and not r.get("disabled") and r.get("enabled", True)}


def load_scopes(ws, ref, row=None):
    """Server tomonidagi haqiqiy holat: {scopes, env_id, env_name, active_env, cid}."""
    cid, _, iid = (ref or "").partition(":")
    scopes = {k: {} for k in SCOPES}
    env_id = env_name = None
    if ws is not None:
        scopes["globals"] = _vars_of(ws.get_globals().get("values"))
        env_id = ws.meta().get("active_environment_id")
        if env_id:
            try:
                env = ws.get_environment(env_id)
                scopes["environment"], env_name = _vars_of(env.get("values")), env.get("name")
            except Exception:       # noqa: BLE001 — o'chirilgan muhit
                env_id = None
        if cid:
            try:
                col = ws.get_collection(cid)
                scopes["collection"] = _vars_of(col.get("variable"))
                for f in (find_path(col["item"], iid) or ([], None))[0]:
                    scopes["collection"].update(_vars_of(f.get("variable")))
            except Exception:       # noqa: BLE001
                pass
    scopes["data"] = {k: v for k, v in (row or {}).items()}
    return scopes, env_id, env_name, bool(env_id)


def merged(scopes):
    out = {}
    for name in SCOPES:            # past → yuqori: globals < collection < environment < data < local
        out.update({k: _s(v) for k, v in scopes.get(name, {}).items()})
    return out


def persist(ws, ref, env_id, before, after, changed):
    """Skript o'zgartirgan scope'larni workspace'ga yozadi (atomik, workspace qulfi bilan). data/local saqlanmaydi."""
    if ws is None:
        return []
    written = []
    cid = (ref or "").partition(":")[0]
    with ws.lock:
        if changed.get("environment") and env_id:
            env = ws.get_environment(env_id)
            new = _apply(env.get("values", []), before["environment"], after["environment"], enabled_key="enabled")
            if new != env.get("values", []):                       # qiymat o'zgarmagan bo'lsa diskka yozilmaydi (rev ko'tarilmaydi)
                env["values"] = new
                ws.save_environment(env)
                written.append("environment")
        if changed.get("globals"):
            g = ws.get_globals()
            new = _apply(g.get("values", []), before["globals"], after["globals"], enabled_key="enabled")
            if new != g.get("values", []):
                g["values"] = new
                ws.save_globals(g)
                written.append("globals")
        if changed.get("collection") and cid:
            col = ws.get_collection(cid)
            new = _apply(col.get("variable", []), before["collection"], after["collection"], enabled_key=None)
            if new != col.get("variable", []):
                col["variable"] = new
                ws.save_collection(col)
                written.append("collection")
    return written


def _apply(rows, before, after, enabled_key):
    rows = [dict(r) for r in rows]
    for k, v in after.items():
        if k in before and _s(before[k]) == _s(v):
            continue
        hit = next((r for r in rows if r.get("key") == k), None)
        # muhit/globals (enabled_key bor): skript faqat JORIY qiymatni o'zgartiradi, Boshlang'ich tegilmaydi; collection — `value`
        field = "current" if enabled_key else "value"
        if hit:
            hit[field] = _s(v)
            if enabled_key:
                hit[enabled_key] = True
            hit.pop("disabled", None)
        else:
            row = {"key": k, "value": "" if enabled_key else _s(v), "type": "default"}
            if enabled_key:
                row["current"] = _s(v)
                row[enabled_key] = True
            rows.append(row)
    removed = set(before) - set(after)
    return [r for r in rows if r.get("key") not in removed]


# ───────────────────────── so'rov/javob ko'rinishlari ─────────────────────────
def _qs(params):
    return "&".join("%s=%s" % (quote(str(p["name"]), safe="{}$:@,/"), quote(str(p.get("value", "")), safe="{}$:@,/")) for p in params if p.get("name") and p.get("type") != "file")


def request_view(spec):
    qs = _qs(spec.get("params") or [])
    return {"method": (spec.get("method") or "GET").upper(), "url": (spec.get("url") or "") + ("?" + qs if qs else ""),
            "headers": [{"key": h["name"], "value": h.get("value", "")} for h in spec.get("headers") or [] if h.get("name")],
            "body": spec.get("body") or "", "body_mode": "urlencoded" if spec.get("body_type") == "form" else "raw"}


def apply_request(spec, new, orig):
    """JS dagi o'zgarishlarni (faqat farq qilganlarini) spec ga qaytaradi."""
    if not new:
        return spec
    spec = dict(spec)
    if new["method"] != orig["method"]:
        spec["method"] = new["method"]
    if new["url"] != orig["url"]:
        base, _, qs = new["url"].partition("?")
        files = [p for p in spec.get("params") or [] if p.get("type") == "file"]
        spec["url"] = base
        spec["params"] = [{"name": unquote(k), "value": unquote(v)} for k, v in parse_qsl(qs.replace("+", "%2B"), keep_blank_values=True)] + files
    if new["header"] != [{"key": h["key"], "value": h["value"]} for h in orig["headers"]]:
        spec["headers"] = [{"name": h["key"], "value": h.get("value", "")} for h in new["header"] if not h.get("disabled")]
    if new["body"]["raw"] != orig["body"]:
        spec["body"] = new["body"]["raw"]
    return spec


def _resolved(spec, variables):
    """Yuborilgan so'rovning o'zgaruvchilari yechilgan nusxasi (test skriptlarida pm.request shu)."""
    rv = lambda x: replace_variables(x, variables)  # noqa: E731
    out = dict(spec)
    out["url"] = rv(spec.get("url", ""))
    out["params"] = [{**p, "name": rv(p.get("name", "")), "value": rv(p.get("value", ""))} for p in spec.get("params") or []]
    out["headers"] = [{"name": rv(h.get("name", "")), "value": rv(h.get("value", ""))} for h in spec.get("headers") or []]
    out["body"] = resolve_form_body(spec.get("body"), variables) if spec.get("body_type") == "form" else rv(spec.get("body") or "")
    return out


def _parse_set_cookie(line):
    first, *attrs = [x.strip() for x in str(line).split(";")]
    name, _, value = first.partition("=")
    c = {"name": name, "value": value, "httpOnly": False, "secure": False}
    for a in attrs:
        k, _, v = a.partition("=")
        k = k.lower()
        if k in ("domain", "path", "expires"):
            c[k] = v
        elif k == "httponly":
            c["httpOnly"] = True
        elif k == "secure":
            c["secure"] = True
    return c


def response_view(result, jar=None):
    text = result.get("body_text")
    if text is None:
        r = result.get("response")
        text = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
    return {"code": result["status"], "status": _phrase(result["status"]), "headers": result.get("resp_headers") or {}, "body": text,
            "time": round(result.get("time", 0) * 1000), "size": result.get("size", 0), "cookies": [_parse_set_cookie(c) for c in result.get("set_cookies") or []], "jar": jar or []}


# ───────────────────────── pm.sendRequest → engine ─────────────────────────
def postman_request_to_spec(req, settings):
    spec = {"method": (req.get("method") or "GET").upper(), "url": req.get("url") or "", "timeout": min(float(req.get("timeout") or 30), 60),
            "headers": [{"name": h["key"], "value": h.get("value", "")} for h in req.get("header") or [] if h.get("key") and not h.get("disabled")]}
    body = req.get("body")
    if body:
        mode = body.get("mode")
        if mode == "raw":
            spec["body"] = body.get("raw") or ""
        elif mode == "urlencoded":
            spec["body"] = "&".join("%s=%s" % (quote(x["key"]), quote(str(x.get("value", "")))) for x in body.get("urlencoded") or [] if not x.get("disabled"))
            spec["body_type"], spec["content_type"] = "form", "application/x-www-form-urlencoded"
        elif mode == "formdata":
            spec["body_type"] = "multipart"
            spec["multipart_fields"] = [{"name": x["key"], "value": str(x.get("value", ""))} for x in body.get("formdata") or [] if not x.get("disabled") and x.get("type", "text") == "text"]
        elif mode == "graphql":
            g = body.get("graphql") or {}
            try:
                v = json.loads(g["variables"]) if g.get("variables") else None
            except ValueError:
                v = None
            spec["body"], spec["body_type"] = json.dumps({"query": g.get("query", ""), **({"variables": v} if v is not None else {})}), "json"
    auth = req.get("auth")
    if auth:
        def f(kind, key):
            return next((x.get("value") for x in auth.get(kind, []) if x.get("key") == key), "")
        if auth.get("type") == "bearer":
            spec["authorization"] = "Bearer " + str(f("bearer", "token"))
        elif auth.get("type") == "basic":
            spec["authorization"] = "Basic " + base64.b64encode(("%s:%s" % (f("basic", "username"), f("basic", "password"))).encode()).decode()
        elif auth.get("type") == "apikey" and f("apikey", "in") != "query":
            spec["headers"].append({"name": f("apikey", "key"), "value": str(f("apikey", "value"))})
    for k in ("follow_redirects", "max_redirects", "http2", "ssl_verify", "proxy", "cert", "cert_key", "ca_bundle", "use_cookies"):
        if (settings or {}).get(k) not in (None, ""):
            spec[k] = settings[k]
    return spec


class EngineHost:
    """pm.sendRequest va cookie jar: asosiy engine orqali (proxy, SSL, cookie jar, fayl siyosati bilan)."""

    def __init__(self, services, variables, settings):
        self.sv, self.vars, self.settings = services, variables, settings or {}

    def send(self, req):
        ctx = ExecContext(variables=self.vars, cookies=self.sv.cookies, allowed_file_roots=self.sv.allowed_file_roots, allowed_files=self.sv.allowed_files, keep_text=True)
        r = execute(postman_request_to_spec(req, self.settings), ctx)
        if r["status"] == "ERROR":
            return {"error": {"message": str(r["response"])}}
        return {"response": response_view(r)}

    def cookie(self, op):
        store = self.sv.cookies
        if store is None:
            return {"error": "cookie jar o'chiq"}
        host = (urlsplit(op.get("url", "")).hostname or "").lower()
        mine = [c for c in store.list() if c["domain"].lstrip(".") == host or host.endswith("." + c["domain"].lstrip("."))]
        brief = lambda c: {"name": c["name"], "value": c["value"], "domain": c["domain"], "path": c["path"], "httpOnly": bool(c["httponly"]), "secure": bool(c["secure"])}  # noqa: E731
        kind = op["op"]
        if kind == "get":
            c = next((x for x in mine if x["name"] == op.get("name")), None)
            return {"value": brief(c) if c else None}
        if kind == "getAll":
            return {"value": [brief(c) for c in mine]}
        if kind == "set":
            c = op["cookie"]
            store.upsert({"domain": host, "name": c["name"], "value": _s(c.get("value", "")), "path": c.get("path", "/"), "secure": c.get("secure"), "httponly": c.get("httpOnly")})
            return {"value": None}
        if kind == "unset":
            store.delete(host, "/", op["name"])
            return {"value": None}
        if kind == "clear":
            store.delete(host)
            return {"value": None}
        return {"error": "noma'lum amal: %s" % kind}


# ───────────────────────── asosiy kirish ─────────────────────────
def run_item(spec, services, scripts=None, ref=None, row=None, info=None, ctx_kwargs=None):
    """spec ni skriptlar bilan bajaradi. Natija — `engine.execute` natijasi + `scripts` kaliti.

    scripts: {"prerequest": [ScriptSource|dict], "test": [...]}  (collection → papka → so'rov tartibida).
    """
    scripts = scripts or {}
    pre, post = [_src(x, "prerequest") for x in scripts.get("prerequest") or []], [_src(x, "test") for x in scripts.get("test") or []]
    kw = dict(ctx_kwargs or {})                 # retry_count, retry_pause, stop (batch)
    spec = {k: v for k, v in spec.items() if k not in ("scripts", "ref", "scripts_info")}

    def make_ctx(variables, keep_text=False):
        base = {"cookies": services.cookies, "allowed_file_roots": services.allowed_file_roots, "allowed_files": services.allowed_files}
        base.update(kw)
        return ExecContext(variables=variables, keep_text=keep_text, **base)

    if not (pre or post):
        return execute(spec, make_ctx(spec.get("env_vars") or {}))
    if not scripting.available():
        r = execute(spec, make_ctx(spec.get("env_vars") or {}))
        r["scripts"] = {"available": False, "message": "Skriptlar o'chiq: quickjs-ng o'rnatilmagan", "install": scripting.INSTALL_HINT, "tests": [], "console": [], "errors": []}
        return r

    ws = services.ws
    limits = Limits.from_meta(ws.meta() if ws is not None else {})
    settings = (ws.meta().get("settings") if ws is not None else None) or {}
    scopes, env_id, env_name, active_env = load_scopes(ws, ref, row)
    before = json.loads(json.dumps(scopes))
    info = dict(info or {})
    host = EngineHost(services, merged(scopes), settings)
    view = request_view(spec)
    session = ScriptSession(scopes, view, {**info, "eventName": "prerequest"}, limits, host, active_env, env_name)

    for s in pre:
        session.run(s)
    mid = session.collect_state()
    skipped = mid["skip"]
    spec2 = apply_request(spec, mid["request"], view) if mid["request"] else spec

    result = None
    if not skipped:
        variables = {**(spec.get("env_vars") or {}), **merged(mid["scopes"])}
        result = execute(spec2, make_ctx(variables, keep_text=True))
        if result["status"] != "ERROR" and post:
            jar = []
            session.set_event("test")
            session.set_sent_request(request_view(_resolved(spec2, variables)))
            session.set_response(response_view(result, jar))
            for s in post:
                session.run(s)
    report = session.collect()
    written = []
    try:
        written = persist(ws, ref, env_id, before, report.scopes, report.changed)
    except Exception as exc:        # noqa: BLE001 — saqlash xatosi so'rov natijasini yo'qotmasin
        report.errors.append({"name": "PersistError", "message": "O'zgaruvchilarni saqlab bo'lmadi: %s" % exc, "stack": "", "line": None, "origin": {"kind": "persist", "scope": "", "name": "", "id": ""}})
    if result is None:
        result = {"status": "SKIPPED", "time": 0.0, "size": 0, "url": spec.get("url", ""), "response": "pm.execution.skipRequest()", "resp_headers": {}, "error": False, "retries": 0, "timing": None, "http_version": None}
    result.pop("body_text", None)
    result["scripts"] = {
        "available": True, "tests": report.tests, "console": report.logs, "errors": report.errors, "skipped": skipped, "next_set": report.next_set,
        "next_request": report.next_request if report.next_set else None, "changed": written, "aborted": report.aborted, "limits": limits.as_dict(),
        "variables": {k: {kk: _s(vv) for kk, vv in report.scopes.get(k, {}).items()} for k in ("environment", "globals", "collection")} if report.changed else {},
    }
    return result


def _src(x, kind):
    if isinstance(x, ScriptSource):
        return x
    return ScriptSource(x.get("source", ""), x.get("kind", kind), x.get("scope", "request"), x.get("name", ""), x.get("id", ""))
