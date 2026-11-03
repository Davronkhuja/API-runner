import json
import os

LEGACY = {
    "folders": [{"id": "f1", "name": "Auth", "expanded": False, "created_at": "2025-01-01T00:00:00"}],
    "requests": [
        {"id": "r1", "name": "Login", "method": "POST", "url": "https://x.io/login",
         "headers": [{"name": "X-A", "value": "1"}], "params": [{"name": "q", "value": "1"}],
         "body": '{"u":1}', "body_type": "json", "content_type": "application/json",
         "authorization": "Bearer abc", "folder_id": "f1", "created_at": "2025-01-02T00:00:00",
         "custom_future_field": {"keep": "me"}},
        {"id": "r2", "name": "Ping", "method": "GET", "url": "https://x.io/ping", "folder_id": None},
    ],
}


def test_migration_creates_collection_and_backup_and_keeps_original(isolated, make_client):
    saved = isolated / "saved_requests.json"
    text = json.dumps(LEGACY, ensure_ascii=False)
    c = make_client(text)
    assert c.app.config["MIGRATION"] == "migrated"
    assert saved.read_text() == text                         # asl fayl tegilmagan
    assert (isolated / "saved_requests.json.bak").read_text() == text
    col = json.loads((isolated / "workspace" / "collections" / "saved.json").read_text())
    assert col["info"]["schema"].endswith("v2.1.0/collection.json")
    folder = col["item"][0]
    assert folder["name"] == "Auth" and folder["item"][0]["name"] == "Login"
    req = folder["item"][0]["request"]
    assert req["method"] == "POST" and req["url"]["raw"] == "https://x.io/login"
    assert req["auth"]["bearer"][0]["value"] == "abc" and req["body"]["raw"] == '{"u":1}'
    assert folder["item"][0]["response"] == []               # Examples uchun joy


def test_migration_is_lossless_through_legacy_api(make_client):
    db = make_client(json.dumps(LEGACY)).get("/saved").get_json()
    by_id = {r["id"]: r for r in db["requests"]}
    assert by_id["r1"] == LEGACY["requests"][0]
    assert by_id["r2"]["folder_id"] is None
    assert db["folders"][0] == {**LEGACY["folders"][0]}


def test_migration_runs_once(isolated, make_client):
    make_client(json.dumps(LEGACY))
    (isolated / "saved_requests.json").write_text(json.dumps({"folders": [], "requests": []}))
    c = make_client()                                         # qayta ishga tushish
    assert c.app.config["MIGRATION"] == "skipped"
    assert len(c.get("/saved").get_json()["requests"]) == 2   # workspace — haqiqat manbai


def test_existing_bak_is_not_overwritten(isolated, make_client):
    (isolated / "saved_requests.json.bak").write_text("OLD BACKUP")
    make_client(json.dumps(LEGACY))
    assert (isolated / "saved_requests.json.bak").read_text() == "OLD BACKUP"
    assert len([f for f in os.listdir(isolated) if f.endswith(".bak")]) == 2


def test_corrupt_legacy_not_touched_and_retried(isolated, make_client):
    c = make_client("{broken")
    assert c.app.config["MIGRATION"] == "corrupt"
    assert (isolated / "saved_requests.json").read_text() == "{broken"
    assert not (isolated / "saved_requests.json.bak").exists()


def test_no_legacy_file(make_client):
    assert make_client().app.config["MIGRATION"] == "nothing"


def test_legacy_api_changes_persist_as_postman_collection(isolated, client):
    fid = client.post("/saved/folder", json={"name": "F"}).get_json()["id"]
    rid = client.post("/saved/request", json={"name": "R", "url": "http://x", "method": "GET",
                                              "folder_id": fid, "headers": [{"name": "H", "value": "v"}]}).get_json()["id"]
    col = json.loads((isolated / "workspace" / "collections" / "saved.json").read_text())
    item = col["item"][0]["item"][0]
    assert item["id"] == rid and item["request"]["header"] == [{"key": "H", "value": "v"}]
    # papkadan ildizga ko'chirish
    client.put(f"/saved/request/{rid}", json={"folder_id": None})
    col = json.loads((isolated / "workspace" / "collections" / "saved.json").read_text())
    assert [i["id"] for i in col["item"]] == [fid, rid] and col["item"][0]["item"] == []


def test_request_order_is_preserved_on_replace(client):
    ids = [client.post("/saved/request", json={"name": f"R{i}"}).get_json()["id"] for i in range(3)]
    client.post("/saved/request", json={"id": ids[1], "name": "R1-edited"})
    assert [r["name"] for r in client.get("/saved").get_json()["requests"]] == ["R0", "R1-edited", "R2"]


def test_examples_survive_request_resave(isolated, client):
    rid = client.post("/saved/request", json={"name": "R"}).get_json()["id"]
    p = isolated / "workspace" / "collections" / "saved.json"
    col = json.loads(p.read_text())
    col["item"][0]["response"] = [{"name": "ex1", "code": 200}]
    p.write_text(json.dumps(col))
    client.post("/saved/request", json={"id": rid, "name": "R2"})
    assert json.loads(p.read_text())["item"][0]["response"] == [{"name": "ex1", "code": 200}]


def test_atomic_write_leaves_no_tmp(isolated, client):
    client.post("/saved/folder", json={"name": "F"})
    assert not [f for f in os.listdir(isolated / "workspace" / "collections") if f.endswith(".tmp")]


def test_relative_order_within_each_folder_is_preserved(make_client):
    reqs = [{"id": f"r{i}", "name": f"R{i}", "folder_id": ("f1" if i % 2 else None)} for i in range(8)]
    data = {"folders": [{"id": "f1", "name": "F"}], "requests": reqs}
    got = make_client(json.dumps(data)).get("/saved").get_json()["requests"]
    for fid in ("f1", None):
        assert [r["id"] for r in got if r["folder_id"] == fid] == [r["id"] for r in reqs if r["folder_id"] == fid]
    assert {r["id"]: r for r in got} == {r["id"]: r for r in reqs}


def test_missing_folder_id_key_stays_missing(make_client):
    got = make_client(json.dumps({"folders": [], "requests": [{"id": "a", "name": "A"}]})).get("/saved").get_json()
    assert got["requests"] == [{"id": "a", "name": "A"}]
