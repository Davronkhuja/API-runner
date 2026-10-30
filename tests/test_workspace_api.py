import json


def test_workspace_summary_empty(client):
    d = client.get("/api/workspace").get_json()
    assert d["collections"] == [] and d["environments"] == [] and d["globals"]["values"] == []


def test_collection_crud_with_nested_folders(client):
    cid = client.post("/api/collections", json={"name": "Mening"}).get_json()["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    assert col["info"]["name"] == "Mening" and col["item"] == []
    col["item"] = [{"id": "a", "name": "L1", "item": [
        {"id": "b", "name": "L2", "item": [
            {"id": "c", "name": "L3", "item": [
                {"id": "r", "name": "Req", "request": {"method": "GET", "url": {"raw": "http://x"}},
                 "response": [{"name": "ok", "code": 200}]}]}]}]}]
    assert client.put(f"/api/collections/{cid}", json=col).status_code == 200
    assert client.get(f"/api/collections/{cid}").get_json() == col
    assert client.get("/api/workspace").get_json()["collections"] == [{"id": cid, "name": "Mening", "requests": 1}]
    client.delete(f"/api/collections/{cid}")
    assert client.get(f"/api/collections/{cid}").status_code == 404


def test_collection_validation(client):
    cid = client.post("/api/collections", json={"name": "C"}).get_json()["id"]
    assert client.put(f"/api/collections/{cid}", json={"info": {"_postman_id": "other"}, "item": []}).status_code == 400
    assert client.post("/api/collections", json={"name": " "}).status_code == 400
    assert client.put("/api/collections/nope", json={"info": {"_postman_id": "nope"}, "item": []}).status_code == 404


def test_environment_crud(client):
    eid = client.post("/api/environments", json={"name": "Dev", "values": [
        {"key": "host", "value": "x", "enabled": True, "type": "default"}]}).get_json()["id"]
    env = client.get(f"/api/environments/{eid}").get_json()
    assert env["name"] == "Dev" and env["values"][0]["key"] == "host"
    env["values"].append({"key": "tok", "value": "s", "enabled": True, "type": "secret"})
    client.put(f"/api/environments/{eid}", json=env)
    assert len(client.get(f"/api/environments/{eid}").get_json()["values"]) == 2
    client.delete(f"/api/environments/{eid}")
    assert client.get("/api/environments/" + eid).status_code == 404


def test_globals(client):
    client.put("/api/globals", json={"values": [{"key": "g", "value": "1", "enabled": True}]})
    assert client.get("/api/globals").get_json()["values"][0]["key"] == "g"
    assert client.put("/api/globals", json={"values": "x"}).status_code == 400


def test_workspace_files_are_plain_json_on_disk(isolated, client):
    client.post("/api/environments", json={"name": "E"})
    files = list((isolated / "workspace" / "environments").glob("*.json"))
    assert len(files) == 1 and json.loads(files[0].read_text())["name"] == "E"
    assert (isolated / "workspace" / "state.db").exists()


LS = {
    "apiRunnerEnvs": json.dumps([{"id": "e1", "name": "Prod", "vars": {"host": "api.io", "k": "v"}},
                                 {"id": "e2", "name": "Dev", "variables": [{"key": "a", "value": "1"}]}]),
    "apiRunnerActiveEnvId": "e1",
    "apiRunnerEnvVars": json.dumps({"legacyvar": "1"}),
    "apiRunnerHistory": json.dumps([{"method": "GET", "url": "http://x", "timestamp": 1700000000000}]),
    "apiRunnerRunHistory": json.dumps([{"url": "http://y"}]),
    "apiRunnerUrlHistory": json.dumps(["http://a", "http://b"]),
}


def test_import_localstorage(isolated, client):
    d = client.post("/api/import/localstorage", json={"data": LS}).get_json()
    assert d["stats"]["environments"] == 2 and d["stats"]["history"] == 1 and d["stats"]["url_history"] == 2
    envs = {e["id"]: e for e in client.get("/api/workspace").get_json()["environments"]}
    assert {v["key"]: v["value"] for v in envs["e1"]["values"]} == {"host": "api.io", "k": "v"}
    assert envs["e2"]["values"][0]["key"] == "a"
    ws = client.get("/api/workspace").get_json()
    assert ws["meta"]["active_environment_id"] == "e1" and ws["meta"]["localstorage_imported"] is True
    assert ws["globals"]["values"][0]["key"] == "legacyvar"
    hist = client.get("/api/history?kind=request").get_json()
    assert hist[0]["payload"]["url"] == "http://x" and hist[0]["ts"] == 1700000000
    # xom nusxa saqlangan
    assert list((isolated / "workspace" / "imports").glob("localstorage-*.json"))


def test_import_localstorage_is_idempotent(client):
    client.post("/api/import/localstorage", json={"data": LS})
    d = client.post("/api/import/localstorage", json={"data": LS}).get_json()
    assert d["stats"]["environments"] == 0 and d["stats"]["history"] == 0
    assert len(client.get("/api/workspace").get_json()["environments"]) == 2
    assert len(client.get("/api/history").get_json()) == 4


def test_import_localstorage_tolerates_garbage(client):
    d = client.post("/api/import/localstorage", json={"data": {"apiRunnerEnvs": "{not json", "apiRunnerHistory": 5}})
    assert d.status_code == 200
    assert client.post("/api/import/localstorage", json={"data": "x"}).status_code == 400


def test_version_endpoint_matches_package(client):
    import apirunner
    assert client.get("/api/version").get_json() == {"version": apirunner.__version__}
    assert apirunner.__version__ == "2.1.2"
