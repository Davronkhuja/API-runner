"""Server qayta ishga tushirish (/api/admin/restart) va versiya ma'lumoti: PM2'siz, chiqish funksiyasi mock bilan."""
import time

from tests.test_runs import item, start


def hook(client, managed=True):
    calls = []
    client.app.config["RESTART_MANAGED"] = managed
    client.app.extensions["exit_fn"] = lambda code: calls.append(code)
    return calls


def test_version_reports_server_ui_managed_and_active(client):
    d = client.get("/api/version").get_json()
    assert set(d) >= {"version", "ui_version", "started", "managed", "active"} and d["active"] == 0


def test_restart_requires_token_and_host(client):
    hook(client)
    anon = client.application.test_client()
    assert anon.post("/api/admin/restart").status_code == 401
    assert client.post("/api/admin/restart", headers={"Host": "evil.example"}).status_code == 403


def test_restart_not_managed_gives_instruction_and_does_not_exit(client):
    calls = hook(client, managed=False)
    r = client.post("/api/admin/restart")
    assert r.status_code == 409 and r.get_json()["managed"] is False and "run.command" in r.get_json()["error"]
    time.sleep(0.6)
    assert calls == []


def test_restart_idle_flushes_and_exits(client):
    calls = hook(client)
    r = client.post("/api/admin/restart")
    assert r.status_code == 200 and r.get_json()["ok"] is True
    for _ in range(40):
        if calls:
            break
        time.sleep(0.05)
    assert calls == [0]


def test_restart_with_active_run_needs_confirmation_then_force_stops_it(client, echo):
    calls = hook(client)
    d = start(client, [item("a", "A", echo + "/slow?s=0.5")], iterations=20)
    r = client.post("/api/admin/restart")
    assert r.status_code == 409 and r.get_json()["needs_confirm"] is True and r.get_json()["active_runs"] == 1
    time.sleep(0.6)
    assert calls == []                                   # tasdiqsiz chiqmaydi
    r = client.post("/api/admin/restart", json={"force": True})
    assert r.status_code == 200 and r.get_json()["stopped_runs"] == 1
    run = client.get(f"/api/runs/{d['id']}").get_json()
    assert run["status"] != "running"                    # run to'xtatilib, natijalar SQLite'da qoldi
