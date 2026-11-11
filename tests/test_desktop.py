"""Desktop rejim: loopback, home, birinchi ishga tushishdagi tanlov (use/copy/fresh), sessiya qulfi, workspace papkasini o'zgartirish."""
import json
import os

import pytest
import requests

from apirunner import desktop
from apirunner.storage import instance
from tests.conftest import TOKEN


def make_ws(path, n=2):
    os.makedirs(os.path.join(path, "collections"))
    json.dump({"schemaVersion": 1}, open(os.path.join(path, "workspace.json"), "w"))
    for i in range(n):
        json.dump({"info": {"name": f"C{i}"}, "item": []}, open(os.path.join(path, "collections", f"c{i}.json"), "w"))
    open(os.path.join(path, ".lock"), "w").close()
    return str(path)


def test_start_server_uses_given_home_and_loopback(tmp_path):
    url, stop, app = desktop.start_server(str(tmp_path / "home"))
    try:
        assert url.startswith("http://127.0.0.1:")
        assert requests.get(url + "/").status_code == 200
        assert requests.get(url + "/api/workspace").status_code == 401
        assert os.path.isdir(tmp_path / "home" / "workspace")
        info = requests.get(url + "/api/desktop", headers={"X-Session-Token": app.config["SESSION_TOKEN"]}).json()
        assert info["desktop"] and info["home"] == str(tmp_path / "home")
    finally:
        stop()


def test_default_home_is_overridable(monkeypatch, tmp_path):
    monkeypatch.setenv("APIRUNNER_HOME", str(tmp_path))
    assert desktop.default_home() == str(tmp_path)


def test_candidates_found_via_env_and_exclude_own_and_nonworkspaces(monkeypatch, tmp_path):
    old = make_ws(tmp_path / "old")
    monkeypatch.setenv("APIRUNNER_LEGACY_WORKSPACE", old)
    monkeypatch.setattr(desktop, "_pm2_cwd", lambda: None)
    monkeypatch.setattr(desktop, "hint_workspace", lambda: str(tmp_path / "nonexistent"))
    c = desktop.find_candidates(str(tmp_path / "home"))
    assert [x["path"] for x in c] == [old] and c[0]["collections"] == 2 and c[0]["holder"] is None
    monkeypatch.setenv("APIRUNNER_LEGACY_WORKSPACE", str(tmp_path / "home" / "workspace"))
    assert desktop.find_candidates(str(tmp_path / "home")) == []


def test_choice_copy_leaves_source_untouched_and_skips_lock_files(tmp_path):
    src = make_ws(tmp_path / "src")
    open(os.path.join(src, ".session.lock"), "w").close()
    before = sorted(os.listdir(src))
    cfg = desktop.apply_choice(str(tmp_path / "home"), "copy", src)
    dst = cfg["workspace_dir"]
    assert dst == str(tmp_path / "home" / "workspace") and sorted(os.listdir(os.path.join(dst, "collections"))) == ["c0.json", "c1.json"]
    assert not os.path.exists(os.path.join(dst, ".session.lock")) and not os.path.exists(os.path.join(dst, ".lock"))
    assert sorted(os.listdir(src)) == before and desktop.load_config(str(tmp_path / "home"))["mode"] == "copy"
    with pytest.raises(ValueError):
        desktop.apply_choice(str(tmp_path / "home"), "copy", src)                 # nusxa papkasi band — ustiga yozilmaydi


def test_choice_use_points_at_source_with_sibling_backups_and_fresh_uses_home(tmp_path):
    src = make_ws(tmp_path / "repo" / "workspace")
    cfg = desktop.apply_choice(str(tmp_path / "home"), "use", src)
    p = desktop.paths_for(str(tmp_path / "home"), cfg)
    assert p["workspace_dir"] == src and p["backup_dir"] == str(tmp_path / "repo" / "backups") and p["saved_file"] == ""
    cfg = desktop.apply_choice(str(tmp_path / "home2"), "fresh")
    assert desktop.paths_for(str(tmp_path / "home2"), cfg)["workspace_dir"] == str(tmp_path / "home2" / "workspace")
    with pytest.raises(ValueError):
        desktop.apply_choice(str(tmp_path / "home3"), "use", str(tmp_path / "nothing"))


def test_chooser_html_escapes_paths_and_warns_about_open_workspace():
    h = desktop.chooser_html([{"path": "/x/<b>y</b>", "label": "L", "collections": 3, "holder": {"pid": 123, "version": "2.9.0"}}])
    assert "&lt;b&gt;" in h and "<b>y</b>" not in h and "pid 123" in h and "Nusxa olish" in h and "boshqa API Runner nusxasida ochiq" in h


def test_session_lock_detects_second_instance(tmp_path, monkeypatch):
    monkeypatch.setenv("APIRUNNER_INSTANCE_LOCK", "1")
    a = instance.InstanceLock(str(tmp_path), "3.0.1", "server")
    assert a.owned and instance.probe(str(tmp_path))["version"] == "3.0.1"
    b = instance.InstanceLock(str(tmp_path), "2.9.0", "desktop")
    assert not b.owned and b.as_json()["conflict"] and b.holder["pid"] == os.getpid()
    a.release()
    assert instance.probe(str(tmp_path)) is None
    c = instance.InstanceLock(str(tmp_path), "3.0.1", "server")
    assert c.owned
    c.release()


def test_instance_api_reports_conflict(isolated, make_client, monkeypatch):
    monkeypatch.setenv("APIRUNNER_INSTANCE_LOCK", "1")
    c1 = make_client()
    assert c1.get("/api/instance").get_json()["conflict"] is False
    from apirunner.app import create_app
    app2 = create_app(workspace_dir=str(isolated / "workspace"), saved_file=str(isolated / "s2.json"), upload_dir=str(isolated / "uploads"), session_token=TOKEN, backup_dir=str(isolated / "backups"))
    c2 = app2.test_client()
    c2.environ_base["HTTP_X_SESSION_TOKEN"] = TOKEN
    j = c2.get("/api/instance").get_json()
    assert j["conflict"] is True and j["holder"]["pid"] == os.getpid()


def test_set_workspace_folder_api(tmp_path):
    url, stop, app = desktop.start_server(str(tmp_path / "home"))
    h = {"X-Session-Token": app.config["SESSION_TOKEN"]}
    try:
        put = lambda p: requests.put(url + "/api/desktop/workspace", json={"workspace_dir": p}, headers=h)  # noqa: E731
        assert put("relative/path").status_code == 400
        full = tmp_path / "full"
        full.mkdir()
        (full / "x.txt").write_text("1")
        assert put(str(full)).status_code == 400                                   # bo'sh emas va workspace emas
        existing = make_ws(tmp_path / "other")
        r = put(existing)
        assert r.status_code == 200 and r.json()["restart_required"] and desktop.load_config(str(tmp_path / "home"))["workspace_dir"] == existing
        assert put(str(tmp_path / "newempty")).status_code == 200
    finally:
        stop()


def test_set_workspace_folder_rejected_outside_desktop_mode(client):
    assert client.put("/api/desktop/workspace", json={"workspace_dir": "/tmp/x"}).status_code == 400
    assert client.get("/api/desktop").get_json()["desktop"] is False
