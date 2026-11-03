import json


def test_empty_db(client):
    assert client.get("/saved").get_json() == {"folders": [], "requests": []}


def test_folder_crud(client):
    r = client.post("/saved/folder", json={"name": "  Papka  "})
    fid = r.get_json()["id"]
    db = client.get("/saved").get_json()
    assert db["folders"][0]["name"] == "Papka"
    assert db["folders"][0]["expanded"] is True

    client.put(f"/saved/folder/{fid}", json={"name": "Yangi", "expanded": False})
    f = client.get("/saved").get_json()["folders"][0]
    assert f["name"] == "Yangi" and f["expanded"] is False

    client.delete(f"/saved/folder/{fid}")
    assert client.get("/saved").get_json()["folders"] == []


def test_folder_requires_name(client):
    assert client.post("/saved/folder", json={"name": " "}).status_code == 400


def test_request_create_update_move_delete(client):
    fid = client.post("/saved/folder", json={"name": "F"}).get_json()["id"]
    rid = client.post("/saved/request", json={"name": "R1", "url": "http://x", "method": "GET"}).get_json()["id"]
    req = client.get("/saved").get_json()["requests"][0]
    assert req["folder_id"] is None and req["url"] == "http://x"

    client.put(f"/saved/request/{rid}", json={"name": "R2", "folder_id": fid})
    req = client.get("/saved").get_json()["requests"][0]
    assert req["name"] == "R2" and req["folder_id"] == fid

    # to'liq almashtirish (id bilan POST) created_at ni saqlaydi
    created = req["created_at"]
    client.post("/saved/request", json={"id": rid, "name": "R3", "url": "http://y", "folder_id": fid})
    req = client.get("/saved").get_json()["requests"][0]
    assert req["name"] == "R3" and req["url"] == "http://y" and req["created_at"] == created

    client.delete(f"/saved/request/{rid}")
    assert client.get("/saved").get_json()["requests"] == []


def test_request_requires_name(client):
    assert client.post("/saved/request", json={"name": ""}).status_code == 400


def test_delete_folder_moves_requests_to_root(client):
    fid = client.post("/saved/folder", json={"name": "F"}).get_json()["id"]
    client.post("/saved/request", json={"name": "R", "folder_id": fid})
    client.delete(f"/saved/folder/{fid}")
    db = client.get("/saved").get_json()
    assert db["requests"][0]["folder_id"] is None


def test_legacy_list_format_is_migrated(make_client):
    db = make_client(json.dumps([{"id": "1", "name": "old"}])).get("/saved").get_json()
    assert db["folders"] == [] and db["requests"][0]["name"] == "old"


def test_corrupt_file_yields_empty_db(make_client):
    assert make_client("{not json").get("/saved").get_json() == {"folders": [], "requests": []}


def test_unicode_roundtrip(client, isolated):
    client.post("/saved/folder", json={"name": "Ўзбекча — ʻoʻ"})
    assert client.get("/saved").get_json()["folders"][0]["name"] == "Ўзбекча — ʻoʻ"
    assert "Ўзбекча" in (isolated / "workspace" / "collections" / "saved.json").read_text(encoding="utf-8")
