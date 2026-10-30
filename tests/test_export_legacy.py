import json

from apirunner.export_legacy import main as export_main
from tests.test_storage_migration import LEGACY


def test_roundtrip_legacy_to_workspace_and_back_is_lossless(make_client):
    c = make_client(json.dumps(LEGACY))
    out = c.get("/api/export/legacy")
    assert out.status_code == 200 and "saved_requests.json" in out.headers["Content-Disposition"]
    data = out.get_json()
    assert data["folders"] == LEGACY["folders"]
    assert {r["id"]: r for r in data["requests"]} == {r["id"]: r for r in LEGACY["requests"]}


def test_request_without_legacy_blob_is_derived_from_postman_fields(client):
    cid = client.post("/api/collections", json={"name": "Yangi"}).get_json()["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    col["item"] = [{"id": "f", "name": "Papka", "item": [{"id": "r", "name": "Req", "request": {
        "method": "POST", "header": [{"key": "A", "value": "1"}, {"key": "Off", "value": "x", "disabled": True}],
        "url": {"raw": "http://x/y?q=1", "query": [{"key": "q", "value": "1"}]},
        "body": {"mode": "raw", "raw": "{}", "options": {"raw": {"language": "json"}}},
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "T"}]}}}]}]
    client.put(f"/api/collections/{cid}", json=col)
    data = client.get("/api/export/legacy").get_json()
    r = data["requests"][0]
    assert r["method"] == "POST" and r["url"] == "http://x/y" and r["headers"] == [{"name": "A", "value": "1"}]
    assert r["params"] == [{"name": "q", "value": "1"}] and r["body_type"] == "json" and r["authorization"] == "Bearer T"
    assert r["folder_id"] == "col-" + cid and data["folders"][0]["name"] == "Yangi"


def test_cli_script(isolated, make_client, capsys):
    make_client(json.dumps(LEGACY))
    out = isolated / "out.json"
    assert export_main(["--workspace", str(isolated / "workspace"), "-o", str(out)]) == 0
    assert len(json.loads(out.read_text())["requests"]) == 2
    assert export_main(["--workspace", str(isolated / "workspace"), "-o", str(out)]) == 1   # ustidan yozmaydi
    assert export_main(["--workspace", str(isolated / "workspace"), "-o", str(out), "--force"]) == 0
