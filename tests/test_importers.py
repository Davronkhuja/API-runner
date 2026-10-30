import json

POSTMAN = {
    "info": {"_postman_id": "x", "name": "Real", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
    "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{tok}}"}]},
    "variable": [{"key": "base", "value": "http://h"}],
    "event": [{"listen": "prerequest", "script": {"exec": ["pm.variables.set('a', 1)"]}}],
    "item": [
        {"name": "Outer", "item": [
            {"name": "Inner", "auth": {"type": "noauth"}, "item": [
                {"name": "Deep", "event": [{"listen": "test", "script": {"exec": ["pm.test('ok', () => {})"]}}],
                 "request": {"method": "POST", "header": [{"key": "X", "value": "1"}],
                             "url": {"raw": "{{base}}/p?q=1", "host": ["{{base}}"], "path": ["p"]},
                             "body": {"mode": "raw", "raw": "{}"}, "description": "desc"},
                 "response": [{"name": "ex", "code": 200, "body": "ok"}]}]}]},
        {"name": "Str", "request": {"method": "GET", "url": "http://h/str"}},
    ],
}


def test_import_postman_keeps_nesting_scripts_auth_examples(client):
    r = client.post("/api/import", json={"content": json.dumps(POSTMAN)}).get_json()
    assert r["kind"] == "postman" and r["name"] == "Real"
    col = client.get(f"/api/collections/{r['id']}").get_json()
    assert col["auth"]["type"] == "bearer" and col["variable"][0]["key"] == "base" and col["event"][0]["listen"] == "prerequest"
    deep = col["item"][0]["item"][0]["item"][0]
    assert deep["event"][0]["script"]["exec"] == ["pm.test('ok', () => {})"]       # skript o'zgarishsiz
    assert deep["response"][0]["code"] == 200 and deep["request"]["description"] == "desc"
    assert col["item"][0]["item"][0]["auth"] == {"type": "noauth"}
    assert col["item"][1]["request"]["url"] == {"raw": "http://h/str"}              # v2.0 satr URL normallashdi
    ids = []
    def walk(xs):
        for x in xs:
            ids.append(x["id"]); walk(x.get("item", []))
    walk(col["item"])
    assert len(ids) == len(set(ids)) == 4


def test_import_openapi(client):
    spec = {"openapi": "3.0.0", "info": {"title": "Pets"}, "servers": [{"url": "http://api.test/v1/"}],
            "paths": {"/pets": {"get": {"summary": "List", "tags": ["pets"], "parameters": [{"name": "limit", "in": "query"}]},
                                "post": {"tags": ["pets"], "requestBody": {"content": {"application/json": {}}}}},
                      "/health": {"get": {}}}}
    r = client.post("/api/import", json={"content": spec}).get_json()
    col = client.get(f"/api/collections/{r['id']}").get_json()
    by_name = {i["name"]: i for i in col["item"]}      # Flask test client JSON kalitlarni saralaydi → tartibga tayanmaymiz
    folder = by_name["pets"]
    assert folder["name"] == "pets" and [i["name"] for i in folder["item"]] == ["List", "POST /pets"]
    assert folder["item"][0]["request"]["url"]["raw"] == "http://api.test/v1/pets"
    assert folder["item"][0]["request"]["url"]["query"][0]["key"] == "limit"
    assert folder["item"][1]["request"]["body"]["mode"] == "raw"
    assert "GET /health" in by_name


def test_import_swagger2(client):
    spec = {"swagger": "2.0", "info": {"title": "Old"}, "host": "h.io", "basePath": "/api", "schemes": ["http"], "paths": {"/x": {"get": {}}}}
    r = client.post("/api/import", json={"content": json.dumps(spec)}).get_json()
    assert client.get(f"/api/collections/{r['id']}").get_json()["item"][0]["request"]["url"]["raw"] == "http://h.io/api/x"


def test_import_rejects_garbage(client):
    assert client.post("/api/import", json={"content": "not json"}).status_code == 400
    assert client.post("/api/import", json={"content": "{}"}).status_code == 400
    assert client.post("/api/import", json={"content": "[1]"}).status_code == 400
