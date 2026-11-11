"""Mock server: collection Example'lari asosida javob beradi.

Moslash: metod + yo'l (`:id` va `{{var}}` — yo'l parametrlari, statik segment ustun) + ixtiyoriy query (Example `originalRequest.url.query`) va sarlavhalar
(`x-mock-*`). Javob tanlash: `x-mock-response-code` / `x-mock-response-name` sarlavhalari. Kechikish: Example `X-Mock-Delay` sarlavhasi (ms) yoki umumiy `delay_ms`.
Javob matnida `{{$guid}}`, `{{$timestamp}}`, `{{$randomInt}}` va yo'l parametrlari (`{{id}}`) almashtiriladi.
"""
import json
import re
import threading
import time
from urllib.parse import urlsplit

from flask import Flask, Response, jsonify, request
from werkzeug.serving import make_server

from .core.variables import replace_variables
from .storage import model

HOP = {"content-length", "transfer-encoding", "connection", "keep-alive", "content-encoding", "x-mock-delay", "server", "date"}
MAX_LOG = 500


def _segments(raw):
    """URL (satr) -> yo'l segmentlari. `{{baseUrl}}/users/:id`, `https://h/users/{{id}}?x=1` -> ['users', ':id'/'{{id}}']."""
    base = (raw or "").split("#")[0].split("?")[0]
    m = re.match(r"^\{\{[^}]+\}\}(.*)$", base)
    if m:
        path = m.group(1)
    else:
        u = urlsplit(base if "://" in base else "//" + base) if re.match(r"^[\w.-]+(:\d+)?(/|$)", base) or "://" in base else None
        path = u.path if u and u.netloc else base
    return [p for p in path.split("/") if p != ""]


def _param(seg):
    m = re.fullmatch(r":([\w-]+)", seg) or re.fullmatch(r"\{\{\s*([\w$.-]+)\s*\}\}", seg) or re.fullmatch(r"\{([\w-]+)\}", seg)
    return m.group(1) if m else None


def _q(url):
    q = (url or {}).get("query") if isinstance(url, dict) else None
    return [(x["key"], x.get("value") or "") for x in q or [] if isinstance(x, dict) and x.get("key") and not x.get("disabled")]


def build_routes(col, folder=None):
    """[{method, segments, name, example, conditions}] — har Example bitta yo'nalish."""
    routes = []

    def walk(items, ok):
        for it in items:
            if model.is_folder(it):
                walk(it["item"], ok or (folder is not None and folder in (it["name"], it["id"])))
            elif ok and it.get("response"):
                r = it.get("request") or {}
                url = r.get("url") if isinstance(r.get("url"), dict) else {"raw": str(r.get("url") or "")}
                segs = _segments(url.get("raw", ""))
                for ex in it["response"]:
                    if not isinstance(ex, dict):
                        continue
                    orig = ex.get("originalRequest") or {}
                    ourl = orig.get("url") if isinstance(orig.get("url"), dict) else {"raw": str(orig.get("url") or "")}
                    cond_q = _q(ourl)
                    cond_h = [(h["key"].lower(), h.get("value") or "") for h in orig.get("header") or [] if isinstance(h, dict) and h.get("key", "").lower().startswith("x-mock-") and not h.get("disabled")]
                    routes.append({"method": (r.get("method") or "GET").upper(), "segments": segs, "name": it["name"], "example": ex, "q": cond_q, "h": cond_h, "item_id": it["id"]})
    walk(col.get("item", []), folder is None)
    return routes


def _match_path(segs, parts):
    if len(segs) != len(parts):
        return None
    params, static = {}, 0
    for s, p in zip(segs, parts):
        name = _param(s)
        if name:
            params[name] = p
        elif s == p:
            static += 1
        else:
            return None
    return params, static


def pick(routes, method, parts, args, headers):
    """Eng mos Example: (route, params) yoki None. Shartlar bajarilmaganlar tashlanadi; ko'p shart va statik segment ustun."""
    want_code = headers.get("x-mock-response-code")
    want_name = headers.get("x-mock-response-name")
    best = None
    for r in routes:
        if r["method"] != method:
            continue
        m = _match_path(r["segments"], parts)
        if not m:
            continue
        if any(args.get(k) != v for k, v in r["q"]) or any(headers.get(k) != v for k, v in r["h"]):
            continue
        ex = r["example"]
        if want_code and str(ex.get("code")) != want_code:
            continue
        if want_name and ex.get("name") != want_name:
            continue
        score = (m[1], len(r["q"]) + len(r["h"]), 1 if 200 <= int(ex.get("code") or 200) < 300 else 0)
        if best is None or score > best[0]:
            best = (score, r, m[0])
    return (best[1], best[2]) if best else None


class MockServer:
    def __init__(self, col, host="127.0.0.1", port=0, delay_ms=0, folder=None):
        self.col, self.host, self.delay_ms = col, host, int(delay_ms or 0)
        self.routes = build_routes(col, folder)
        self.log, self.seq, self.lock = [], 0, threading.Lock()
        self.app = self._app()
        self.srv = make_server(host, int(port or 0), self.app, threaded=True)
        self.port = self.srv.server_port
        self.thread = None

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"

    def start(self):
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()

    def summary_routes(self):
        return [{"method": r["method"], "path": "/" + "/".join(r["segments"]), "name": r["name"], "example": r["example"].get("name"), "code": r["example"].get("code"),
                 "query": [f"{k}={v}" for k, v in r["q"]], "headers": [f"{k}: {v}" for k, v in r["h"]]} for r in self.routes]

    def entries(self, start=0):
        with self.lock:
            return [e for e in self.log if e["seq"] >= start]

    def _record(self, **e):
        with self.lock:
            e["seq"] = self.seq
            self.seq += 1
            self.log.append(e)
            del self.log[:-MAX_LOG]

    def _app(self):
        app = Flask("mock")

        @app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
        @app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
        def handle(path):
            t0 = time.time()
            parts = [p for p in path.split("/") if p]
            args = {k: v for k, v in request.args.items()}
            headers = {k.lower(): v for k, v in request.headers.items()}
            hit = pick(self.routes, request.method, parts, args, headers)
            base = {"ts": t0, "method": request.method, "path": "/" + path, "query": request.query_string.decode(), "remote": request.remote_addr, "size_in": request.content_length or 0}
            if not hit:
                avail = sorted({f"{r['method']} /{'/'.join(r['segments'])}" for r in self.routes})
                self._record(**base, matched=None, status=404, delay=0, ms=0)
                return jsonify({"error": "Mock: mos Example topilmadi", "method": request.method, "path": "/" + path, "available": avail}), 404
            r, params = hit
            ex = r["example"]
            exh = {h["key"]: h.get("value", "") for h in ex.get("header") or [] if isinstance(h, dict) and h.get("key")}
            delay = self.delay_ms + int(next((v for k, v in exh.items() if k.lower() == "x-mock-delay" and str(v).isdigit()), 0))
            if delay:
                time.sleep(delay / 1000.0)
            body = replace_variables(ex.get("body") or "", {**params, **{k: v for k, v in args.items()}}) if isinstance(ex.get("body"), str) else json.dumps(ex.get("body"))
            resp = Response(body if request.method != "HEAD" else b"", status=int(ex.get("code") or 200))
            for k, v in exh.items():
                if k.lower() not in HOP:
                    resp.headers[k] = replace_variables(str(v), params)
            if not any(k.lower() == "content-type" for k in exh):
                resp.headers["Content-Type"] = "application/json" if body.strip()[:1] in "{[" else "text/plain; charset=utf-8"
            resp.headers["X-Mock-Example"] = str(ex.get("name") or "")
            self._record(**base, matched=f"{r['name']} · {ex.get('name')}", status=resp.status_code, delay=delay, ms=round((time.time() - t0) * 1000))
            return resp
        return app


class MockManager:
    def __init__(self):
        self.mocks, self.lock = {}, threading.Lock()
        self.next = 1

    def start(self, col, port=0, delay_ms=0, folder=None, host="127.0.0.1"):
        try:
            m = MockServer(col, host, port, delay_ms, folder)
        except (OSError, SystemExit) as e:                         # werkzeug band portda sys.exit(1) qiladi
            raise ValueError(f"Port {port} band yoki ochib bo'lmadi") from e
        if not m.routes:
            m.srv.server_close()
            raise ValueError("Bu collection'da Example (javob namunasi) yo'q — mock uchun kamida bitta kerak")
        with self.lock:
            mid = str(self.next)
            self.next += 1
            self.mocks[mid] = m
        m.id = mid
        m.collection = col["info"]["name"]
        m.collection_id = model.collection_id(col)
        m.start()
        return m

    def get(self, mid):
        return self.mocks.get(mid)

    def stop(self, mid):
        m = self.mocks.pop(mid, None)
        if m:
            m.stop()
        return bool(m)

    def stop_all(self):
        for k in list(self.mocks):
            self.stop(k)


def run_cli(args):
    from .cli import CliError, load_collection
    col, _base, _w = load_collection(args)
    try:
        m = MockServer(col, args.host, args.port, args.delay)
    except (OSError, SystemExit) as e:
        raise CliError(f"Port {args.port} band yoki ochib bo'lmadi") from e
    if not m.routes:
        raise CliError("Collection'da Example yo'q — mock uchun kamida bitta kerak")
    print(f"Mock server: {m.url}  ({col['info']['name']}, {len(m.routes)} ta Example)\n")
    for r in m.summary_routes():
        print(f"  {r['method'].ljust(7)} {r['path'].ljust(36)} → {r['code']} {r['example'] or ''}" + (f"  [{' '.join(r['query'] + r['headers'])}]" if r["query"] or r["headers"] else ""))
    print("\nTo'xtatish: Ctrl+C")
    m.srv.timeout = 0.5
    try:
        m.srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
