"""Proxy capture: ishga tushirish/to'xtatish, ushlangan so'rovlar, collection'ga saqlash."""
from flask import Blueprint, current_app, jsonify, request

from ..proxy import entries_to_items
from ..storage import model

bp = Blueprint("proxy", __name__, url_prefix="/api")


def _mgr():
    return current_app.extensions["proxy"]


def _state():
    p = _mgr().proxy
    return {"running": bool(p), "url": p.url if p else None, "port": p.port if p else None, "next": p.seq if p else 0}


@bp.get("/proxy")
def state():
    p = _mgr().proxy
    d = _state()
    d["entries"] = p.entries(request.args.get("from", 0, type=int)) if p else []
    return jsonify(d)


@bp.post("/proxy/start")
def start():
    port = (request.get_json(silent=True) or {}).get("port") or 0
    if not isinstance(port, int) or not 0 <= port <= 65535:
        return jsonify({"error": "Port 0–65535 oralig'ida bo'lsin (0 — avtomatik)"}), 400
    try:
        _mgr().start(port)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_state())


@bp.post("/proxy/stop")
def stop():
    return jsonify({"ok": _mgr().stop()})


@bp.post("/proxy/clear")
def clear():
    if _mgr().proxy:
        _mgr().proxy.clear()
    return jsonify({"ok": True})


@bp.post("/proxy/save")
def save():
    """Tanlangan yozuvlar (seq ro'yxati; bo'sh — hammasi) collection ichida yangi papkaga qo'shiladi."""
    d = request.get_json(silent=True) or {}
    p = _mgr().proxy
    if not p:
        return jsonify({"error": "Proxy ishlamayapti"}), 409
    ws = current_app.extensions["workspace"]
    try:
        col = ws.get_collection(d.get("collection_id") or "")
    except Exception:                                   # noqa: BLE001
        return jsonify({"error": "Collection topilmadi"}), 404
    seqs = set(d.get("seqs") or [])
    items = entries_to_items([e for e in p.entries(full=True) if not seqs or e["seq"] in seqs])
    if not items:
        return jsonify({"error": "Saqlanadigan HTTP so'rov yo'q (HTTPS tunnellar ichi ko'rinmaydi)"}), 400
    folder = model.new_folder((d.get("folder_name") or "").strip() or "Ushlangan so'rovlar")
    folder["item"] = items
    col["item"].append(folder)
    ws.save_collection(col)
    return jsonify({"saved": len(items), "folder_id": folder["id"]})
