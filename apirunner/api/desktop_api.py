"""Nusxalar to'qnashuvi (sessiya qulfi) va desktop (.app) rejimida workspace papkasini o'zgartirish."""
import os

from flask import Blueprint, current_app, jsonify, request

from .. import desktop as dsk

bp = Blueprint("desktop", __name__, url_prefix="/api")


@bp.get("/instance")
def instance():
    """{conflict, holder:{pid,version,mode,started}|None, path} — bu workspace boshqa nusxada ham ochiqmi."""
    inst = current_app.extensions.get("instance")
    return jsonify(inst.as_json() if inst else {"conflict": False, "holder": None, "path": None})


@bp.get("/desktop")
def desktop_info():
    d = current_app.config.get("DESKTOP")
    ws = current_app.extensions["workspace"]
    return jsonify({"desktop": bool(d), "workspace_dir": ws.root, "home": d["home"] if d else None, "config": dsk.load_config(d["home"]) if d else None})


@bp.put("/desktop/workspace")
def set_workspace():
    """Desktop rejimi: keyingi ishga tushishdan boshlab ishlatiladigan workspace papkasi. Mavjud papka (workspace.json bor) yoki yangi bo'sh papka."""
    d = current_app.config.get("DESKTOP")
    if not d:
        return jsonify({"error": "Bu sozlama faqat desktop (.app) rejimida; oddiy serverda APIRUNNER_WORKSPACE muhit o'zgaruvchisi ishlatiladi"}), 400
    path = str((request.get_json(silent=True) or {}).get("workspace_dir") or "").strip()
    if not path or not os.path.isabs(path):
        return jsonify({"error": "To'liq (absolyut) papka yo'lini kiriting"}), 400
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.exists(path) and not os.path.isdir(path):
        return jsonify({"error": "Bu yo'l papka emas"}), 400
    if os.path.isdir(path) and os.listdir(path) and not os.path.exists(os.path.join(path, "workspace.json")):
        return jsonify({"error": "Papka bo'sh emas va API Runner workspace'i emas (workspace.json yo'q)"}), 400
    from ..storage import instance
    holder = instance.probe(path) if os.path.abspath(path) != os.path.abspath(current_app.extensions["workspace"].root) else None
    cfg = dsk.load_config(d["home"]) or {}
    cfg.update(workspace_dir=path, mode="custom")
    dsk.save_config(d["home"], cfg)
    return jsonify({"ok": True, "restart_required": True, "workspace_dir": path, "locked_by": holder})
