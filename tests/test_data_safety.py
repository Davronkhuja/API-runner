"""Ma'lumotlar xavfsizligi qoidalari (har biri uchun test). Hamma narsa tmp_path ichida — haqiqiy fayllarga tegmaydi."""
import hashlib
import json
import multiprocessing
import os
import sqlite3
import threading

import pytest

from apirunner.app import create_app
from apirunner.storage import backup as bk
from apirunner.storage import migrations, tree_ops
from apirunner.storage.atomic import atomic_write_json
from apirunner.storage.db import StateDB
from apirunner.storage.restore import main as restore_main
from apirunner.storage.workspace import CURRENT_SCHEMA, Conflict, Workspace

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "saved_requests.anonymized.json")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def tree_snapshot(root):
    """Katalog mazmuni (SQLite'siz): {nisbiy yo'l: sha}."""
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            if f.endswith((".tmp", "state.db-wal", "state.db-shm")) or f in ("state.db", ".lock"):
                continue
            p = os.path.join(d, f)
            out[os.path.relpath(p, root)] = sha(p)
    return out


def app_for(tmp, saved_text=None, name="w"):
    saved = tmp / "saved_requests.json"
    if saved_text is not None:
        saved.write_text(saved_text, encoding="utf-8")
    return create_app(workspace_dir=str(tmp / name), saved_file=str(saved), upload_dir=str(tmp / "up"),
                      session_token="t", backup_dir=str(tmp / "backups"))


# ───────────── 1) haqiqiy ma'lumotga tegmaslik ─────────────
def test_create_app_requires_explicit_paths_under_testing(isolated):
    with pytest.raises(RuntimeError, match="APIRUNNER_TESTING"):
        create_app(workspace_dir=str(isolated / "w"))


def test_fixtures_live_in_tmp(isolated, client):
    assert str(isolated).startswith(("/private/var", "/tmp", "/var", "/private/tmp")) or "pytest" in str(isolated)
    assert client.app.extensions["backup_dir"].startswith(str(isolated))


# ───────────── 3) atomik yozuv ─────────────
def test_atomic_write_crash_keeps_original_and_leaves_no_tmp(tmp_path, monkeypatch):
    p = tmp_path / "data.json"
    atomic_write_json(str(p), {"v": 1})
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk uzildi")))
    with pytest.raises(OSError):
        atomic_write_json(str(p), {"v": 2, "big": "x" * 10000})
    monkeypatch.undo()
    assert json.loads(p.read_text()) == {"v": 1}
    assert [f for f in os.listdir(tmp_path) if f.endswith(".tmp")] == []


def test_atomic_write_serialization_error_keeps_original(tmp_path):
    p = tmp_path / "d.json"
    atomic_write_json(str(p), {"ok": 1})
    with pytest.raises(TypeError):
        atomic_write_json(str(p), {"bad": object()})
    assert json.loads(p.read_text()) == {"ok": 1} and os.listdir(tmp_path) == ["d.json"]


def test_workspace_writes_use_atomic_path(tmp_path, monkeypatch):
    calls = []
    import apirunner.storage.workspace as w
    real = w.atomic_write_json
    monkeypatch.setattr(w, "atomic_write_json", lambda p, d: (calls.append(p), real(p, d))[1])
    ws = Workspace(str(tmp_path / "w"))
    ws.save_globals({"values": []})
    assert any(c.endswith("globals.json") for c in calls)


def test_sqlite_runs_in_wal_mode(tmp_path):
    db = StateDB(str(tmp_path / "s.db"))
    assert db.journal_mode().lower() == "wal"
    db.add_history("url", "http://x")
    assert db.journal_mode().lower() == "wal"


def test_sqlite_concurrent_writers(tmp_path):
    db = StateDB(str(tmp_path / "s.db"))
    errs = []

    def w(i):
        try:
            for j in range(30):
                db.add_history("url", f"u{i}-{j}")
        except Exception as e:   # noqa: BLE001
            errs.append(e)
    ts = [threading.Thread(target=w, args=(i,)) for i in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errs and db.count_history() == 180


# ───────────── 3b) bir vaqtda yozish ─────────────
from tests._mp_worker import adds as _proc_adds  # noqa: E402


def test_concurrent_threads_do_not_lose_updates(tmp_path):
    ws = Workspace(str(tmp_path / "w"))
    from apirunner.storage import model
    cid = ws.save_collection(model.new_collection("C"))
    ts = [threading.Thread(target=_proc_adds, args=(ws.root, cid, f"t{i}", 15)) for i in range(5)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(ws.get_collection(cid)["item"]) == 75


def test_concurrent_processes_do_not_lose_updates(tmp_path):
    ws = Workspace(str(tmp_path / "w"))
    from apirunner.storage import model
    cid = ws.save_collection(model.new_collection("C"))
    ctx = multiprocessing.get_context("spawn")      # fork Playwright oqimlari bilan osilib qoladi
    ps = [ctx.Process(target=_proc_adds, args=(ws.root, cid, f"p{i}", 12)) for i in range(4)]
    [p.start() for p in ps]
    [p.join(60) for p in ps]
    assert all(p.exitcode == 0 for p in ps)
    assert len(ws.get_collection(cid)["item"]) == 48
    assert ws.get_collection(cid)["x-apirunner"]["rev"] == 49          # har yozuvda rev +1 (1 boshlang'ich + 48)


def test_stale_rev_put_is_rejected_with_409(client):
    cid = client.post("/api/collections", json={"name": "C"}).get_json()["id"]
    a = client.get(f"/api/collections/{cid}").get_json()       # tab A
    b = client.get(f"/api/collections/{cid}").get_json()       # tab B (bir xil rev)
    a["item"].append({"id": "x", "name": "from-A", "request": {"method": "GET", "url": {"raw": "u"}}, "response": []})
    assert client.put(f"/api/collections/{cid}", json=a).status_code == 200
    b["item"].append({"id": "y", "name": "from-B", "request": {"method": "GET", "url": {"raw": "u"}}, "response": []})
    r = client.put(f"/api/collections/{cid}", json=b)
    assert r.status_code == 409 and r.get_json()["conflict"] is True
    assert [i["id"] for i in client.get(f"/api/collections/{cid}").get_json()["item"]] == ["x"]       # A yo'qolmadi


def test_stale_rev_environment_and_globals(client):
    eid = client.post("/api/environments", json={"name": "E"}).get_json()["id"]
    a = client.get(f"/api/environments/{eid}").get_json()
    b = client.get(f"/api/environments/{eid}").get_json()
    assert client.put(f"/api/environments/{eid}", json=a).status_code == 200
    assert client.put(f"/api/environments/{eid}", json=b).status_code == 409
    g1 = client.get("/api/globals").get_json()
    g2 = client.get("/api/globals").get_json()
    assert client.put("/api/globals", json=g1).status_code == 200
    assert client.put("/api/globals", json=g2).status_code == 409


# ───────────── 2) zaxira ─────────────
def make_ws_with_data(tmp):
    ws = Workspace(str(tmp / "w"))
    from apirunner.storage import model
    ws.save_collection(model.new_collection("C"))
    ws.save_environment(model.new_environment("E"))
    db = StateDB(os.path.join(ws.root, "state.db"))
    db.add_history("url", "http://x")
    return ws


def test_backup_contains_saved_workspace_and_consistent_sqlite(tmp_path):
    ws = make_ws_with_data(tmp_path)
    saved = tmp_path / "saved_requests.json"
    saved.write_text('{"folders": [], "requests": []}')
    path = bk.create_backup(ws.root, str(saved), "9.9.9", str(tmp_path / "backups"))
    assert os.path.basename(path).endswith("_v9.9.9") and bk.NAME_RE.match(os.path.basename(path))
    assert sha(os.path.join(path, "saved_requests.json")) == sha(str(saved))
    assert tree_snapshot(os.path.join(path, "workspace")) == tree_snapshot(ws.root)
    c = sqlite3.connect(os.path.join(path, "workspace", "state.db"))
    assert c.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 1
    c.close()
    assert json.load(open(os.path.join(path, "manifest.json")))["version"] == "9.9.9"
    assert not [n for n in os.listdir(tmp_path / "backups") if n.endswith(".partial")]


def test_backup_prunes_to_20_only_after_new_one_exists_and_only_own_dirs(tmp_path):
    ws = make_ws_with_data(tmp_path)
    bdir = tmp_path / "backups"
    bdir.mkdir()
    # 23 ta eski zaxira (nomlari andozaga mos) + begona narsalar
    for i in range(23):
        d = bdir / f"20200101-0000{i:02d}_v1.0.{i}"
        d.mkdir()
        (d / "manifest.json").write_text("{}")
    (bdir / "mening_qo'lda_zaxiram").mkdir()
    (bdir / "mening_qo'lda_zaxiram" / "muhim.txt").write_text("saqla")
    (bdir / "notes.txt").write_text("saqla")
    other = tmp_path / "boshqa"
    other.mkdir()
    (bdir / "20200101-000000_v0.0.1x").symlink_to(other, target_is_directory=True)
    new = bk.create_backup(ws.root, None, "2.0.0", str(bdir))
    names = [b["name"] for b in bk.list_backups(str(bdir))]
    assert len(names) == 20 and os.path.basename(new) == names[0]
    assert "20200101-000000_v1.0.0" not in names and "20200101-000022_v1.0.22" in names     # eng eskilari o'chdi
    assert (bdir / "mening_qo'lda_zaxiram" / "muhim.txt").read_text() == "saqla"             # begona papka tegilmagan
    assert (bdir / "notes.txt").exists() and other.exists()                                   # symlink nishoni tegilmagan


def test_failed_backup_deletes_nothing_old(tmp_path, monkeypatch):
    ws = make_ws_with_data(tmp_path)
    bdir = tmp_path / "backups"
    for i in range(20):
        (bdir / f"20200101-0000{i:02d}_v1").mkdir(parents=True)
    monkeypatch.setattr(bk, "_copy_db", lambda *a: (_ for _ in ()).throw(OSError("db nusxa olinmadi")))
    with pytest.raises(OSError):
        bk.create_backup(ws.root, None, "2", str(bdir))
    assert len(bk.list_backups(str(bdir))) == 20            # yangisi yaratilmadi → eskilari o'chirilmadi
    assert not [n for n in os.listdir(bdir) if n.endswith(".partial")]


# ───────────── 2) migratsiya: idempotentlik, sonlar, rollback ─────────────
def test_new_workspace_has_current_schema_version(tmp_path):
    assert Workspace(str(tmp_path / "w")).schema_version() == CURRENT_SCHEMA


def test_old_workspace_without_schema_version_gets_migrated_with_backup(tmp_path):
    ws = make_ws_with_data(tmp_path)
    meta = ws.meta()
    meta.pop("schemaVersion")
    atomic_write_json(os.path.join(ws.root, "workspace.json"), meta)
    # eski sxema: hash ustunisiz baza
    os.remove(os.path.join(ws.root, "state.db"))
    c = sqlite3.connect(os.path.join(ws.root, "state.db"))
    c.executescript("CREATE TABLE history (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, ts REAL NOT NULL, payload TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'app');"
                    "INSERT INTO history(kind, ts, payload, source) VALUES ('url', 1, '\"http://a\"', 'localstorage'), ('url', 2, '\"http://a\"', 'localstorage'), ('url', 3, '\"http://b\"', 'app');")
    c.commit()
    c.close()
    r = migrations.run_all(Workspace(ws.root), None, str(tmp_path / "backups"), "9")
    assert r["status"] == "ok" and r["backup"] and os.path.isdir(r["backup"])
    assert Workspace(ws.root).schema_version() == CURRENT_SCHEMA
    c = sqlite3.connect(os.path.join(ws.root, "state.db"))
    rows = c.execute("SELECT source, hash FROM history ORDER BY id").fetchall()
    c.close()
    assert len(rows) == 3                                                    # hech narsa o'chmadi
    assert rows[0][1] is not None and rows[1][1] is None and rows[2][1] is None     # takroriy xeshsiz qoldi, 'app' tegilmadi
    again = migrations.run_all(Workspace(ws.root), None, str(tmp_path / "backups"), "9")
    assert again["status"] == "nothing" and again["backup"] is None          # idempotent: qayta zaxira ham olinmaydi


def test_step_is_idempotent_when_run_twice_directly(tmp_path):
    ws = make_ws_with_data(tmp_path)
    migrations.step_1_to_2(ws)
    migrations.step_1_to_2(ws)
    c = sqlite3.connect(os.path.join(ws.root, "state.db"))
    assert c.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 1
    c.close()


def test_failed_schema_step_rolls_back_to_backup(tmp_path):
    ws = make_ws_with_data(tmp_path)
    meta = ws.meta()
    meta["schemaVersion"] = 1
    atomic_write_json(os.path.join(ws.root, "workspace.json"), meta)
    before = tree_snapshot(ws.root)

    def evil(w):
        w.update_meta(corrupted=True)
        from apirunner.storage import model
        w.save_collection(model.new_collection("YARIM"))          # yarim qolgan o'zgarish
        raise RuntimeError("migratsiya o'rtasida xato")
    r = migrations.run_all(ws, None, str(tmp_path / "backups"), "9", steps={1: evil}, current=2)
    assert r["status"] == "rolled_back" and "tiklandi" in r["message"]
    assert tree_snapshot(ws.root) == before                       # to'liq qaytdi
    assert Workspace(ws.root).schema_version() == 1 and not Workspace(ws.root).meta().get("corrupted")
    assert migrations.count_workspace(Workspace(ws.root)) == r["before"]


def test_count_mismatch_after_migration_triggers_rollback(tmp_path):
    ws = make_ws_with_data(tmp_path)
    meta = ws.meta()
    meta["schemaVersion"] = 1
    atomic_write_json(os.path.join(ws.root, "workspace.json"), meta)

    def lossy(w):                                                 # xatosiz, lekin env'ni yo'qotadi
        for e in w.list_environments():
            w.delete_environment(e["id"])
    r = migrations.run_all(ws, None, str(tmp_path / "backups"), "9", steps={1: lossy}, current=2)
    assert r["status"] == "rolled_back" and "environments soni mos emas" in r["message"]
    assert len(Workspace(ws.root).list_environments()) == 1


def test_missing_step_rolls_back(tmp_path):
    ws = make_ws_with_data(tmp_path)
    r = migrations.run_all(ws, None, str(tmp_path / "backups"), "9", steps={}, current=5)
    assert r["status"] == "rolled_back"


def test_rollback_surfaces_warning_in_status_endpoint(tmp_path, monkeypatch):
    """Legacy import xatosi → rollback → UI ogohlantirishi (/api/status) va saved_requests.json tegilmagan."""
    saved_text = json.dumps({"folders": [], "requests": [{"id": "r1", "name": "A"}]})
    saved = tmp_path / "saved_requests.json"
    saved.write_text(saved_text)
    before = sha(str(saved))
    import apirunner.storage.migrations as m
    monkeypatch.setattr(m, "migrate_saved_requests", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("import qulab ketdi")))
    app = app_for(tmp_path)
    c = app.test_client()
    c.environ_base["HTTP_X_SESSION_TOKEN"] = "t"
    st = c.get("/api/status").get_json()
    assert st["migration"]["status"] == "rolled_back" and "bekor qilindi" in st["migration"]["message"]
    assert sha(str(saved)) == before and not (tmp_path / "saved_requests.json.bak").exists()
    assert c.get("/saved").get_json() == {"folders": [], "requests": []}


# ───────────── anonimlashtirilgan haqiqiy fayl nusxasi bilan migratsiya ─────────────
def test_migration_with_anonymized_real_file(tmp_path):
    real_shape = json.load(open(FIXTURE))
    saved = tmp_path / "saved_requests.json"
    saved.write_text(open(FIXTURE, encoding="utf-8").read(), encoding="utf-8")
    h0 = sha(str(saved))
    app = app_for(tmp_path)
    res = app.config["MIGRATION_RESULT"]
    assert res["status"] == "ok" and res["legacy"] == "migrated"
    assert res["before"]["requests"] == 0 and res["after"]["requests"] == len(real_shape["requests"]) == 32
    assert res["after"]["folders"] == len(real_shape["folders"]) == 5
    assert sha(str(saved)) == h0                                              # asl fayl o'zgarmadi
    assert len(bk.list_backups(str(tmp_path / "backups"))) == 1
    assert sha(os.path.join(res["backup"], "saved_requests.json")) == h0
    c = app.test_client()
    c.environ_base["HTTP_X_SESSION_TOKEN"] = "t"
    got = c.get("/saved").get_json()
    assert got["folders"] == real_shape["folders"]
    assert {r["id"]: r for r in got["requests"]} == {r["id"]: r for r in real_shape["requests"]}   # yo'qotishsiz
    # qayta ishga tushirish: dublikat ham, yangi zaxira ham yo'q
    app2 = app_for(tmp_path)
    assert app2.config["MIGRATION_RESULT"]["status"] == "nothing"
    c2 = app2.test_client()
    c2.environ_base["HTTP_X_SESSION_TOKEN"] = "t"
    assert len(c2.get("/saved").get_json()["requests"]) == 32
    assert len(bk.list_backups(str(tmp_path / "backups"))) == 1
    assert sha(str(saved)) == h0


def test_legacy_records_without_ids_are_kept_not_dropped(tmp_path):
    app = app_for(tmp_path, json.dumps({"folders": [{"name": "F"}], "requests": [{"name": "A"}, {"name": "B"}]}))
    assert app.config["MIGRATION_RESULT"]["status"] == "ok"
    c = app.test_client()
    c.environ_base["HTTP_X_SESSION_TOKEN"] = "t"
    d = c.get("/saved").get_json()
    assert len(d["folders"]) == 1 and [r["name"] for r in d["requests"]] == ["A", "B"]


def test_original_saved_file_never_modified_even_after_edits(tmp_path):
    app = app_for(tmp_path, open(FIXTURE, encoding="utf-8").read())
    h0 = sha(str(tmp_path / "saved_requests.json"))
    c = app.test_client()
    c.environ_base["HTTP_X_SESSION_TOKEN"] = "t"
    c.post("/saved/folder", json={"name": "yangi"})
    c.post("/saved/request", json={"name": "yangi"})
    c.post("/api/backups")
    assert sha(str(tmp_path / "saved_requests.json")) == h0


# ───────────── 4) localStorage importi ─────────────
LS = {
    "apiRunnerEnvs": json.dumps([{"id": "e1", "name": "Prod", "vars": {"a": "1"}},
                                 {"id": "ed", "name": "Default", "vars": {"d1": "x", "d2": "y"}}]),
    "apiRunnerEnvVars": json.dumps({"legacy1": "z"}),
    "apiRunnerHistory": json.dumps([{"method": "GET", "url": "http://h1", "timestamp": 1700000000000}]),
    "apiRunnerUrlHistory": json.dumps(["http://a", "http://b"]),
}


def test_import_twice_creates_no_duplicates(client):
    s1 = client.post("/api/import/localstorage", json={"data": LS}).get_json()["stats"]
    s2 = client.post("/api/import/localstorage", json={"data": LS}).get_json()["stats"]
    assert s1["environments"] == 1 and s1["history"] == 1 and s1["url_history"] == 2
    assert s2["environments"] == 0 and s2["history"] == 0 and s2["url_history"] == 0 and s2["globals"] == 0
    ws = client.get("/api/workspace").get_json()
    assert len(ws["environments"]) == 1 and len(client.get("/api/history").get_json()) == 3
    assert [v["key"] for v in ws["globals"]["values"]].count("d1") == 1


def test_partial_overlap_import_adds_only_new_entries(client):
    client.post("/api/import/localstorage", json={"data": LS})
    more = dict(LS, apiRunnerUrlHistory=json.dumps(["http://a", "http://b", "http://NEW"]))
    s = client.post("/api/import/localstorage", json={"data": more}).get_json()["stats"]
    assert s["url_history"] == 1                                              # faqat yangisi


def test_default_env_and_legacy_vars_go_to_globals_with_flag(client):
    client.post("/api/import/localstorage", json={"data": LS})
    ws = client.get("/api/workspace").get_json()
    assert {v["key"] for v in ws["globals"]["values"]} == {"d1", "d2", "legacy1"}
    assert [e["name"] for e in ws["environments"]] == ["Prod"]                # "Default" env bo'lib qolmadi
    assert ws["meta"]["legacy_default_migrated"] is True
    client.put("/api/workspace/meta", json={"legacy_default_notified": True})
    assert client.get("/api/status").get_json()["meta"]["legacy_default_notified"] is True


def test_import_never_overwrites_existing_global_value(client):
    g = client.get("/api/globals").get_json()
    g["values"] = [{"key": "d1", "value": "MENIKI", "enabled": True, "type": "default"}]
    client.put("/api/globals", json=g)
    client.post("/api/import/localstorage", json={"data": LS})
    vals = {v["key"]: v["value"] for v in client.get("/api/globals").get_json()["values"]}
    assert vals["d1"] == "MENIKI" and vals["d2"] == "y"


# ───────────── 5) tiklash ─────────────
def test_restore_function_backs_up_current_first_and_leaves_saved_file(tmp_path):
    app = app_for(tmp_path, open(FIXTURE, encoding="utf-8").read())
    ws = app.extensions["workspace"]
    c = app.test_client()
    c.environ_base["HTTP_X_SESSION_TOKEN"] = "t"
    first = c.post("/api/backups").get_json()["name"]                         # holat A
    snapA = tree_snapshot(ws.root)
    c.post("/saved/request", json={"name": "FAQAT-KEYIN"})                    # holat B (zaxiradan keyin)
    snapB = tree_snapshot(ws.root)
    assert snapA != snapB
    h = sha(str(tmp_path / "saved_requests.json"))
    r = c.post("/api/backups/restore", json={"name": first}).get_json()
    assert r["ok"] and "pre-restore" in r["pre_restore"]
    assert tree_snapshot(ws.root) == snapA                                     # tiklandi
    pre = os.path.join(tmp_path, "backups", r["pre_restore"], "workspace")
    assert tree_snapshot(pre) == snapB                                         # joriy holat saqlangan edi
    assert sha(str(tmp_path / "saved_requests.json")) == h
    assert len(c.get("/saved").get_json()["requests"]) == 32                   # ilova tiklangan holatda ishlaydi


@pytest.mark.parametrize("name", ["../w", "../../etc", "", "nope", "20200101-000000_v1"])
def test_restore_rejects_bad_names(client, name):
    assert client.post("/api/backups/restore", json={"name": name}).status_code == 400


def test_restore_cli(tmp_path, capsys):
    app = app_for(tmp_path, open(FIXTURE, encoding="utf-8").read())
    ws = app.extensions["workspace"]
    name = os.path.basename(app.config["MIGRATION_RESULT"]["backup"])          # migratsiyadan oldingi (bo'sh) holat
    c = app.test_client()
    c.environ_base["HTTP_X_SESSION_TOKEN"] = "t"
    assert len(c.get("/saved").get_json()["requests"]) == 32
    rc = restore_main([name, "--workspace", ws.root, "--backups", str(tmp_path / "backups"), "--saved-file", str(tmp_path / "saved_requests.json")])
    assert rc == 0 and "Tiklandi" in capsys.readouterr().out
    assert migrations.count_workspace(Workspace(ws.root))["requests"] == 0
    assert any(b["suffix"] == "pre-restore" for b in bk.list_backups(str(tmp_path / "backups")))
    assert restore_main(["/etc", "--workspace", ws.root, "--backups", str(tmp_path / "backups")]) == 1


def test_backups_api_list_and_create(client):
    assert client.get("/api/backups").get_json() == []
    n = client.post("/api/backups").get_json()["name"]
    lst = client.get("/api/backups").get_json()
    assert [b["name"] for b in lst] == [n] and lst[0]["suffix"] == "manual" and "path" not in lst[0]
