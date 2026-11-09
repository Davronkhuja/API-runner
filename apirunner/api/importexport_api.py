"""Import (ko'rib chiqish → tasdiq) va eksport (Postman v2.1, OpenAPI, muhit/globals, workspace zip)."""
import json
import os

from flask import Blueprint, Response, current_app, jsonify, request

from .. import __version__
from ..exporters import openapi as oas_export
from ..exporters import postman as pm_export
from ..exporters import workspace as ws_export
from ..importers.common import ImportErr, stats
from ..importers.registry import items_of, parse_source
from ..storage import backup as bk
from ..storage import import_apply
from ..storage.workspace import NotFound

bp = Blueprint("importexport", __name__, url_prefix="/api")


def _ws():
    return current_app.extensions["workspace"]


def _parse(src):
    return parse_source(src.get("content"), src.get("name", ""), src.get("encoding"))


# ── import ──
@bp.post("/import")
def import_any():
    """Bitta manba. `dry_run` — faqat xulosa. Amal ko'rsatilmasa — yangi collection sifatida qo'shiladi (eski xatti-harakat)."""
    d = request.get_json(silent=True) or {}
    try:
        parsed = _parse(d)
    except ImportErr as e:
        return jsonify({"error": str(e)}), 400
    items = items_of(parsed)
    first = next((i for i in items if i["type"] == "collection"), items[0] if items else None)
    s = stats(first["ref"]) if first and first["type"] == "collection" else {"folders": 0, "requests": 0, "variables": first["stats"].get("variables", 0) if first else 0}
    summary = {"kind": parsed["kind"], "label": parsed["label"], "name": first["name"] if first else "", "folders": s["folders"], "requests": s["requests"], "variables": s["variables"],
               "examples": s.get("examples", 0), "scripts": s.get("scripts", 0), "items": len(items), "warnings": parsed["warnings"]}
    if d.get("dry_run"):
        return jsonify({"ok": True, "dry_run": True, **summary})
    ws = _ws()
    import_apply.restore_files(ws, parsed["files"])
    results = [import_apply.apply_item(ws, i, d.get("action") or "import", lambda: _backup("pre-import")) for i in items]
    out = {"ok": True, **summary, "results": results}
    col = next((r for r in results if r["type"] == "collection" and r.get("id")), None)
    if col:
        out["id"] = col["id"]
    return jsonify(out)


@bp.post("/import/preview")
def import_preview():
    """Ko'p manba: har biri uchun format, elementlar (statistika) va nom to'qnashuvi (birlashtirish natijasi oldindan hisoblanadi)."""
    ws = _ws()
    out = []
    for src in (request.get_json(silent=True) or {}).get("sources") or []:
        row = {"name": src.get("name", "")}
        try:
            parsed = _parse(src)
        except ImportErr as e:
            out.append({**row, "ok": False, "error": str(e)})
            continue
        items = []
        for it in items_of(parsed):
            c = import_apply.conflict_of(ws, it)
            items.append({"type": it["type"], "name": it["name"], "stats": it["stats"], "conflict": c, "default_action": "copy" if c else "import"})
        out.append({**row, "ok": True, "kind": parsed["kind"], "label": parsed["label"], "warnings": parsed["warnings"], "items": items, "files": len(parsed["files"])})
    return jsonify({"sources": out})


def _backup(suffix):
    ws = _ws()
    path = bk.create_backup(ws.root, current_app.extensions["saved_file"], __version__, current_app.extensions["backup_dir"], suffix=suffix)
    return os.path.basename(path)


@bp.post("/import/apply")
def import_apply_route():
    """{sources:[…], decisions:[{source, item, action}]} — har element uchun amal (import|copy|replace|merge|skip)."""
    d = request.get_json(silent=True) or {}
    decisions = {(x.get("source"), x.get("item")): x.get("action") for x in d.get("decisions") or []}
    ws = _ws()
    results, errors, restored = [], [], 0
    for si, src in enumerate(d.get("sources") or []):
        try:
            parsed = _parse(src)
        except ImportErr as e:
            errors.append({"source": si, "error": str(e)})
            continue
        for ii, it in enumerate(items_of(parsed)):
            action = decisions.get((si, ii)) or ("copy" if import_apply.conflict_of(ws, it) else "import")
            try:
                r = import_apply.apply_item(ws, it, action, lambda: _backup("pre-import-globals"))
            except ValueError as e:
                errors.append({"source": si, "item": ii, "error": str(e)})
                continue
            results.append({"source": si, "item": ii, **r})
        if parsed["files"]:
            restored += import_apply.restore_files(ws, parsed["files"])
    return jsonify({"ok": not errors, "results": results, "errors": errors, "files_restored": restored})


# ── eksport ──
def _download(data, filename, mime):
    body = data if isinstance(data, (bytes, str)) else json.dumps(data, indent=2, ensure_ascii=False)
    return Response(body, mimetype=mime, headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


def _fname(name, ext):
    base = "".join(c if c.isalnum() or c in "-_." else "_" for c in (name or "export")).strip("_") or "export"
    return f"{base}.{ext}"


@bp.get("/collections/<cid>/export")
def export_collection(cid):
    fmt = request.args.get("format", "postman")
    try:
        col = _ws().get_collection(cid)
    except NotFound:
        return jsonify({"error": "Collection topilmadi"}), 404
    name = col["info"]["name"]
    if fmt == "postman":
        return _download(pm_export.export_collection(col, strip_secrets=request.args.get("secrets") != "1"), _fname(name, "postman_collection.json"), "application/json")
    if fmt in ("openapi", "openapi-yaml"):
        doc = oas_export.export_openapi(col)
        if fmt == "openapi":
            return _download(oas_export.to_text(doc, "json"), _fname(name, "openapi.json"), "application/json")
        return _download(oas_export.to_text(doc, "yaml"), _fname(name, "openapi.yaml"), "application/yaml")
    return jsonify({"error": "format: postman | openapi | openapi-yaml"}), 400


@bp.get("/environments/<eid>/export")
def export_environment(eid):
    try:
        env = _ws().get_environment(eid)
    except NotFound:
        return jsonify({"error": "Muhit topilmadi"}), 404
    return _download(pm_export.export_environment(env), _fname(env.get("name"), "postman_environment.json"), "application/json")


@bp.get("/globals/export")
def export_globals():
    return _download(pm_export.export_globals(_ws().get_globals()), "globals.postman_globals.json", "application/json")


@bp.get("/workspace/export")
def export_workspace():
    data, manifest = ws_export.export_zip(_ws(), include_state=request.args.get("state", "1") != "0")
    name = f"api-runner-workspace-{manifest['exported_at'][:10]}.zip"
    return _download(data, name, "application/zip")
