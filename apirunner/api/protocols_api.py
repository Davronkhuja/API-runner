"""WebSocket / SSE sessiyalari: ulanish (server tomonida), oqim, yuborish, yopish, eksport. GraphQL sxema keshi."""
import json
import time

import httpx
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from ..core.auth import apply_auth_config
from ..core.engine import ExecContext, _build_kwargs
from ..core.protocols import ProtocolError, decode_payload
from ..core.scripted import Services, run_prerequest
from ..core.variables import replace_variables
from ..storage import schema_cache

bp = Blueprint("protocols", __name__, url_prefix="/api")


def _mgr():
    return current_app.extensions["protocols"]


def _sess(sid):
    s = _mgr().get(sid)
    if not s:
        raise ProtocolError("Sessiya topilmadi (server qayta ishga tushgan bo'lishi mumkin) — qayta ulaning")
    return s


@bp.errorhandler(ProtocolError)
def _perr(e):
    return jsonify({"error": str(e)}), 400 if "topilmadi" not in str(e) else 404


def _scheme(url, kind):
    u = (url or "").strip()
    low = u.lower()
    if kind == "ws":
        if low.startswith("http://"):
            return "ws://" + u[7:]
        if low.startswith("https://"):
            return "wss://" + u[8:]
        if not low.startswith(("ws://", "wss://")):
            raise ProtocolError("WebSocket manzili ws:// yoki wss:// bilan boshlanishi kerak")
    else:
        if low.startswith("ws://") or low.startswith("wss://"):
            raise ProtocolError("SSE manzili http:// yoki https:// bilan boshlanishi kerak")
        if not low.startswith(("http://", "https://")):
            raise ProtocolError("SSE manzili http:// yoki https:// bilan boshlanishi kerak")
    return u


@bp.post("/protocols/connect")
def connect():
    """{kind: ws|sse, spec: <engine spec>, options: {...}, scripts?, ref?} -> {id}."""
    d = request.get_json(silent=True) or {}
    kind = d.get("kind")
    if kind not in ("ws", "sse"):
        raise ProtocolError("kind: ws | sse")
    spec = d.get("spec") or {}
    if not (spec.get("url") or "").strip():
        raise ProtocolError("URL kiritilmagan")
    ext = current_app.extensions
    services = Services(ws=ext["workspace"], cookies=ext["cookies"], allowed_file_roots=())
    script_report = None
    spec2, variables, script_report = run_prerequest(spec, services, d.get("scripts"), d.get("ref"), None, d.get("info"))
    if script_report and (script_report.get("skipped")):
        return jsonify({"error": "Pre-request skripti ulanishni o'tkazib yubordi (pm.execution.skipRequest)", "scripts": script_report}), 409
    ctx = ExecContext(variables=variables)
    spec2 = {**spec2, "method": (spec2.get("method") if kind == "sse" else "GET") or "GET", "url": _scheme(replace_variables(spec2.get("url", ""), variables), kind)}
    try:
        method, url, kw = _build_kwargs({**spec2, "method": "GET" if kind == "ws" else spec2["method"]}, ctx, [])
    except Exception as exc:                        # noqa: BLE001 — o'zgaruvchi/fayl xatolari
        raise ProtocolError(str(exc)) from exc
    auth = kw.get("auth")
    if auth is not None and kind == "ws":
        raise ProtocolError("Digest/NTLM auth WebSocket handshake'ida qo'llab-quvvatlanmaydi (Bearer, Basic, API Key, JWT, Hawk, AWS SigV4 ishlaydi)")
    if kw.get("params"):
        url = str(httpx.URL(url).copy_merge_params(kw["params"]))
    url = _scheme(url, kind)
    opts = d.get("options") or {}
    cfg = {"url": url, "headers": dict(kw["headers"]), "timeout": spec2.get("timeout") or 30, "ssl_verify": bool(spec2.get("ssl_verify", True)), "variables": variables,
           "reconnect": opts.get("reconnect") or {}, "name": spec.get("name") or ""}
    if kind == "ws":
        cfg["subprotocols"] = [replace_variables(x, variables).strip() for x in (opts.get("subprotocols") or []) if str(x).strip()]
        cfg["ping_interval"] = opts.get("ping_interval") or None
    else:
        cfg["method"] = (spec2.get("method") or "GET").upper()
        if cfg["method"] not in ("GET", "POST", "PUT"):
            raise ProtocolError("SSE uchun GET, POST yoki PUT")
        cfg["body"] = kw.get("data")
        cfg["auth"] = auth
        cfg["last_event_id"] = replace_variables(opts.get("last_event_id") or "", variables)
    s = _mgr().start(kind, cfg)
    return jsonify({"id": s.id, "url": url, "scripts": script_report})


@bp.get("/protocols/<sid>")
def info(sid):
    return jsonify(_sess(sid).summary())


@bp.get("/protocols/<sid>/events")
def events(sid):
    s = _sess(sid)
    return jsonify({**s.summary(), "events": s.snapshot(request.args.get("from", 0, type=int))})


@bp.get("/protocols/<sid>/stream")
def stream(sid):
    s = _sess(sid)
    start = request.args.get("from", 0, type=int)

    def gen():
        for ev in s.stream(start):
            if ev is None:
                yield ": ping\n\n"
            else:
                yield "id: %d\ndata: %s\n\n" % (ev["seq"], json.dumps(ev, ensure_ascii=False))
    return Response(stream_with_context(gen()), content_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.post("/protocols/<sid>/send")
def send(sid):
    s = _sess(sid)
    if s.kind != "ws":
        raise ProtocolError("Faqat WebSocket sessiyasiga xabar yuboriladi")
    d = request.get_json(silent=True) or {}
    kind = d.get("kind") or "text"
    data = d.get("data", "")
    if kind != "binary" and isinstance(data, str):
        data = replace_variables(data, s.cfg.get("variables") or {})              # {{o'zgaruvchi}} va {{$guid}} kabi dinamiklar
    s.send(decode_payload(kind, data, d.get("encoding")))
    return jsonify({"ok": True})


@bp.post("/protocols/<sid>/close")
def close(sid):
    _sess(sid).close()
    return jsonify({"ok": True})


@bp.get("/protocols/<sid>/export")
def export(sid):
    s = _sess(sid)
    fmt = request.args.get("format", "json")
    evs = s.snapshot(0)
    if fmt == "txt":
        lines = []
        for e in evs:
            ts = __import__("time").strftime("%H:%M:%S", __import__("time").localtime(e["ts"])) + ".%03d" % int((e["ts"] % 1) * 1000)
            arrow = {"in": "<-", "out": "->"}.get(e.get("dir"), "··")
            lines.append(f"{ts} {arrow} {e['type']}{(' ' + str(e.get('event'))) if e.get('event') else ''} {e.get('data', e.get('message', ''))}".rstrip())
        body, mime, ext = "\n".join(lines), "text/plain", "txt"
    else:
        body, mime, ext = json.dumps({"session": s.summary(), "events": evs}, indent=2, ensure_ascii=False), "application/json", "json"
    return Response(body, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{s.kind}-{sid}.{ext}"'})


# ── Mock server (UI'dan ishga tushirish) ──
def _mocks():
    return current_app.extensions["mocks"]


def _mock_json(m):
    return {"id": m.id, "url": m.url, "port": m.port, "collection": m.collection, "collection_id": m.collection_id, "delay_ms": m.delay_ms, "routes": m.summary_routes(), "running": True}


@bp.post("/mocks")
def mock_start():
    d = request.get_json(silent=True) or {}
    try:
        col = current_app.extensions["workspace"].get_collection(d.get("collection_id") or "")
    except Exception:                               # noqa: BLE001
        return jsonify({"error": "Collection topilmadi"}), 404
    port = d.get("port") or 0
    if not isinstance(port, int) or not 0 <= port <= 65535:
        return jsonify({"error": "Port 0–65535 oralig'ida bo'lsin (0 — avtomatik)"}), 400
    try:
        m = _mocks().start(col, port, d.get("delay_ms") or 0, d.get("folder") or None)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_mock_json(m))


@bp.get("/mocks")
def mock_list():
    return jsonify([_mock_json(m) for m in _mocks().mocks.values()])


@bp.get("/mocks/<mid>/log")
def mock_log(mid):
    m = _mocks().get(mid)
    if not m:
        return jsonify({"entries": [], "running": False})
    return jsonify({"entries": m.entries(request.args.get("from", 0, type=int)), "running": True, "next": m.seq})


@bp.post("/mocks/<mid>/stop")
def mock_stop(mid):
    return jsonify({"ok": _mocks().stop(mid)})


# ── GraphQL sxema keshi (diskda: workspace/schemas/) ──
@bp.get("/graphql/schema")
def gql_schema_get():
    key = (request.args.get("key") or "").strip()
    if not key:
        return jsonify({"error": "key kerak"}), 400
    d = schema_cache.get(current_app.extensions["workspace"].root, key)
    return jsonify({"cached": True, **d} if d else {"cached": False})


@bp.put("/graphql/schema")
def gql_schema_put():
    d = request.get_json(silent=True) or {}
    key, intro = (d.get("key") or "").strip(), d.get("introspection")
    if not key or not isinstance(intro, dict) or "__schema" not in intro:
        return jsonify({"error": "key va introspection (data.__schema) kerak"}), 400
    if len(json.dumps(intro)) > 20 * 1024 * 1024:
        return jsonify({"error": "Sxema 20 MB dan katta"}), 400
    schema_cache.put(current_app.extensions["workspace"].root, key, intro)
    return jsonify({"ok": True})


@bp.delete("/graphql/schema")
def gql_schema_delete():
    schema_cache.delete(current_app.extensions["workspace"].root, (request.args.get("key") or "").strip())
    return jsonify({"ok": True})
