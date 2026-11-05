"""Fayl ombori (workspace/files/<sha256>), multipart/binary yuborish, migratsiya (Params fayli -> Body form-data)."""
import hashlib
import io
import json
import os
import time

import pytest

from apirunner.storage import files, migrations
from apirunner.storage.workspace import Workspace


def upload(client, name, data):
    r = client.post("/api/files", data={"file": (io.BytesIO(data), name)}, content_type="multipart/form-data")
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def run(client, **cfg):
    return client.post("/run_one", json=cfg).get_json()


# ── ombor ──
def test_upload_is_content_addressed_deduped_and_stored_inside_workspace(client):
    a = upload(client, "ariza.pdf", b"PDF-1")
    b = upload(client, "boshqa nom.pdf", b"PDF-1")
    assert a["hash"] == b["hash"] == hashlib.sha256(b"PDF-1").hexdigest()
    assert a["ref"].startswith("files/" + a["hash"] + "/") and a["size"] == 5
    root = client.application.extensions["workspace"].root
    assert os.path.isfile(os.path.join(root, "files", a["hash"]))
    assert len(os.listdir(os.path.join(root, "files"))) == 1                     # bitta nusxa, .part qoldig'i yo'q


def test_status_reports_missing_external_and_managed_files(client, tmp_path):
    a = upload(client, "a.txt", b"x")
    ext = tmp_path / "ext.txt"
    ext.write_text("hello")
    st = client.post("/api/files/status", json={"refs": [a["ref"], str(ext), str(tmp_path / "yoq.txt"), "files/" + "0" * 64 + "/x.txt"]}).get_json()
    assert st[a["ref"]] == {"exists": True, "size": 1, "name": "a.txt", "managed": True}
    assert st[str(ext)]["exists"] and not st[str(ext)]["managed"] and st[str(ext)]["size"] == 5
    assert not st[str(tmp_path / "yoq.txt")]["exists"]
    assert not st["files/" + "0" * 64 + "/x.txt"]["exists"]


def test_adopt_only_copies_from_the_upload_dir(client, isolated, tmp_path):
    inside = isolated / "uploads" / "tmp1.bin"
    inside.write_bytes(b"data")
    ok = client.post("/api/files/adopt", json={"path": f"{inside}::asl.bin"}).get_json()
    assert ok["name"] == "asl.bin" and ok["ref"].startswith("files/")
    outside = tmp_path / "secret.txt"
    outside.write_text("s")
    assert client.post("/api/files/adopt", json={"path": str(outside)}).status_code == 400   # ixtiyoriy faylni o'qib bo'lmaydi


def test_cleanup_removes_only_unreferenced_old_files(client):
    root = client.application.extensions["workspace"].root
    used = upload(client, "used.txt", b"used")
    old = upload(client, "old.txt", b"old")
    fresh = upload(client, "fresh.txt", b"fresh")
    cid = client.post("/api/collections", json={"name": "C"}).get_json()["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    col["item"] = [{"id": "r", "name": "R", "request": {"method": "POST", "url": {"raw": "http://x"}, "body": {"mode": "formdata", "formdata": [{"key": "f", "type": "file", "src": [used["ref"]]}]}}, "response": []}]
    client.put(f"/api/collections/{cid}", json=col)
    for h in (used["hash"], old["hash"]):                                         # "eski" — grace oynasidan o'tgan
        os.utime(os.path.join(root, "files", h), (time.time() - 7200, time.time() - 7200))
    u = client.get("/api/files/usage").get_json()
    assert u["count"] == 3 and u["unused_count"] == 1 and u["unused_size"] == 3
    r = client.post("/api/files/cleanup").get_json()
    assert r == {"removed": 1, "freed": 3}
    left = set(os.listdir(os.path.join(root, "files")))
    assert left == {used["hash"], fresh["hash"]}                                  # ishlatilayotgani va yangisi tegilmadi


def test_unsaved_open_tab_drafts_keep_their_files(client):
    root = client.application.extensions["workspace"].root
    f = upload(client, "draft.txt", b"d")
    os.utime(os.path.join(root, "files", f["hash"]), (time.time() - 7200,) * 2)
    with open(os.path.join(root, "ui_state_test.json"), "w") as fh:
        json.dump({"tabs": [{"draft": {"body": {"fields": [{"files": [{"ref": f["ref"]}]}]}}}]}, fh)
    assert files.cleanup(root) == {"removed": 0, "freed": 0}


# ── yuborish ──
def test_multipart_text_and_multiple_files_under_one_key_and_content_type(client, echo):
    a, b = upload(client, "a.txt", b"AAA"), upload(client, "b.png", b"BBB")
    spec = dict(url=echo + "/echo", method="POST", body_type="multipart", multipart_fields=[
        {"name": "title", "value": "salom"},
        {"name": "docs", "type": "file", "files": [{"ref": a["ref"], "name": "a.txt"}, {"ref": b["ref"], "name": "b.png"}]},
        {"name": "one", "type": "file", "content_type": "application/x-custom", "files": [{"ref": a["ref"], "name": "x.bin"}]},
    ])
    d = run(client, **spec)
    assert d["status"] == 200
    r = d["response"]
    assert r["form"] == {"title": ["salom"]}
    assert r["files"]["docs"]["filename"] in ("a.txt", "b.png")                   # echo faqat birinchisini ko'rsatadi (flat)
    assert r["files"]["one"] == {"filename": "x.bin", "content": "AAA"}
    assert "multipart/form-data" in r["headers"]["Content-Type"]
    # ikkala fayl ham yuborilganini xom tanadan tekshiramiz
    raw = run(client, **{**spec, "url": echo + "/echo"})["response"]
    assert raw["files"].get("docs") is not None


def test_missing_file_gives_clear_error_and_never_sends(client, echo, tmp_path):
    d = run(client, url=echo + "/echo", method="POST", body_type="multipart", multipart_fields=[
        {"name": "f", "type": "file", "files": [{"ref": str(tmp_path / "yoq.pdf"), "name": "yoq.pdf"}]}])
    assert d["status"] == "ERR"
    assert "Fayl topilmadi: yoq.pdf" in d["response"] and "qayta tanlang" in d["response"]


def test_binary_body_content_type_is_guessed_from_file_name(client, echo):
    f = upload(client, "rasm.png", b"\x89PNG-data")
    d = run(client, url=echo + "/echo", method="POST", body_file=f["ref"], body_file_name="rasm.png")
    assert d["status"] == 200 and d["response"]["headers"]["Content-Type"] == "image/png"
    d = run(client, url=echo + "/echo", method="POST", body_file=f["ref"], body_file_name="rasm.png", content_type="application/x-mine")
    assert d["response"]["headers"]["Content-Type"] == "application/x-mine"
    d = run(client, url=echo + "/echo", method="POST", body_file="files/" + "1" * 64 + "/yoq.bin", body_file_name="yoq.bin")
    assert d["status"] == "ERR" and "Fayl topilmadi: yoq.bin" in d["response"]


def test_batch_run_resolves_file_refs_too(run_batch, client, echo):
    f = upload(client, "b.txt", b"batch")
    results, _ = run_batch(dict(url=echo + "/echo", method="POST", body_type="multipart", rows=[{}],
                                multipart_fields=[{"name": "d", "type": "file", "files": [{"ref": f["ref"], "name": "b.txt"}]}]))
    assert results[0]["status"] == 200


# ── migratsiya ──
def old_item(upload_path, query_text=True):
    legacy = {"id": "r1", "name": "Yuklash", "method": "POST", "url": "http://h/up", "headers": [], "body": '{"ignored": true}', "body_type": "json",
              "params": [{"name": "q", "value": "1"}, {"name": "doc", "value": f"{upload_path}::ariza.pdf", "type": "file"}]}
    return legacy


def seed_schema2(tmp_path, upload_path):
    ws = Workspace(str(tmp_path / "w"))
    from apirunner.storage import model
    col = model.new_collection("Eski")
    col["item"] = [model.legacy_to_request_item(old_item(upload_path))]
    ws.save_collection(col)
    meta = ws.meta()
    meta["schemaVersion"] = 2
    from apirunner.storage.atomic import atomic_write_json
    atomic_write_json(os.path.join(ws.root, "workspace.json"), meta)
    w2 = Workspace(ws.root)
    return w2, w2.list_collections()[0]["id"]


def test_migration_moves_params_file_rows_to_body_formdata_with_backup(tmp_path):
    up = tmp_path / "up.bin"
    up.write_bytes(b"PDF!")
    ws, cid = seed_schema2(tmp_path, up)
    r = migrations.run_all(ws, None, str(tmp_path / "backups"), "9")
    assert r["status"] == "ok" and r["backup"] and r["before"] == r["after"]       # hech narsa yo'qolmadi
    it = Workspace(ws.root).get_collection(cid)["item"][0]
    req = it["request"]
    assert [q["key"] for q in req["url"]["query"]] == ["q"] and "doc" not in req["url"].get("raw", "")   # matnli parametr query'da qoldi
    fd = req["body"]["formdata"]
    assert req["body"]["mode"] == "formdata" and len(fd) == 1 and fd[0]["key"] == "doc" and fd[0]["type"] == "file"
    ref = fd[0]["src"][0]
    assert ref.startswith("files/") and ref.endswith("/ariza.pdf")
    assert open(files.resolve(ws.root, ref), "rb").read() == b"PDF!"              # fayl workspace ichida; asl o'chirilmadi
    assert up.exists()
    assert it["x-apirunner"]["files_migrated"] and json.loads(json.dumps(it["x-apirunner"]["pre_files_body"]))["raw"] == '{"ignored": true}'
    assert it["x-apirunner"]["legacy"]["params"][1]["type"] == "file"             # asl yozuv tegilmadi
    # zaxirada asl holat bor
    saved = [p for p in os.listdir(os.path.join(r["backup"], "workspace", "collections"))]
    assert saved
    again = migrations.run_all(Workspace(ws.root), None, str(tmp_path / "backups"), "9")
    assert again["status"] == "nothing"                                             # idempotent


def test_migration_keeps_missing_file_as_external_ref_and_is_idempotent_per_item(tmp_path):
    ws, cid = seed_schema2(tmp_path, tmp_path / "yoq.bin")
    migrations.step_2_to_3(ws)
    migrations.step_2_to_3(ws)                                                       # qayta ishga tushirish dublikat yaratmaydi
    fd = ws.get_collection(cid)["item"][0]["request"]["body"]["formdata"]
    assert len(fd) == 1 and fd[0]["src"] == [str(tmp_path / "yoq.bin")]


def test_migrated_request_sends_exactly_what_the_old_one_did(client, echo, isolated):
    """Xarakteristika: eski usul (params type=file) va migratsiyadan keyingi (Body form-data) bir xil so'rov yuboradi."""
    up = isolated / "uploads" / "u.bin"
    up.write_bytes(b"CONTENT")
    old = run(client, url=echo + "/echo", method="POST", params=[{"name": "q", "value": "1"}, {"name": "doc", "value": f"{up}::ariza.pdf", "type": "file"}])
    ws = client.application.extensions["workspace"]
    item = {"request": {"method": "POST", "url": {"raw": echo + "/echo?q=1&doc=x", "query": [{"key": "q", "value": "1"}, {"key": "doc", "value": f"{up}::ariza.pdf"}]}},
            "x-apirunner": {"legacy": {"params": [{"name": "doc", "value": f"{up}::ariza.pdf", "type": "file"}]}}}
    assert migrations.migrate_item_files(ws, item)
    fd = item["request"]["body"]["formdata"]
    new = run(client, url=echo + "/echo", method="POST", params=[{"name": "q", "value": "1"}], body_type="multipart", multipart_fields=[
        {"name": f["key"], "type": "file", "files": [{"ref": r, "name": files.parse_ref(r)[2]} for r in f["src"]]} for f in fd])
    keep = lambda d: {"method": d["response"]["method"], "args": d["response"]["args"], "form": d["response"]["form"], "files": d["response"]["files"]}  # noqa: E731
    assert keep(old) == keep(new) and new["response"]["files"]["doc"] == {"filename": "ariza.pdf", "content": "CONTENT"}
