"""Bir nechta workspace: ro'yxat, yaratish, nomlash, almashtirish, o'chirish (Savatga)."""
from flask import Blueprint, current_app, jsonify, request

from ..storage.registry import DEFAULT_ID, RegistryError
from ..storage.workspace import Workspace

bp = Blueprint("workspaces", __name__, url_prefix="/api")


def _reg():
    return current_app.extensions["registry"]


def _counts(path):
    try:
        ws = Workspace(path)
        return {"collections": len(ws.list_collections()), "environments": len(ws.list_environments())}
    except Exception:                                   # noqa: BLE001
        return {"collections": 0, "environments": 0}


@bp.errorhandler(RegistryError)
def _err(e):
    return jsonify({"error": str(e)}), 400


@bp.get("/workspaces")
def list_workspaces():
    rows = _reg().list()
    return jsonify({"active": _reg().active, "items": [{**r, **(_counts(r["path"]) if request.args.get("counts") else {})} for r in rows]})


@bp.post("/workspaces")
def create():
    wid = _reg().create((request.get_json(silent=True) or {}).get("name"))
    return jsonify({"ok": True, "id": wid})


@bp.put("/workspaces/<wid>")
def rename(wid):
    _reg().rename(wid, (request.get_json(silent=True) or {}).get("name"))
    return jsonify({"ok": True})


def _busy():
    ext = current_app.extensions
    runs, jobs = ext["run_manager"].active(), ext["jobs"].active()
    mocks = list(ext["mocks"].mocks.values())
    live = [s for s in ext["protocols"].sessions.values() if s.status != "closed"]
    return len(runs) + len(jobs), len(mocks), len(live)


@bp.post("/workspaces/<wid>/activate")
def activate(wid):
    """Almashtirish: faol run'lar, mock va WS/SSE ulanishlari bor bo'lsa avval tasdiq (`force`). Keyin hammasi yangi workspace'ga qayta bog'lanadi."""
    from ..app import bind_workspace
    reg, ext = _reg(), current_app.extensions
    if not reg.get(wid):
        raise RegistryError("Workspace topilmadi")
    if wid == reg.active:
        return jsonify({"ok": True, "unchanged": True})
    runs, mocks, live = _busy()
    if (runs or mocks or live) and not (request.get_json(silent=True) or {}).get("force"):
        return jsonify({"error": "Faol jarayonlar bor", "needs_confirm": True, "runs": runs, "mocks": mocks, "connections": live}), 409
    for r in ext["run_manager"].active():
        r.stop.set()
    ext["mocks"].stop_all()
    ext["protocols"].shutdown()
    ext["protocols"].sessions.clear()
    target = reg.get(wid)["path"]
    bind_workspace(current_app._get_current_object(), target, ext["saved_file"] if wid == DEFAULT_ID else "", ext["backup_dir"], current_app.config["UPLOAD_DIR"])
    reg.set_active(wid)
    return jsonify({"ok": True, "active": wid})


@bp.delete("/workspaces/<wid>")
def remove(wid):
    reg = _reg()
    item, moved = reg.remove(wid)
    tid = current_app.extensions["trash"].add_workspace(item, moved)
    return jsonify({"ok": True, "trash_id": tid})
