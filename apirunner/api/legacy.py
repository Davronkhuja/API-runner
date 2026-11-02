"""Eski UI bilan 1:1 mos endpointlar: /saved/*, /run, /stream, /stop, /run_one, /upload_temp.

Ma'lumot workspace'dagi "saved" collection'da turadi; eski tekis format shu daraxtdan hosil qilinadi.
"""
import json
import os
import queue as queue_module
import uuid

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from ..core.engine import ExecContext, execute
from ..storage import model
from ..storage.migrate import LEGACY_COLLECTION_ID, LEGACY_COLLECTION_NAME
from ..storage.legacy_view import flat_view
from ..storage.workspace import NotFound
from .util import now_iso

bp = Blueprint("legacy", __name__)


def _ws():
    return current_app.extensions["workspace"]


def _load_col(ws):
    try:
        return ws.get_collection(LEGACY_COLLECTION_ID)
    except NotFound:
        return model.new_collection(LEGACY_COLLECTION_NAME, LEGACY_COLLECTION_ID)


def _find(items, rid, parent=None):
    """(item, ota_ro'yxat, ota_papka_node|None) ni qaytaradi."""
    for it in items:
        if it["id"] == rid:
            return it, items, parent
        if model.is_folder(it):
            hit = _find(it["item"], rid, it)
            if hit:
                return hit
    return None


@bp.get("/saved")
def get_saved():
    return jsonify(flat_view(_load_col(_ws())))


# ── papkalar ──
@bp.post("/saved/folder")
def create_folder():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nom kiritilmagan"}), 400
    ws = _ws()
    with ws.lock:
        col = _load_col(ws)
        fid = str(uuid.uuid4())
        legacy = {"id": fid, "name": name, "expanded": True, "created_at": now_iso()}
        col["item"].append(model.new_folder(name, fid, True, legacy))
        ws.save_collection(col)
    return jsonify({"ok": True, "id": fid})


@bp.put("/saved/folder/<fid>")
def update_folder(fid):
    data = request.get_json(silent=True) or {}
    ws = _ws()
    with ws.lock:
        col = _load_col(ws)
        hit = _find(col["item"], fid)
        if hit and model.is_folder(hit[0]):
            node, ext = hit[0], hit[0].setdefault("x-apirunner", {})
            legacy = ext.setdefault("legacy", {"id": fid})
            if "name" in data:
                node["name"] = data["name"].strip() or node["name"]
            if "expanded" in data:
                ext["expanded"] = bool(data["expanded"])
            legacy.update(name=node["name"], expanded=ext.get("expanded", True), updated_at=now_iso())
            ws.save_collection(col)
    return jsonify({"ok": True})


@bp.delete("/saved/folder/<fid>")
def delete_folder(fid):
    ws = _ws()
    with ws.lock:
        col = _load_col(ws)
        hit = _find(col["item"], fid)
        if hit and model.is_folder(hit[0]):
            node, siblings, _ = hit
            siblings.remove(node)
            # ichidagi so'rovlar ildizga chiqadi (eski xatti-harakat)
            col["item"].extend(it for it, _p in model.iter_requests(node["item"]))
            ws.save_collection(col)
    return jsonify({"ok": True})


# ── so'rovlar ──
def _attach(col, item, folder_id):
    parent = _find(col["item"], folder_id) if folder_id else None
    target = parent[0]["item"] if parent and model.is_folder(parent[0]) else col["item"]
    target.append(item)


@bp.post("/saved/request")
def save_request():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nom kiritilmagan"}), 400
    ws = _ws()
    with ws.lock:
        col = _load_col(ws)
        rid = data.get("id")
        hit = _find(col["item"], rid) if rid else None
        if hit and not model.is_folder(hit[0]):
            old, siblings, _ = hit
            old_legacy = old.get("x-apirunner", {}).get("legacy", {})
            data["updated_at"] = now_iso()
            data.setdefault("created_at", old_legacy.get("created_at", now_iso()))
            new_item = model.legacy_to_request_item(data)
            new_item["response"] = old.get("response", [])          # Example'lar yo'qolmasin
            new_folder = data.get("folder_id")
            _, _, cur_parent = hit
            if (cur_parent["id"] if cur_parent else None) == new_folder:
                siblings[siblings.index(old)] = new_item           # joyi saqlanadi
            else:
                siblings.remove(old)
                _attach(col, new_item, new_folder)
            ws.save_collection(col)
            return jsonify({"ok": True, "id": rid})
        data["id"] = str(uuid.uuid4())
        data["created_at"] = now_iso()
        data.setdefault("folder_id", None)
        _attach(col, model.legacy_to_request_item(data), data["folder_id"])
        ws.save_collection(col)
    return jsonify({"ok": True, "id": data["id"]})


@bp.put("/saved/request/<rid>")
def update_request(rid):
    data = request.get_json(silent=True) or {}
    ws = _ws()
    with ws.lock:
        col = _load_col(ws)
        hit = _find(col["item"], rid)
        if hit and not model.is_folder(hit[0]):
            item, siblings, cur_parent = hit
            legacy = item.setdefault("x-apirunner", {}).setdefault("legacy", {"id": rid})
            if "name" in data:
                item["name"] = legacy["name"] = data["name"].strip() or item["name"]
            legacy["updated_at"] = now_iso()
            if "folder_id" in data:
                legacy["folder_id"] = data["folder_id"]
                if (cur_parent["id"] if cur_parent else None) != data["folder_id"]:
                    siblings.remove(item)
                    _attach(col, item, data["folder_id"])
            ws.save_collection(col)
    return jsonify({"ok": True})


@bp.delete("/saved/request/<rid>")
def delete_request(rid):
    ws = _ws()
    with ws.lock:
        col = _load_col(ws)
        hit = _find(col["item"], rid)
        if hit and not model.is_folder(hit[0]):
            hit[1].remove(hit[0])
            ws.save_collection(col)
    return jsonify({"ok": True})


# ── fayl yuklash / runner ──
@bp.post("/upload_temp")
def upload_temp():
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "fayl topilmadi"}), 400
    upload_dir = current_app.config["UPLOAD_DIR"]
    os.makedirs(upload_dir, exist_ok=True)
    ext = os.path.splitext(f.filename or "")[1][:16]
    path = os.path.join(upload_dir, uuid.uuid4().hex + ext)
    f.save(path)
    return jsonify({"path": path, "name": f.filename})


@bp.post("/run")
def run_job():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Ma'lumot yuborilmagan"}), 400
    if not data.get("url"):
        return jsonify({"error": "URL kiritilmagan"}), 400
    if not data.get("rows"):
        data["rows"] = [{}]
    return jsonify({"job_id": current_app.extensions["jobs"].start(data)})


@bp.get("/stream/<job_id>")
def stream(job_id):
    jobs = current_app.extensions["jobs"]
    job = jobs.get(job_id)
    if not job:
        def err():
            yield 'data: {"error":"Job topilmadi"}\n\n'
        return Response(err(), content_type="text/event-stream")
    q = job["queue"]

    def generate():
        while True:
            try:
                item = q.get(timeout=60)
            except queue_module.Empty:
                yield ": keepalive\n\n"
                continue
            payload = json.dumps(item["data"], ensure_ascii=False)
            yield f"event: {item['type']}\ndata: {payload}\n\n"
            if item["type"] == "done":
                jobs.discard(job_id)
                break

    return Response(stream_with_context(generate()), content_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.post("/stop/<job_id>")
def stop_job(job_id):
    job = current_app.extensions["jobs"].get(job_id)
    if job:
        job["stop_event"].set()
        return jsonify({"ok": True})
    return jsonify({"error": "Job topilmadi"}), 404


@bp.post("/run_one")
def run_one():
    cfg = request.get_json(silent=True) or {}
    if not (cfg.get("url") or "").strip():
        return jsonify({"error": "no url"}), 400
    spec = dict(cfg, url=cfg["url"].strip(), timeout=cfg.get("timeout") or 30)
    ctx = ExecContext(variables=cfg.get("env_vars") or {},
                      allowed_file_roots=current_app.extensions["jobs"].allowed_file_roots,
                      cookies=current_app.extensions["cookies"])
    res = execute(spec, ctx)
    return jsonify({
        "status": "ERR" if res["status"] == "ERROR" else res["status"],
        "time": round(res["time"], 3), "size": res["size"], "response": res["response"],
        "resp_headers": res["resp_headers"], "url": res["url"],
        "set_cookies": res.get("set_cookies", []), "redirects": res.get("redirects", 0),
    })
