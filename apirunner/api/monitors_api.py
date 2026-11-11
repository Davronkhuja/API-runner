"""Rejalashtirilgan run'lar (monitor): CRUD, qo'lda yurgizish. Natijalar run tarixida (kind=monitor)."""
import threading

from flask import Blueprint, current_app, jsonify, request

from .. import monitor as mon

bp = Blueprint("monitors", __name__, url_prefix="/api")


def _store():
    return current_app.extensions["monitors"]


def _view(m):
    try:
        nxt = mon.next_run(m["cron"]) if m.get("enabled") else None
    except mon.CronError:
        nxt = None
    return {**m, "next_at": nxt.timestamp() if nxt else None}


@bp.get("/monitors")
def list_monitors():
    return jsonify({"items": [_view(m) for m in _store().list()]})


@bp.post("/monitors/validate")
def validate():
    cron = (request.get_json(silent=True) or {}).get("cron", "")
    try:
        nxt = mon.next_run(cron)
    except mon.CronError as e:
        return jsonify({"ok": False, "error": str(e)})
    return jsonify({"ok": True, "next_at": nxt.timestamp() if nxt else None})


@bp.post("/monitors")
def create():
    try:
        return jsonify(_view(_store().upsert(request.get_json(silent=True) or {}))), 201
    except (ValueError, mon.CronError) as e:
        return jsonify({"error": str(e)}), 400


@bp.put("/monitors/<mid>")
def update(mid):
    try:
        return jsonify(_view(_store().upsert(request.get_json(silent=True) or {}, mid)))
    except KeyError:
        return jsonify({"error": "Monitor topilmadi"}), 404
    except (ValueError, mon.CronError) as e:
        return jsonify({"error": str(e)}), 400


@bp.delete("/monitors/<mid>")
def remove(mid):
    if not _store().remove(mid):
        return jsonify({"error": "Monitor topilmadi"}), 404
    return jsonify({"ok": True})


@bp.post("/monitors/<mid>/run")
def run_now(mid):
    m = _store().get(mid)
    if not m:
        return jsonify({"error": "Monitor topilmadi"}), 404
    app = current_app._get_current_object()
    if request.args.get("wait"):
        return jsonify(mon.execute(app, m))
    threading.Thread(target=mon.execute, args=(app, m), daemon=True).start()
    return jsonify({"started": True}), 202
