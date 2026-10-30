"""Yangi workspace API (/api/*): collection, environment, globals, localStorage importi."""
from flask import Blueprint, current_app, jsonify, request

from ..storage import model
from ..storage.migrate import import_localstorage
from ..storage.workspace import NotFound

bp = Blueprint("workspace_api", __name__, url_prefix="/api")


def _ws():
    return current_app.extensions["workspace"]


@bp.errorhandler(NotFound)
def _not_found(_e):
    return jsonify({"error": "Topilmadi"}), 404


@bp.get("/version")
def version():
    from .. import __version__
    return jsonify({"version": __version__})


@bp.get("/export/legacy")
def export_legacy_route():
    """Orqaga qaytish: workspace -> saved_requests.json formati (yuklab olinadi)."""
    from flask import Response
    import json as _json
    from ..storage.legacy_view import export_workspace
    body = _json.dumps(export_workspace(_ws()), ensure_ascii=False, indent=2)
    return Response(body, content_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=saved_requests.json"})


@bp.get("/workspace")
def summary():
    ws = _ws()
    return jsonify({"meta": ws.meta(), "collections": ws.list_collections(),
                    "environments": ws.list_environments(), "globals": ws.get_globals()})


# collections
@bp.post("/collections")
def create_collection():
    name = (request.get_json(silent=True) or {}).get("name", "").strip()
    if not name:
        return jsonify({"error": "Nom kiritilmagan"}), 400
    col = model.new_collection(name)
    return jsonify({"ok": True, "id": _ws().save_collection(col)})


@bp.get("/collections/<cid>")
def get_collection(cid):
    return jsonify(_ws().get_collection(cid))


@bp.put("/collections/<cid>")
def put_collection(cid):
    col = request.get_json(silent=True) or {}
    if col.get("info", {}).get("_postman_id") != cid or not isinstance(col.get("item"), list):
        return jsonify({"error": "Collection tuzilmasi noto'g'ri"}), 400
    _ws().get_collection(cid)                 # mavjudligini tekshirish
    _ws().save_collection(col)
    return jsonify({"ok": True})


@bp.delete("/collections/<cid>")
def delete_collection(cid):
    _ws().delete_collection(cid)
    return jsonify({"ok": True})


# environments
@bp.post("/environments")
def create_environment():
    d = request.get_json(silent=True) or {}
    if not d.get("name", "").strip():
        return jsonify({"error": "Nom kiritilmagan"}), 400
    env = model.new_environment(d["name"].strip(), values=d.get("values") or [])
    return jsonify({"ok": True, "id": _ws().save_environment(env)})


@bp.get("/environments/<eid>")
def get_environment(eid):
    return jsonify(_ws().get_environment(eid))


@bp.put("/environments/<eid>")
def put_environment(eid):
    env = request.get_json(silent=True) or {}
    if env.get("id") != eid or not isinstance(env.get("values"), list):
        return jsonify({"error": "Environment tuzilmasi noto'g'ri"}), 400
    _ws().get_environment(eid)
    _ws().save_environment(env)
    return jsonify({"ok": True})


@bp.delete("/environments/<eid>")
def delete_environment(eid):
    _ws().delete_environment(eid)
    return jsonify({"ok": True})


# globals
@bp.get("/globals")
def get_globals():
    return jsonify(_ws().get_globals())


@bp.put("/globals")
def put_globals():
    g = request.get_json(silent=True) or {}
    if not isinstance(g.get("values"), list):
        return jsonify({"error": "Globals tuzilmasi noto'g'ri"}), 400
    g["_postman_variable_scope"] = "globals"
    _ws().save_globals(g)
    return jsonify({"ok": True})


# tarix (SQLite)
@bp.get("/history")
def history():
    kind = request.args.get("kind")
    limit = min(int(request.args.get("limit", 500)), 5000)
    return jsonify(current_app.extensions["db"].list_history(kind, limit))


# localStorage -> backend (bir martalik, idempotent)
@bp.post("/import/localstorage")
def import_ls():
    dump = (request.get_json(silent=True) or {}).get("data")
    if not isinstance(dump, dict):
        return jsonify({"error": "data (obyekt) kerak"}), 400
    stats = import_localstorage(_ws(), current_app.extensions["db"], dump)
    _ws().update_meta(localstorage_imported=True)
    return jsonify({"ok": True, "stats": stats})
