"""Bosqich 5: har format uchun REAL namunaviy fayllar bilan import → eksport → qayta import (natija bir xil)."""
import base64
import io
import json
import pathlib
import zipfile

import pytest
import yaml

from apirunner.exporters import openapi as oas_export
from apirunner.exporters import postman as pm_export
from apirunner.importers.common import stats
from apirunner.importers.postman import canonical, import_postman
from apirunner.importers.registry import parse_source

FX = pathlib.Path(__file__).parent / "fixtures"
POSTMAN_FILES = ["twitter", "echo", "helpers", "newman_nested_requests", "newman_reporter_sample", "catURL", "compat_flow.postman_collection", "v2_0_collection"]


def text(*p):
    return (FX.joinpath(*p)).read_text(encoding="utf-8")


def one(parsed):
    assert len(parsed["collections"]) == 1
    return parsed["collections"][0]


def roundtrip_postman(col):
    return import_postman(pm_export.export_collection(col))


def flat(col):
    """(yo'l, nom, metod, url) ro'yxati — tuzilma solishtirish uchun."""
    out = []

    def walk(items, trail):
        for it in items:
            if "item" in it:
                out.append((trail, it["name"], "FOLDER", ""))
                walk(it["item"], trail + (it["name"],))
            else:
                r = it["request"]
                out.append((trail, it["name"], r["method"], r["url"]["raw"]))
    walk(col["item"], ())
    return out


def no_internal_keys(obj):
    s = json.dumps(obj)
    return "x-apirunner" not in s


# ── Postman collection ──
@pytest.mark.parametrize("name", POSTMAN_FILES)
def test_postman_real_files_roundtrip_is_identical_and_idempotent(name):
    col = one(parse_source(text("postman", name + ".json")))
    exported = pm_export.export_collection(col)
    assert exported["info"]["schema"].endswith("v2.1.0/collection.json") and no_internal_keys(exported)
    again = import_postman(exported)
    assert canonical(col) == canonical(again)
    assert canonical(again) == canonical(roundtrip_postman(again))                 # ikkinchi aylanish ham o'zgarmaydi
    assert stats(col) == stats(again)


def test_postman_v20_shapes_are_normalized():
    col = one(parse_source(text("postman", "v2_0_collection.json")))
    assert col["auth"]["bearer"] == [{"key": "token", "value": "{{tok}}", "type": "string"}]       # v2.0 obyekt → v2.1 ro'yxat
    folder = col["item"][0]
    assert folder["x-apirunner"]["description"] == "Papka tavsifi" and "description" not in folder
    req = folder["item"][0]["request"]
    assert req["url"]["raw"] == "https://api.example.test/v1/items?limit=5" and req["url"]["query"] == [{"key": "limit", "value": "5"}]
    assert req["header"] == [{"key": "Accept", "value": "application/json"}, {"key": "X-Trace", "value": "1"}]
    assert req["description"] == "**Qalin** tavsif"
    ex = folder["item"][0]["response"][0]
    assert ex["code"] == 200 and ex["header"] == [{"key": "Content-Type", "value": "application/json"}] and ex["id"].startswith("ex")
    assert col["item"][1]["request"] == {"method": "GET", "header": [], "url": {"raw": "https://api.example.test/ping"}}
    ev = col["item"][2]["event"][0]["script"]["exec"]
    assert ev == ["pm.test('ok', function () { pm.response.to.have.status(200); });"]
    assert col["item"][2]["request"]["url"]["raw"] == "https://api.example.test/v1/items/:id"
    assert col["x-apirunner"]["description"] == "v2.0 shaklidagi eski collection"


def test_postman_export_puts_description_back_and_derives_url_parts():
    col = one(parse_source(text("postman", "v2_0_collection.json")))
    out = pm_export.export_collection(col)
    assert out["info"]["description"] == "v2.0 shaklidagi eski collection"
    assert out["item"][0]["description"] == "Papka tavsifi"
    u = out["item"][0]["item"][0]["request"]["url"]
    assert u["protocol"] == "https" and u["host"] == ["api", "example", "test"] and u["path"] == ["v1", "items"] and u["query"][0]["key"] == "limit"
    # eskirgan qismlar raw'dan qayta hisoblanadi (foydalanuvchi raw'ni tahrirlagan bo'lishi mumkin)
    col["item"][0]["item"][0]["request"]["url"]["raw"] = "http://other.test:8080/v2/x"
    u = pm_export.export_collection(col)["item"][0]["item"][0]["request"]["url"]
    assert u["host"] == ["other", "test"] and u["port"] == "8080" and u["path"] == ["v2", "x"] and u["protocol"] == "http"


def test_postman_export_strips_secrets_and_file_refs():
    col = one(parse_source(text("postman", "echo.json")))
    col["variable"] = [{"key": "k", "value": "V", "type": "default"}, {"key": "s", "value": "TOP", "type": "secret"}]
    col["item"] = [{"id": "r", "name": "up", "request": {"method": "POST", "header": [], "url": {"raw": "http://x/"}, "body": {"mode": "formdata", "formdata": [{"key": "f", "type": "file", "src": ["files/" + "a" * 64 + "/report.pdf"]}]}}, "response": []}]
    out = pm_export.export_collection(col)
    assert out["variable"] == [{"key": "k", "value": "V", "type": "string"}, {"key": "s", "value": "", "type": "secret"}]
    assert out["item"][0]["request"]["body"]["formdata"][0]["src"] == "report.pdf"
    assert "TOP" not in json.dumps(out) and "aaaaaaaa" not in json.dumps(out)


# ── Postman environment / globals ──
def test_postman_environment_roundtrip_initial_only_and_secret_blank():
    p = parse_source(text("postman", "environment.json"))
    env = p["environments"][0]
    assert p["kind"] == "postman-env" and env["name"] == "Staging"
    vals = {v["key"]: v for v in env["values"]}
    assert vals["port"]["value"] == "8080" and vals["debug"]["enabled"] is False and vals["api_token"]["type"] == "secret"
    env["values"][0]["current"] = "https://CURRENT.test"                                  # Current eksportga ketmasligi kerak
    out = pm_export.export_environment(env)
    ov = {v["key"]: v for v in out["values"]}
    assert ov["base_url"]["value"] == "https://staging.example.test" and "current" not in ov["base_url"]
    assert ov["api_token"] == {"key": "api_token", "value": "", "type": "secret", "enabled": True}
    assert out["_postman_variable_scope"] == "environment" and "s3cr3t" not in json.dumps(out) and "CURRENT" not in json.dumps(out)
    again = parse_source(json.dumps(out))["environments"][0]
    assert [(v["key"], v["value"], v["enabled"], v["type"]) for v in again["values"]] == [(v["key"], v["value"], v["enabled"], v["type"]) for v in
                                                                                     [{**x, "value": "" if x["type"] == "secret" else x["value"]} for x in env["values"]]]


def test_postman_globals_roundtrip():
    p = parse_source(text("postman", "globals.json"))
    assert p["kind"] == "postman-globals" and [v["key"] for v in p["globals"]] == ["tenant", "global_secret"]
    out = pm_export.export_globals(p["globals"])
    assert out["_postman_variable_scope"] == "globals" and out["values"][1]["value"] == "" and out["values"][0]["value"] == "acme"
    assert [v["key"] for v in parse_source(json.dumps(out))["globals"]] == ["tenant", "global_secret"]


# ── OpenAPI ──
def test_openapi3_yaml_import_details():
    p = parse_source(text("openapi", "petstore3.yaml"))
    col = one(p)
    assert p["kind"] == "openapi" and col["info"]["name"] == "Swagger Petstore" and col["info"]["version"] == "1.0.11"
    assert {v["key"]: v["value"] for v in col["variable"]}["baseUrl"] == "https://petstore3.swagger.io/api/v3"
    names = [i["name"] for i in col["item"]]
    assert names == ["pet", "store", "Health check"]                                       # tag bo'yicha papkalar, tagsiz — ildizda
    assert col["item"][0]["x-apirunner"]["description"] == "Everything about your Pets"
    pet = {i["name"]: i for i in col["item"][0]["item"]}
    find = pet["Finds Pets by status"]["request"]
    assert find["url"]["raw"] == "{{baseUrl}}/pet/findByStatus" and find["url"]["query"][0]["value"] == "available" and find["url"]["query"][0].get("disabled") is True
    one_ = pet["Find pet by ID"]["request"]
    assert one_["url"]["raw"] == "{{baseUrl}}/pet/:petId" and one_["url"]["variable"][0]["key"] == "petId"
    put = pet["Update an existing pet"]["request"]
    body = json.loads(put["body"]["raw"])
    assert body == {"id": 10, "name": "doggie", "category": {"id": 0, "name": "string"}, "photoUrls": ["string"], "status": "available"}   # $ref + misollar
    assert [e["code"] for e in pet["Update an existing pet"]["response"]] == [200, 404]
    assert json.loads(pet["Update an existing pet"]["response"][0]["body"])["name"] == "doggie"
    up = pet["uploads an image"]["request"]["body"]
    assert up["mode"] == "formdata" and {"key": "file", "type": "file", "src": []} in up["formdata"]
    assert pet["Add a new pet to the store"]["request"]["body"]["mode"] == "raw"            # JSON tanlandi (form emas)
    # xavfsizlik: global api_key → collection apikey; /health noauth; PUT /pet oauth2
    assert col["auth"]["type"] == "apikey" and {r["key"]: r["value"] for r in col["auth"]["apikey"]}["key"] == "api_key"
    assert col["item"][2]["request"]["auth"] == {"type": "noauth"}
    o = pet["Update an existing pet"]["request"]["auth"]
    assert o["type"] == "oauth2" and {r["key"]: r["value"] for r in o["oauth2"]}["grant_type"] == "implicit"
    assert not p["warnings"]


def test_swagger2_import_details():
    col = one(parse_source(text("openapi", "swagger2_petstore.json")))
    assert {v["key"]: v["value"] for v in col["variable"]}["baseUrl"] == "https://petstore.swagger.io/v2"
    pets = {i["name"]: i for i in col["item"][0]["item"]}
    assert json.loads(pets["Add a new pet"]["request"]["body"]["raw"]) == {"id": 0, "name": "doggie", "tags": ["string"]}
    assert pets["Updates a pet with form data"]["request"]["body"]["mode"] == "urlencoded"
    assert pets["uploads an image"]["request"]["body"]["formdata"][0] == {"key": "file", "type": "file", "src": []}
    assert pets["Find pet by ID"]["request"]["auth"]["type"] == "apikey"
    assert [e["code"] for e in pets["Add a new pet"]["response"]] == [200, 405]


def oas_shape(col):
    """OpenAPI aylanishi uchun mazmuniy shakl: papka, nom, metod, yo'l, query/header kalitlari, body turi, javob kodlari."""
    out = []

    def walk(items, trail):
        for it in items:
            if "item" in it:
                walk(it["item"], trail + (it["name"],))
                continue
            r = it["request"]
            raw = r["url"]["raw"].split("?")[0]
            path = "/" + raw.split("}}", 1)[-1].lstrip("/") if raw.startswith("{{") else "/" + raw.split("/", 3)[-1]
            out.append((trail, it["name"], r["method"], path, sorted(q["key"] for q in r["url"].get("query") or []), sorted(h["key"] for h in r["header"]),
                        (r.get("body") or {}).get("mode"), sorted(e["code"] for e in it["response"])))
    walk(col["item"], ())
    return sorted(out, key=lambda x: (x[0], x[1], x[2]))


@pytest.mark.parametrize("fixture", ["petstore3.yaml", "swagger2_petstore.json"])
def test_openapi_import_export_import_roundtrip(fixture):
    col = one(parse_source(text("openapi", fixture)))
    doc = oas_export.export_openapi(col)
    assert doc["openapi"] == "3.0.3" and doc["paths"] and "x-skipped" not in doc
    for fmt in ("json", "yaml"):
        txt = oas_export.to_text(doc, fmt)
        back = one(parse_source(txt))
        assert oas_shape(back) == oas_shape(col), fmt
        assert back["info"]["name"] == col["info"]["name"] and back["info"]["version"] == col["info"]["version"]
        assert {v["key"]: v["value"] for v in back["variable"]}["baseUrl"] == {v["key"]: v["value"] for v in col["variable"]}["baseUrl"]


def test_openapi_export_details():
    col = one(parse_source(text("openapi", "petstore3.yaml")))
    doc = oas_export.export_openapi(col)
    assert doc["servers"] == [{"url": "https://petstore3.swagger.io/api/v3"}]
    assert set(doc["paths"]) == {"/pet", "/pet/findByStatus", "/pet/{petId}", "/pet/{petId}/uploadImage", "/store/inventory", "/health"}
    get = doc["paths"]["/pet/{petId}"]["get"]
    assert get["parameters"][0] == {"name": "petId", "in": "path", "required": True, "schema": {"type": "string"}, "example": "1"} and get["tags"] == ["pet"]
    assert doc["paths"]["/health"]["get"]["security"] == []
    put = doc["paths"]["/pet"]["put"]
    assert put["requestBody"]["content"]["application/json"]["schema"]["properties"]["category"]["type"] == "object"
    assert set(put["responses"]) == {"200", "404"} and put["responses"]["200"]["content"]["application/json"]["example"]["name"] == "doggie"
    assert doc["components"]["securitySchemes"]["apiKeyAuth"] == {"type": "apiKey", "name": "api_key", "in": "header"}
    assert doc["components"]["securitySchemes"]["oauth2Auth"]["type"] == "oauth2"
    assert doc["security"] == [{"apiKeyAuth": []}]


def test_openapi_export_from_postman_collection_with_variables_and_hosts():
    col = one(parse_source(text("postman", "compat_flow.postman_collection.json")))
    doc = oas_export.export_openapi(col)
    assert doc["paths"] and all(p.startswith("/") for p in doc["paths"])
    assert any("{" in p for p in doc["paths"])                                             # {{current_id}} → {current_id}
    json.dumps(doc)                                                                         # serializatsiya


# ── Insomnia ──
def test_insomnia_v4_import():
    p = parse_source(text("insomnia", "insomnia_v4.json"))
    col = one(p)
    assert p["kind"] == "insomnia" and col["info"]["name"] == "Shop API" and col["x-apirunner"]["description"] == "Do'kon API (Insomnia)"
    assert [i["name"] for i in col["item"]] == ["Products", "Login form", "GraphQL"]       # metaSortKey bo'yicha
    products = col["item"][0]
    assert [i["name"] for i in products["item"]] == ["Admin", "List products"] and products["x-apirunner"]["description"] == "Mahsulotlar"
    lst = products["item"][1]["request"]
    assert lst["url"]["raw"] == "{{base_url}}/products?page=1" and lst["url"]["query"][1] == {"key": "debug", "value": "1", "disabled": True}
    assert lst["auth"]["bearer"][0]["value"] == "{{auth.token}}" and lst["description"] == "Ro'yxat"
    create = products["item"][0]["item"][0]["request"]
    assert create["body"]["mode"] == "raw" and "{{retries}}" in create["body"]["raw"] and create["auth"]["type"] == "basic"
    assert col["item"][1]["request"]["body"]["urlencoded"] == [{"key": "user", "value": "u"}, {"key": "pass", "value": "p"}]
    assert col["item"][2]["request"]["body"] == {"mode": "graphql", "graphql": {"query": "{ products { id } }", "variables": json.dumps({"a": 1})}}
    assert {v["key"]: v["value"] for v in col["variable"]} == {"base_url": "https://shop.example.test", "auth.token": "base-token", "retries": "3"}
    assert [e["name"] for e in p["environments"]] == ["Shop API · Production"] and p["environments"][0]["values"][0]["value"] == "https://shop.prod.example.test"


def test_insomnia_rejects_v5_with_hint():
    from apirunner.importers.common import ImportErr
    with pytest.raises(ImportErr, match="v4"):
        parse_source("type: collection.insomnia.rest/5.0\nname: x\ncollection: []\n")


# ── HAR ──
def test_har_import():
    p = parse_source(text("har", "sample.har"))
    col = one(p)
    assert p["kind"] == "har" and col["info"]["name"] == "https://shop.example.test/"
    assert [f["name"] for f in col["item"]] == ["shop.example.test", "auth.example.test"]    # bir nechta host — papkalar
    get, post = col["item"][0]["item"]
    assert get["name"] == "GET /api/products" and [h["key"] for h in get["request"]["header"]] == ["accept", "x-client"]    # pseudo/cookie/accept-encoding tushdi
    assert get["request"]["url"]["query"] == [{"key": "page", "value": "2"}, {"key": "sort", "value": "price"}]
    assert get["response"][0]["code"] == 200 and json.loads(get["response"][0]["body"]) == {"items": [{"id": 1}], "page": 2}
    assert [h["key"] for h in get["response"][0]["header"]] == ["content-type"]
    assert post["request"]["body"]["options"]["raw"]["language"] == "json" and post["response"][0]["body"] == '{"ok":true}'   # base64 ochildi
    tok = col["item"][1]["item"][0]["request"]["body"]
    assert tok["mode"] == "urlencoded" and tok["urlencoded"][0] == {"key": "grant_type", "value": "password"}
    assert any("Cookie" in w for w in p["warnings"])


# ── cURL ──
def test_curl_multiple_commands_with_bash_quoting():
    p = parse_source(text("curl", "multi.sh"))
    col = one(p)
    assert p["kind"] == "curl" and len(col["item"]) == 5 and not p["warnings"]
    a, b, c, d, e = [i["request"] for i in col["item"]]
    assert a["method"] == "GET" and a["url"]["query"] == [{"key": "active", "value": "true"}] and {"key": "authorization", "value": "Bearer eyJhbGciOi"} in a["header"]
    assert b["method"] == "POST" and b["body"]["options"]["raw"]["language"] == "json" and json.loads(b["body"]["raw"]) == {"name": "Ali", "tags": ["a", "b"]}
    assert c["method"] == "PUT" and c["auth"]["basic"][0]["value"] == "admin" and c["body"]["mode"] == "urlencoded"
    assert c["body"]["urlencoded"] == [{"key": "a", "value": "1"}, {"key": "note", "value": "hello world&x"}]
    assert {"key": "x-note", "value": "it's fine"} in d["header"] and json.loads(d["body"]["raw"]) == {"q": "line1\nline2"}
    assert e["body"]["formdata"] == [{"key": "file", "type": "file", "src": []}, {"key": "title", "value": "Q1 report", "type": "text"}]


def test_curl_errors_are_reported():
    from apirunner.importers.common import ImportErr
    with pytest.raises(ImportErr):
        parse_source("curl -X POST")
    p = parse_source("curl https://ok.test/a\ncurl -H")
    assert len(one(p)["item"]) == 1 and p["warnings"]


# ── har / insomnia / curl → Postman → qayta import ──
@pytest.mark.parametrize("path", [("insomnia", "insomnia_v4.json"), ("har", "sample.har"), ("curl", "multi.sh"), ("openapi", "petstore3.yaml"), ("openapi", "swagger2_petstore.json")])
def test_every_source_survives_postman_export_roundtrip(path):
    col = one(parse_source(text(*path)))
    back = roundtrip_postman(col)
    assert canonical(col) == canonical(back) and flat(col) == flat(back)
    assert canonical(back) == canonical(roundtrip_postman(back))


# ── workspace zip ──
def test_workspace_zip_roundtrip_through_api(make_client, tmp_path):
    src = make_client()
    cid = src.post("/api/collections", json={"name": "Zip col"}).get_json()["id"]
    col = src.get(f"/api/collections/{cid}").get_json()
    col["item"] = [{"id": "r1", "name": "R", "request": {"method": "GET", "header": [], "url": {"raw": "http://x.test/"}}, "response": []}]
    src.put(f"/api/collections/{cid}", json=col)
    eid = src.post("/api/environments", json={"name": "ZipEnv"}).get_json()["id"]
    env = src.get(f"/api/environments/{eid}").get_json()
    env["values"] = [{"key": "k", "value": "init", "current": "cur", "enabled": True, "type": "secret"}]
    src.put(f"/api/environments/{eid}", json=env)
    src.put("/api/globals", json={"values": [{"key": "g", "value": "1", "enabled": True, "type": "default"}]})
    r = src.post("/api/workspace/export", json={"secrets": True, "state": True})              # to'liq zaxira (maxfiylar bilan)
    assert r.status_code == 200 and r.mimetype == "application/zip" and "attachment" in r.headers["Content-Disposition"]
    z = zipfile.ZipFile(io.BytesIO(r.data))
    assert {"manifest.json", "globals.json", "workspace.json", f"collections/{cid}.json", f"environments/{eid}.json"} <= set(z.namelist())
    assert json.loads(z.read("manifest.json"))["kind"] == "api-runner-workspace" and "state.db" in z.namelist()
    assert "state.db" not in zipfile.ZipFile(io.BytesIO(src.get("/api/workspace/export").data)).namelist()          # sukut: bazasiz
    # toza workspace'ga import
    dst = make_client.__wrapped__(make_client) if False else None
    payload = {"sources": [{"name": "ws.zip", "content": base64.b64encode(r.data).decode(), "encoding": "base64"}]}
    pv = src.post("/api/import/preview", json=payload).get_json()["sources"][0]
    assert pv["ok"] and pv["kind"] == "workspace" and {i["type"] for i in pv["items"]} >= {"collection", "environment", "globals"}
    assert all(i["conflict"] for i in pv["items"])                                           # o'sha workspace'ga qaytarilmoqda
    res = src.post("/api/import/apply", json={**payload, "decisions": [{"source": 0, "item": i, "action": "copy" if pv["items"][i]["type"] != "globals" else "merge"} for i in range(len(pv["items"]))]}).get_json()
    assert res["ok"], res
    names = {c["name"] for c in src.get("/api/workspace").get_json()["collections"]}
    assert names >= {"Zip col", "Zip col (2)"}
    copy = next(c for c in src.get("/api/workspace").get_json()["collections"] if c["name"] == "Zip col (2)")
    a, b = canonical(src.get(f"/api/collections/{copy['id']}").get_json()), canonical(src.get(f"/api/collections/{cid}").get_json())
    a["info"].pop("name"); b["info"].pop("name")
    assert a == b
    envs = {e["name"]: e for e in src.get("/api/workspace").get_json()["environments"]}
    assert envs["ZipEnv (2)"]["values"][0]["current"] == "cur"                               # zaxira — to'liq (Current ham)


def test_workspace_zip_rejects_foreign_and_corrupt(client):
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("random.txt", "x")
    r = client.post("/api/import/preview", json={"sources": [{"name": "a.zip", "content": base64.b64encode(bad.getvalue()).decode(), "encoding": "base64"}]}).get_json()["sources"][0]
    assert not r["ok"] and "workspace" in r["error"]
    r = client.post("/api/import/preview", json={"sources": [{"name": "a.zip", "content": base64.b64encode(b"not a zip").decode(), "encoding": "base64"}]}).get_json()["sources"][0]
    assert not r["ok"] and "buzuq" in r["error"]
