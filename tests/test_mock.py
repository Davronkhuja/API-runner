"""Mock server: Example'lar asosida moslash (metod, yo'l, path variables, query, header), kechikish, jurnal, UI API."""
import json
import time

import pytest
import requests

from apirunner.mock import MockServer, build_routes, pick


def ex(name, code, body, query=None, headers=None, rh=None):
    o = {"name": name, "code": code, "status": "x", "header": rh if rh is not None else [{"key": "Content-Type", "value": "application/json"}], "body": body, "originalRequest": {"method": "GET", "url": {"raw": "x", "query": [{"key": k, "value": v} for k, v in (query or {}).items()]},
                                                                                                                                 "header": [{"key": k, "value": v} for k, v in (headers or {}).items()]}}
    return o


def item(i, name, method, raw, examples):
    return {"id": i, "name": name, "request": {"method": method, "header": [], "url": {"raw": raw}}, "response": examples}


COL = {"info": {"_postman_id": "m1", "name": "Mock col"}, "item": [
    item("a", "List users", "GET", "{{baseUrl}}/users", [ex("ok", 200, '[{"id": 1}]'), ex("admins", 200, '[{"id": 99}]', query={"role": "admin"})]),
    item("b", "Get user", "GET", "https://api.example.com/users/:id", [ex("found", 200, '{"id": "{{id}}", "name": "User {{id}}"}'), ex("not found", 404, '{"error": "no"}', headers={"x-mock-response-code": "404"})]),
    item("c", "Me", "GET", "{{baseUrl}}/users/me", [ex("me", 200, '{"me": true}')]),
    item("d", "Create", "POST", "{{baseUrl}}/users", [ex("created", 201, '{"id": "{{$guid}}"}', rh=[{"key": "Content-Type", "value": "application/json"}, {"key": "X-Mock-Delay", "value": "120"}, {"key": "X-Custom", "value": "yes"}])]),
    {"id": "f", "name": "Folder", "item": [item("e", "Ping", "GET", "{{baseUrl}}/ping", [ex("pong", 200, "pong", rh=[])])]},
]}


@pytest.fixture
def mock():
    m = MockServer(COL).start()
    yield m
    m.stop()


def test_matching_methods_paths_static_over_param_and_path_variables(mock):
    u = mock.url
    assert requests.get(u + "/users").json() == [{"id": 1}]
    r = requests.get(u + "/users/42")
    assert r.status_code == 200 and r.json() == {"id": "42", "name": "User 42"}               # path variable javobga qo'yildi
    assert requests.get(u + "/users/me").json() == {"me": True}                                 # statik segment parametrdan ustun
    assert requests.get(u + "/ping").text == "pong" and requests.get(u + "/ping").headers["Content-Type"].startswith("text/plain")
    nf = requests.get(u + "/nope")
    assert nf.status_code == 404 and "GET /users/:id" in nf.json()["available"] and nf.json()["error"].startswith("Mock")
    assert requests.delete(u + "/users").status_code == 404                                    # metod mos emas


def test_query_and_header_conditions_choose_the_more_specific_example(mock):
    u = mock.url
    assert requests.get(u + "/users?role=admin").json() == [{"id": 99}]
    assert requests.get(u + "/users?role=guest").json() == [{"id": 1}]                          # shart bajarilmadi: umumiy example
    r = requests.get(u + "/users/7", headers={"x-mock-response-code": "404"})
    assert r.status_code == 404 and r.json() == {"error": "no"}


def test_status_headers_delay_and_dynamic_variables(mock):
    t = time.time()
    r = requests.post(u := mock.url + "/users", json={})
    assert time.time() - t >= 0.12 and r.status_code == 201 and r.headers["X-Custom"] == "yes"
    assert "X-Mock-Delay" not in r.headers and len(r.json()["id"]) == 36 and r.headers["X-Mock-Example"] == "created"
    del u


def test_global_delay_and_journal():
    m = MockServer(COL, delay_ms=80).start()
    try:
        t = time.time()
        requests.get(m.url + "/ping")
        assert time.time() - t >= 0.08
        requests.get(m.url + "/missing")
        log = m.entries()
        assert [(e["method"], e["path"], e["status"]) for e in log] == [("GET", "/ping", 200), ("GET", "/missing", 404)]
        assert log[0]["matched"] == "Ping · pong" and log[0]["delay"] == 80 and log[1]["matched"] is None
        assert [e["seq"] for e in m.entries(1)] == [1]
    finally:
        m.stop()


def test_folder_scope_and_route_table():
    r = build_routes(COL, folder="Folder")
    assert [x["name"] for x in r] == ["Ping"]
    m = MockServer(COL)
    assert {(x["method"], x["path"]) for x in m.summary_routes()} >= {("GET", "/users/:id"), ("POST", "/users"), ("GET", "/ping")}
    m.srv.server_close()
    assert pick(build_routes(COL), "GET", ["users", "5"], {}, {})[1] == {"id": "5"}


# ── UI API ──
def put_col(client):
    cid = client.post("/api/collections", json={"name": "MockApi"}).get_json()["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    col["item"] = COL["item"]
    client.put(f"/api/collections/{cid}", json=col)
    return cid


def test_api_start_stop_port_log_and_errors(client):
    cid = put_col(client)
    r = client.post("/api/mocks", json={"collection_id": cid, "port": 0, "delay_ms": 0}).get_json()
    assert r["url"].startswith("http://127.0.0.1:") and len(r["routes"]) >= 5 and r["collection"] == "MockApi"
    assert requests.get(r["url"] + "/users/9").json()["id"] == "9"
    d = client.get(f"/api/mocks/{r['id']}/log").get_json()
    assert d["entries"][0]["path"] == "/users/9" and d["running"] is True
    assert [m["id"] for m in client.get("/api/mocks").get_json()] == [r["id"]]
    busy = client.post("/api/mocks", json={"collection_id": cid, "port": r["port"]})
    assert busy.status_code == 400 and "band" in busy.get_json()["error"]                      # port band
    assert client.post(f"/api/mocks/{r['id']}/stop").get_json()["ok"]
    with pytest.raises(requests.ConnectionError):
        requests.get(r["url"] + "/users", timeout=1)
    assert client.get("/api/mocks").get_json() == []
    empty = client.post("/api/collections", json={"name": "NoEx"}).get_json()["id"]
    assert client.post("/api/mocks", json={"collection_id": empty}).status_code == 400
    assert client.post("/api/mocks", json={"collection_id": "nope"}).status_code == 404


def test_non_latin1_example_name_and_header_values_do_not_break_the_response():
    col = {"info": {"_postman_id": "m2", "name": "Uni"}, "item": [item("u", "U", "GET", "{{b}}/u", [ex("200 OK — foydalanuvchi", 200, "{}", rh=[{"key": "Content-Type", "value": "application/json"}, {"key": "X-Title", "value": "Ўзбек — ok"}])])]}
    m = MockServer(col).start()
    try:
        r = requests.get(m.url + "/u")
        assert r.status_code == 200 and "foydalanuvchi" in r.headers["X-Mock-Example"] and r.headers["X-Title"].endswith("ok")
    finally:
        m.stop()
