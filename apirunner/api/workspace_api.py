"""Yangi workspace API (/api/*): collection, environment, globals, localStorage importi."""
import os

from flask import Blueprint, current_app, jsonify, request

from ..core import scripting
from ..core.scripting.sandbox import Limits
from ..storage import files, model, tree_ops
from ..storage.migrate import import_localstorage
from ..storage.workspace import Conflict, NotFound

bp = Blueprint("workspace_api", __name__, url_prefix="/api")


def _ws():
    return current_app.extensions["workspace"]


@bp.errorhandler(NotFound)
def _not_found(_e):
    return jsonify({"error": "Topilmadi"}), 404


@bp.errorhandler(Conflict)
def _conflict(_e):
    return jsonify({"error": "Ma'lumot boshqa tab yoki jarayonda o'zgartirilgan. Qayta yuklang.", "conflict": True}), 409


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
    _ws().save_collection(col, expected_rev=(col.get("x-apirunner") or {}).get("rev"))
    return jsonify({"ok": True})


@bp.delete("/collections/<cid>")
def delete_collection(cid):
    _ws().delete_collection(cid)
    return jsonify({"ok": True})


# environments
ENV_KINDS = ("", "dev", "test", "prod")


def _env_extras_error(d):
    """Muhit turi (Dev/Test/Prod) va Prod tasdig'i: noto'g'ri qiymat 400."""
    if "kind" in d and d["kind"] not in ENV_KINDS:
        return "Muhit turi dev, test yoki prod bo'lishi kerak"
    for k in ("confirm_writes", "runner_get_only"):
        if k in d and not isinstance(d[k], bool):
            return f"{k} true/false bo'lishi kerak"
    return None


@bp.post("/environments")
def create_environment():
    d = request.get_json(silent=True) or {}
    if not d.get("name", "").strip():
        return jsonify({"error": "Nom kiritilmagan"}), 400
    bad = _env_extras_error(d)
    if bad:
        return jsonify({"error": bad}), 400
    env = model.new_environment(d["name"].strip(), values=d.get("values") or [])
    for k in ("kind", "confirm_writes", "runner_get_only"):
        if k in d:
            env[k] = d[k]
    return jsonify({"ok": True, "id": _ws().save_environment(env)})


@bp.get("/environments/<eid>")
def get_environment(eid):
    return jsonify(_ws().get_environment(eid))


@bp.put("/environments/<eid>")
def put_environment(eid):
    env = request.get_json(silent=True) or {}
    if env.get("id") != eid or not isinstance(env.get("values"), list):
        return jsonify({"error": "Environment tuzilmasi noto'g'ri"}), 400
    bad = _env_extras_error(env)
    if bad:
        return jsonify({"error": bad}), 400
    _ws().get_environment(eid)
    _ws().save_environment(env, expected_rev=env.get("rev"))
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
    _ws().save_globals(g, expected_rev=g.get("rev"))
    return jsonify({"ok": True})


# skriptlar (quickjs-ng): holat va chegaralar
@bp.get("/scripts/status")
def scripts_status():
    return jsonify({"available": scripting.available(), "version": scripting.version(), "install": scripting.INSTALL_HINT,
                    "limits": Limits.from_meta(_ws().meta()).as_dict(), "defaults": scripting.DEFAULT_LIMITS})


# cookie jar (SQLite)
@bp.get("/cookies")
def list_cookies():
    return jsonify(current_app.extensions["cookies"].list())


@bp.post("/cookies")
def upsert_cookie():
    try:
        current_app.extensions["cookies"].upsert(request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


@bp.delete("/cookies")
def delete_cookies():
    n = current_app.extensions["cookies"].delete(request.args.get("domain"), request.args.get("path"), request.args.get("name"))
    return jsonify({"ok": True, "deleted": n})


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


# ── daraxt (item) operatsiyalari ──
@bp.errorhandler(tree_ops.TreeError)
def _tree_error(e):
    return jsonify({"error": str(e)}), 400


@bp.post("/collections/<cid>/items")
def add_item(cid):
    d = request.get_json(silent=True) or {}
    item = d.get("item")
    if not isinstance(item, dict):
        return jsonify({"error": "item kerak"}), 400
    ws = _ws()
    with ws.lock:
        col = ws.get_collection(cid)
        new_id = tree_ops.add_item(col, d.get("parent_id"), item, d.get("index"))
        ws.save_collection(col)
    return jsonify({"ok": True, "id": new_id})


@bp.patch("/collections/<cid>/items/<iid>")
def patch_item(cid, iid):
    ws = _ws()
    with ws.lock:
        col = ws.get_collection(cid)
        node = tree_ops.update_item(col, iid, request.get_json(silent=True) or {})
        ws.save_collection(col)
    return jsonify({"ok": True, "item": node})


@bp.delete("/collections/<cid>/items/<iid>")
def delete_item(cid, iid):
    ws = _ws()
    with ws.lock:
        col = ws.get_collection(cid)
        tree_ops.delete_item(col, iid)
        ws.save_collection(col)
    return jsonify({"ok": True})


@bp.post("/items/move")
def move_items():
    """{src, dst, ids[], target_id, position: before|after|inside, copy}"""
    d = request.get_json(silent=True) or {}
    mapping = tree_ops.move(_ws(), d.get("src"), d.get("ids") or [], d.get("dst") or d.get("src"),
                            d.get("target_id"), d.get("position", "inside"), bool(d.get("copy")))
    return jsonify({"ok": True, "mapping": mapping})


# ── UI holati (ochiq tablar va h.k. — sahifa yangilanganda va server qayta ishga tushganda tiklanadi) ──
@bp.get("/ui-state")
def get_ui_state():
    return jsonify(_ws().get_ui_state())


@bp.put("/ui-state")
def put_ui_state():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        return jsonify({"error": "obyekt kerak"}), 400
    ws = _ws()
    with ws.lock:                                   # tablar va daraxt holati alohida yoziladi — kalitlar bo'yicha birlashtiriladi
        cur = ws.get_ui_state()
        cur.update(d)
        ws.save_ui_state(cur)
    return jsonify({"ok": True})


@bp.put("/workspace/meta")
def put_meta():
    d = request.get_json(silent=True) or {}
    allowed = {k: d[k] for k in ("active_environment_id", "legacy_default_notified", "nameclean_dismissed") if k in d}
    if isinstance(d.get("settings"), dict):
        allowed["settings"] = d["settings"]
    if isinstance(d.get("script_limits"), dict):
        allowed["script_limits"] = Limits.from_meta({"script_limits": d["script_limits"]}).as_dict()      # chegaralarga keltiriladi
    _ws().update_meta(**allowed)
    return jsonify({"ok": True, "meta": _ws().meta()})


# ── tarix (server tomonda) ──
@bp.post("/history")
def add_history():
    d = request.get_json(silent=True) or {}
    if d.get("kind") not in ("request", "run", "url"):
        return jsonify({"error": "kind noto'g'ri"}), 400
    current_app.extensions["db"].add_history(d["kind"], d.get("payload"))
    return jsonify({"ok": True})


@bp.delete("/history")
def clear_history():
    current_app.extensions["db"].delete_history(request.args.get("kind"), request.args.get("id", type=int))
    return jsonify({"ok": True})


# ── import (fayl tashlash / Import tugmasi). Bosqich 5 da to'liq round-trip testlar bilan kengayadi ──
@bp.post("/import")
def import_any():
    import json as _json
    d = request.get_json(silent=True) or {}
    content = d.get("content")
    try:
        doc = _json.loads(content) if isinstance(content, str) else content
    except _json.JSONDecodeError:
        return jsonify({"error": "JSON o'qib bo'lmadi (YAML hali qo'llab-quvvatlanmaydi)"}), 400
    from ..importers.openapi import import_openapi, looks_like_openapi
    from ..importers.postman import import_postman, looks_like_postman
    if looks_like_openapi(doc):
        col, kind = import_openapi(doc), "openapi"
    elif looks_like_postman(doc):
        col, kind = import_postman(doc), "postman"
    else:
        return jsonify({"error": "Format tanilmadi (Postman collection yoki OpenAPI JSON kerak)"}), 400
    summary = _import_summary(col, kind)
    if d.get("dry_run"):
        return jsonify({"ok": True, "dry_run": True, **summary})
    cid = _ws().save_collection(col)
    return jsonify({"ok": True, "id": cid, **summary})


def _import_summary(col, kind):
    folders = requests_n = 0
    stack = list(col.get("item", []))
    while stack:
        it = stack.pop()
        if model.is_folder(it):
            folders += 1
            stack.extend(it.get("item", []))
        else:
            requests_n += 1
    return {"kind": kind, "name": col["info"]["name"], "folders": folders, "requests": requests_n, "variables": len(col.get("variable", []))}


@bp.post("/import/fetch")
def import_fetch():
    """URL'dan import uchun matnni yuklab beradi (faqat http/https, 15 s, 10 MB)."""
    import httpx
    url = str((request.get_json(silent=True) or {}).get("url") or "").strip()
    if not url.lower().startswith(("http://", "https://")):
        return jsonify({"error": "URL http:// yoki https:// bilan boshlanishi kerak"}), 400
    try:
        r = httpx.get(url, timeout=15, follow_redirects=True)
    except httpx.HTTPError as exc:
        return jsonify({"error": f"Yuklab bo'lmadi: {exc}"}), 400
    if r.status_code >= 400:
        return jsonify({"error": f"Server {r.status_code} qaytardi"}), 400
    if len(r.content) > 10 * 1024 * 1024:
        return jsonify({"error": "Fayl 10 MB dan katta"}), 400
    return jsonify({"content": r.text})


# ── holat / zaxiralar ──
@bp.get("/status")
def status():
    from .. import __version__
    r = dict(current_app.config["MIGRATION_RESULT"])
    return jsonify({"version": __version__, "schemaVersion": _ws().schema_version(),
                    "migration": {"status": r["status"], "legacy": r["legacy"], "message": r["message"]},
                    "meta": _ws().meta()})


@bp.get("/backups")
def list_backups():
    from ..storage import backup as bk
    return jsonify([{k: v for k, v in b.items() if k != "path"} for b in bk.list_backups(current_app.extensions["backup_dir"])])


@bp.post("/backups")
def create_backup_route():
    from .. import __version__
    from ..storage import backup as bk
    ws = _ws()
    with ws.lock:
        path = bk.create_backup(ws.root, current_app.extensions["saved_file"], __version__,
                                current_app.extensions["backup_dir"], suffix="manual")
    return jsonify({"ok": True, "name": os.path.basename(path)})


@bp.post("/collections/<cid>/inherit-auth")
def inherit_auth(cid):
    """So'rovlarning o'z auth'ini olib tashlaydi (ya'ni "Meros"). Ommaviy o'zgarishdan OLDIN zaxira olinadi; bitta atomik yozuv."""
    from .. import __version__
    from ..storage import backup as bk
    d = request.get_json(silent=True) or {}
    ids = d.get("ids")
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids (ro'yxat) kerak"}), 400
    ws = _ws()
    with ws.lock:
        col = ws.get_collection(cid)
        targets = []
        for iid in ids:
            hit = tree_ops.find(col["item"], iid)
            if not hit or "item" in hit[0]:
                return jsonify({"error": "So'rov topilmadi: %s" % iid}), 404
            targets.append(hit[0])
        path = bk.create_backup(ws.root, current_app.extensions["saved_file"], __version__, current_app.extensions["backup_dir"], suffix="pre-bulk-auth")
        changed = 0
        for item in targets:
            if (item.get("request") or {}).pop("auth", None) is not None:
                changed += 1
        ws.save_collection(col)
    return jsonify({"ok": True, "changed": changed, "backup": os.path.basename(path)})


@bp.post("/backups/restore")
def restore_backup_route():
    from .. import __version__
    from ..storage.restore import restore_backup
    name = (request.get_json(silent=True) or {}).get("name", "")
    bdir = current_app.extensions["backup_dir"]
    ws = _ws()
    try:
        with ws.lock:
            pre = restore_backup(os.path.join(bdir, os.path.basename(name)), ws.root,
                                 current_app.extensions["saved_file"], __version__, bdir)
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "pre_restore": os.path.basename(pre)})


# ── yuklangan fayllar (workspace/files/<sha256>) ──
def _ws_root():
    return _ws().root


@bp.post("/files")
def upload_file():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "fayl topilmadi"}), 400
    return jsonify(files.store(_ws_root(), f.stream, f.filename))


@bp.post("/files/status")
def files_status():
    """{refs:[...]} -> {ref: {exists,size,name,managed}} — fayl topilmaganini (qizil qator) aniqlash uchun."""
    refs = (request.get_json(silent=True) or {}).get("refs") or []
    return jsonify({r: files.info(_ws_root(), r) for r in refs if isinstance(r, str)})


@bp.post("/files/adopt")
def adopt_file():
    """Eski vaqtinchalik yuklashni (.tmp_uploads) omborga ko'chiradi. Faqat yuklash papkasidagi fayllar."""
    d = request.get_json(silent=True) or {}
    raw, _, label = str(d.get("path") or "").partition("::")
    path = os.path.realpath(raw.strip())
    root = os.path.realpath(current_app.config["UPLOAD_DIR"])
    if not (path.startswith(root + os.sep) and os.path.isfile(path)):
        return jsonify({"error": "Fayl topilmadi yoki ruxsat yo'q"}), 400
    return jsonify(files.adopt(_ws_root(), path, d.get("name") or label.strip() or None))


@bp.get("/files/usage")
def files_usage():
    return jsonify(files.usage(_ws_root()))


@bp.post("/files/cleanup")
def files_cleanup():
    return jsonify(files.cleanup(_ws_root()))


# ── saqlangan javoblar (SQLite; har tabning oxirgi javobi va tarix diff'i uchun) ──
@bp.get("/responses/<int:rid>")
def get_response(rid):
    r = current_app.extensions["db"].get_response(rid)
    if not r:
        return jsonify({"error": "Javob saqlanmagan"}), 404
    body = r.pop("body")
    r["body"] = None if r["binary"] else body.decode("utf-8", "replace")
    return jsonify(r)


@bp.get("/responses/<int:rid>/raw")
def get_response_raw(rid):
    from flask import Response
    r = current_app.extensions["db"].get_response(rid)
    if not r:
        return jsonify({"error": "Javob saqlanmagan"}), 404
    resp = Response(r["body"], content_type=r["ctype"] or "application/octet-stream")
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Security-Policy"] = "sandbox"          # HTML javob (preview) skript bajara olmasin
    return resp
