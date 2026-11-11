"""WebSocket / SSE sessiyalari: ulanish (server tomonida), oqim, yuborish, yopish, eksport. GraphQL sxema keshi."""
import json

import httpx
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from ..core.auth import apply_auth_config
from ..core.engine import ExecContext, _build_kwargs
from ..core.protocols import ProtocolError, decode_payload
from ..core.scripted import Services, run_prerequest
from ..core.variables import replace_variables

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
