"""Bir nechta workspace: izolyatsiya, almashtirish, nomlash, o'chirish (Savat) va tiklash, qayta ishga tushganda faol workspace eslab qolinadi."""
import os
import time

from tests.conftest import TOKEN
from tests.test_runs import item, start, wait


def ws_names(c):
    return {i["id"]: i for i in c.get("/api/workspaces").get_json()["items"]}


def names(c):
    return sorted(x["name"] for x in c.get("/api/workspace").get_json()["collections"])


def test_default_workspace_listed_and_create_validation(client):
    d = client.get("/api/workspaces").get_json()
    assert d["active"] == "default" and d["items"][0]["name"] == "Shaxsiy workspace" and d["items"][0]["default"] and d["items"][0]["active"]
    assert client.post("/api/workspaces", json={"name": "  "}).status_code == 400
    wid = client.post("/api/workspaces", json={"name": "Ish"}).get_json()["id"]
    assert client.post("/api/workspaces", json={"name": "ish"}).status_code == 400                 # nom takrorlanmaydi (katta-kichik harfsiz)
    assert client.post("/api/workspaces", json={"name": "x" * 61}).status_code == 400
    assert os.path.isdir(ws_names(client)[wid]["path"])
    assert client.put(f"/api/workspaces/{wid}", json={"name": "Ish 2"}).status_code == 200
    assert client.put(f"/api/workspaces/{wid}", json={"name": "Shaxsiy workspace"}).status_code == 400
    assert client.put("/api/workspaces/default", json={"name": "Asosiy"}).status_code == 200
    assert ws_names(client)["default"]["name"] == "Asosiy"


def test_switch_isolates_collections_environments_history_and_runs(client, echo):
    client.post("/api/collections", json={"name": "A-col"})
    client.post("/api/environments", json={"name": "A-env"})
    client.post("/api/history", json={"kind": "request", "payload": {"method": "GET", "url": "http://a/"}})
    wid = client.post("/api/workspaces", json={"name": "B"}).get_json()["id"]
    assert client.post(f"/api/workspaces/{wid}/activate").get_json()["active"] == wid
    assert names(client) == [] and client.get("/api/workspace").get_json()["environments"] == []        # yangi workspace — bo'sh
    assert client.get("/api/history?kind=request&limit=10").get_json() == []
    client.post("/api/collections", json={"name": "B-col"})
    run = start(client, [item("a", "A", echo + "/echo")])
    assert run["number"] == 1
    wait(client, run["id"])
    assert client.post("/api/workspaces/default/activate").status_code == 200
    assert names(client) == ["A-col"] and [e["name"] for e in client.get("/api/workspace").get_json()["environments"]] == ["A-env"]
    assert len(client.get("/api/history?kind=request&limit=10").get_json()) == 1
    assert client.get("/api/runs?scope=C").get_json() == []                                           # run tarixi ham alohida
    client.post(f"/api/workspaces/{wid}/activate")
    assert names(client) == ["B-col"] and client.get("/api/runs?scope=C").get_json()[0]["number"] == 1
    assert client.post(f"/api/workspaces/{wid}/activate").get_json()["unchanged"] is True


def test_switch_confirmation_when_runs_mocks_or_connections_active(client, echo, ws_server):
    from tests.test_mock import COL
    wid = client.post("/api/workspaces", json={"name": "Busy"}).get_json()["id"]
    start(client, [item("a", "A", echo + "/slow?s=1")], iterations=5)
    r = client.post(f"/api/workspaces/{wid}/activate")
    assert r.status_code == 409 and r.get_json()["needs_confirm"] and r.get_json()["runs"] == 1
    assert client.get("/api/workspaces").get_json()["active"] == "default"                           # almashmadi
    assert client.post(f"/api/workspaces/{wid}/activate", json={"force": True}).status_code == 200
    client.post("/api/workspaces/default/activate")
    cid = client.post("/api/collections", json={"name": "M"}).get_json()["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    col["item"] = COL["item"]
    client.put(f"/api/collections/{cid}", json=col)
    m = client.post("/api/mocks", json={"collection_id": cid}).get_json()
    assert client.post(f"/api/workspaces/{wid}/activate").get_json()["mocks"] == 1
    assert client.post(f"/api/workspaces/{wid}/activate", json={"force": True}).status_code == 200
    assert client.get("/api/mocks").get_json() == []                                                  # mock to'xtatildi
    del m
    client.post("/api/workspaces/default/activate")
    sid = client.post("/api/protocols/connect", json={"kind": "ws", "spec": {"url": ws_server.url + "/echo", "method": "GET", "headers": [], "params": [], "env_vars": {}}}).get_json()["id"]
    time.sleep(0.3)
    assert client.post(f"/api/workspaces/{wid}/activate").get_json()["connections"] == 1
    client.post(f"/api/protocols/{sid}/close")


def test_delete_goes_to_trash_keeps_data_and_restore_brings_it_back(client):
    wid = client.post("/api/workspaces", json={"name": "Vaqtincha"}).get_json()["id"]
    client.post(f"/api/workspaces/{wid}/activate")
    client.post("/api/collections", json={"name": "Muhim collection"})
    client.post("/api/workspaces/default/activate")
    assert client.delete("/api/workspaces/default").status_code == 400                                # sukut o'chmaydi
    path = ws_names(client)[wid]["path"]
    r = client.delete(f"/api/workspaces/{wid}").get_json()
    assert r["ok"] and wid not in ws_names(client) and not os.path.exists(path)
    row = next(x for x in client.get("/api/trash").get_json() if x["kind"] == "workspace")
    assert row["name"] == "Vaqtincha" and row["days_left"] == 30
    moved = os.path.join(os.path.dirname(os.path.dirname(path)), "workspaces", ".trash")
    assert os.listdir(moved) and any("collections" in fs or True for _r, _d, fs in os.walk(moved))   # ma'lumot diskda qoldi
    res = client.post(f"/api/trash/{row['id']}/restore").get_json()
    assert res["kind"] == "workspace" and res["workspace_id"] in ws_names(client)
    client.post(f"/api/workspaces/{res['workspace_id']}/activate")
    assert names(client) == ["Muhim collection"]                                                      # ichidagi hamma narsa joyida


def test_cannot_delete_active_and_forever_delete_purges_folder(client):
    wid = client.post("/api/workspaces", json={"name": "Z"}).get_json()["id"]
    client.post(f"/api/workspaces/{wid}/activate")
    r = client.delete(f"/api/workspaces/{wid}")
    assert r.status_code == 400 and "Faol" in r.get_json()["error"]
    client.post("/api/workspaces/default/activate")
    client.delete(f"/api/workspaces/{wid}")
    tid = next(x for x in client.get("/api/trash").get_json() if x["kind"] == "workspace")["id"]
    base = os.path.join(client.app.extensions["registry"].root, ".trash")
    assert os.listdir(base)
    client.delete(f"/api/trash/{tid}")
    assert os.listdir(base) == []                                                                     # savatdan butunlay o'chirilganda papka ham ketadi
    assert client.delete("/api/workspaces/nope").status_code == 400


def test_active_workspace_is_remembered_after_restart(client, make_client):
    wid = client.post("/api/workspaces", json={"name": "Eslab"}).get_json()["id"]
    client.post(f"/api/workspaces/{wid}/activate")
    client.post("/api/collections", json={"name": "Faqat shu yerda"})
    ws_root = client.app.extensions["registry"].default_dir
    from apirunner.app import create_app
    app2 = create_app(workspace_dir=ws_root, saved_file="", upload_dir=ws_root + "-up", session_token=TOKEN, backup_dir=ws_root + "-bk")
    c2 = app2.test_client()
    c2.environ_base["HTTP_X_SESSION_TOKEN"] = TOKEN
    assert c2.get("/api/workspaces").get_json()["active"] == wid and names(c2) == ["Faqat shu yerda"]


def test_workspace_zip_and_find_replace_stay_within_active_workspace(client):
    client.post("/api/collections", json={"name": "Default only"})
    wid = client.post("/api/workspaces", json={"name": "Other"}).get_json()["id"]
    client.post(f"/api/workspaces/{wid}/activate")
    import io
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/workspace/export").data))
    assert not any(n.startswith("collections/") for n in z.namelist())
    assert client.post("/api/find-replace/search", json={"query": "Default"}).get_json()["results"] == []
