"""Import konflikt holati: bir xil nomli collection/muhit/globals — birlashtirish / yangi nusxa / almashtirish / o'tkazib yuborish; eksport endpointlari."""
import json
import os
import pathlib

FX = pathlib.Path(__file__).parent / "fixtures"


def src(*p, name=None):
    return {"name": name or p[-1], "content": FX.joinpath(*p).read_text(encoding="utf-8")}


def preview(client, *sources):
    return client.post("/api/import/preview", json={"sources": list(sources)}).get_json()["sources"]


def apply(client, sources, decisions=None):
    r = client.post("/api/import/apply", json={"sources": sources, "decisions": decisions or []})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def collections(client):
    return client.get("/api/workspace").get_json()["collections"]


def count(col):
    n = 0
    stack = list(col["item"])
    while stack:
        i = stack.pop()
        stack.extend(i.get("item", [])) if "item" in i else None
        n += "item" not in i
    return n


ECHO = src("postman", "echo.json")


def test_preview_reports_format_stats_and_no_conflict_first_time(client):
    s = preview(client, ECHO, src("openapi", "petstore3.yaml"), src("insomnia", "insomnia_v4.json"), src("har", "sample.har"), src("curl", "multi.sh"), src("postman", "environment.json"), src("postman", "globals.json"))
    assert [x["kind"] for x in s] == ["postman", "openapi", "insomnia", "har", "curl", "postman-env", "postman-globals"]
    assert all(x["ok"] and all(i["conflict"] is None and i["default_action"] == "import" for i in x["items"]) for x in s)
    assert s[0]["items"][0]["stats"]["requests"] == 23 and s[0]["items"][0]["stats"]["folders"] == 7
    assert [i["type"] for i in s[2]["items"]] == ["collection", "environment"]
    assert s[3]["warnings"] and s[1]["items"][0]["stats"]["examples"] >= 5
    assert collections(client) == []                                                       # ko'rib chiqish hech narsa yozmaydi


def test_preview_garbage_and_unknown_formats_are_reported_per_source(client):
    s = preview(client, {"name": "x.txt", "content": "bu hech narsa emas"}, {"name": "y.json", "content": '{"a": 1}'}, {"name": "z.json", "content": "{buzuq"}, ECHO)
    assert [x["ok"] for x in s] == [False, False, False, True]
    assert "Format tanilmadi" in s[1]["error"] and "Qo'llab-quvvatlanadi" in s[1]["error"]


def test_same_name_collection_shows_conflict_with_merge_counts_and_defaults_to_copy(client):
    apply(client, [ECHO])
    p = preview(client, ECHO)[0]["items"][0]
    assert p["conflict"]["name"] == "Echo" or p["conflict"]["id"]
    assert p["default_action"] == "copy" and p["conflict"]["merge"] == {"added_folders": 0, "added_requests": 0, "skipped": 23, "added_variables": 0}


def test_copy_creates_numbered_new_collection(client):
    base = json.loads(ECHO["content"])["info"]["name"]
    apply(client, [ECHO])
    copy = {"source": 0, "item": 0, "action": "copy"}
    assert apply(client, [ECHO], [copy])["results"][0]["name"] == f"{base} (2)"
    assert apply(client, [ECHO], [copy])["results"][0]["name"] == f"{base} (3)"
    assert sorted(c["name"] for c in collections(client)) == [base, f"{base} (2)", f"{base} (3)"]
    assert len({c["id"] for c in collections(client)}) == 3


def test_replace_keeps_id_and_puts_old_into_trash(client):
    first = apply(client, [ECHO])["results"][0]
    cid = first["id"]
    old = client.get(f"/api/collections/{cid}").get_json()
    # eskisini o'zgartiramiz, so'ng replace
    old["item"] = old["item"][:2]
    client.put(f"/api/collections/{cid}", json=old)
    r = apply(client, [ECHO], [{"source": 0, "item": 0, "action": "replace"}])["results"][0]
    assert r["id"] == cid and r["replaced"] == cid
    assert count(client.get(f"/api/collections/{cid}").get_json()) == 23                    # yangi mazmun
    rows = client.get("/api/trash").get_json()
    assert len(rows) == 1 and rows[0]["kind"] == "collection" and rows[0]["origin"]["requests"] < 23    # eskisi (2 papka) savatda
    assert len(collections(client)) == 1


def test_merge_adds_only_new_items_and_is_idempotent(client):
    cid = apply(client, [ECHO])["results"][0]["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    removed = col["item"].pop()                                                             # oxirgi papkani olib tashlaymiz
    client.put(f"/api/collections/{cid}", json=col)
    before = count(client.get(f"/api/collections/{cid}").get_json())
    p = preview(client, ECHO)[0]["items"][0]["conflict"]["merge"]
    assert p["added_folders"] >= 1 and p["added_requests"] >= 1
    r = apply(client, [ECHO], [{"source": 0, "item": 0, "action": "merge"}])["results"][0]
    assert r["added_requests"] == p["added_requests"] and r["id"] == cid
    after = count(client.get(f"/api/collections/{cid}").get_json())
    assert after == before + p["added_requests"] == 23
    again = apply(client, [ECHO], [{"source": 0, "item": 0, "action": "merge"}])["results"][0]
    assert again["added_requests"] == 0 and again["added_folders"] == 0 and len(collections(client)) == 1
    del removed


def test_merge_never_overwrites_existing_requests_or_settings(client):
    cid = apply(client, [src("postman", "helpers.json")])["results"][0]["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    col["item"][0]["request"]["url"]["raw"] = "http://my-edit.test/"                         # foydalanuvchi tahriri (URL farqli → boshqa so'rov sifatida)
    col["item"][1]["name"] = "Mening nomim"
    col["variable"] = [{"key": "mine", "value": "1", "type": "default"}]
    client.put(f"/api/collections/{cid}", json=col)
    apply(client, [src("postman", "helpers.json")], [{"source": 0, "item": 0, "action": "merge"}])
    now = client.get(f"/api/collections/{cid}").get_json()
    assert now["item"][0]["request"]["url"]["raw"] == "http://my-edit.test/" and now["item"][1]["name"] == "Mening nomim"
    assert any(v["key"] == "mine" for v in now["variable"])


def test_skip_does_nothing(client):
    apply(client, [ECHO])
    n = len(collections(client))
    r = apply(client, [ECHO], [{"source": 0, "item": 0, "action": "skip"}])
    assert r["results"][0]["action"] == "skip" and len(collections(client)) == n


def test_environment_conflict_merge_keeps_existing_values_and_replace_trashes_old(client):
    env_src = src("postman", "environment.json")
    apply(client, [env_src])
    eid = client.get("/api/workspace").get_json()["environments"][0]["id"]
    env = client.get(f"/api/environments/{eid}").get_json()
    env["values"] = [{"key": "base_url", "value": "https://MINE", "enabled": True, "type": "default"}]
    client.put(f"/api/environments/{eid}", json=env)
    p = preview(client, env_src)[0]["items"][0]
    assert p["conflict"]["merge"]["added_variables"] == 3 and p["default_action"] == "copy"
    apply(client, [env_src], [{"source": 0, "item": 0, "action": "merge"}])
    vals = {v["key"]: v["value"] for v in client.get(f"/api/environments/{eid}").get_json()["values"]}
    assert vals["base_url"] == "https://MINE" and vals["port"] == "8080" and len(vals) == 4
    apply(client, [env_src], [{"source": 0, "item": 0, "action": "replace"}])
    assert {v["key"]: v["value"] for v in client.get(f"/api/environments/{eid}").get_json()["values"]}["base_url"] == "https://staging.example.test"
    assert any(r["kind"] == "environment" for r in client.get("/api/trash").get_json())
    apply(client, [env_src], [{"source": 0, "item": 0, "action": "copy"}])
    assert sorted(e["name"] for e in client.get("/api/workspace").get_json()["environments"]) == ["Staging", "Staging (2)"]


def test_globals_merge_and_replace_with_backup(client):
    client.put("/api/globals", json={"values": [{"key": "tenant", "value": "MINE", "enabled": True, "type": "default"}, {"key": "own", "value": "1", "enabled": True, "type": "default"}]})
    g = src("postman", "globals.json")
    assert preview(client, g)[0]["items"][0]["conflict"]["merge"]["added_variables"] == 1
    apply(client, [g], [{"source": 0, "item": 0, "action": "merge"}])
    vals = {v["key"]: v["value"] for v in client.get("/api/globals").get_json()["values"]}
    assert vals == {"tenant": "MINE", "own": "1", "global_secret": "g-123"}
    r = apply(client, [g], [{"source": 0, "item": 0, "action": "replace"}])["results"][0]
    assert r["backup"].endswith("pre-import-globals") and os.path.isdir(os.path.join(client.app.extensions["backup_dir"], r["backup"]))
    assert {v["key"] for v in client.get("/api/globals").get_json()["values"]} == {"tenant", "global_secret"}


def test_insomnia_creates_collection_and_environment_together(client):
    r = apply(client, [src("insomnia", "insomnia_v4.json")])
    assert [x["type"] for x in r["results"]] == ["collection", "environment"]
    assert client.get("/api/workspace").get_json()["environments"][0]["name"] == "Shop API · Production"


def test_legacy_import_endpoint_still_works_for_every_format(client):
    for p in (("postman", "twitter.json"), ("openapi", "petstore3.yaml"), ("insomnia", "insomnia_v4.json"), ("har", "sample.har"), ("curl", "multi.sh")):
        d = client.post("/api/import", json={"content": FX.joinpath(*p).read_text(encoding="utf-8"), "dry_run": True}).get_json()
        assert d["ok"] and d["requests"] > 0 and d["kind"] and d["name"], p
        d = client.post("/api/import", json={"content": FX.joinpath(*p).read_text(encoding="utf-8")}).get_json()
        assert d["ok"] and client.get(f"/api/collections/{d['id']}").status_code == 200
    assert client.post("/api/import", json={"content": "xxx yyy"}).status_code == 400


# ── eksport endpointlari ──
def test_export_endpoints_download_correct_files(client):
    cid = apply(client, [src("openapi", "petstore3.yaml")])["results"][0]["id"]
    r = client.get(f"/api/collections/{cid}/export")
    assert r.status_code == 200 and r.headers["Content-Disposition"].startswith("attachment") and r.headers["Content-Disposition"].endswith('.postman_collection.json"')
    assert json.loads(r.data)["info"]["schema"].endswith("v2.1.0/collection.json")
    j = client.get(f"/api/collections/{cid}/export?format=openapi")
    assert j.headers["Content-Disposition"].endswith('openapi.json"') and json.loads(j.data)["openapi"] == "3.0.3"
    y = client.get(f"/api/collections/{cid}/export?format=openapi-yaml")
    assert y.mimetype == "application/yaml" and y.data.startswith(b"openapi: 3.0.3")
    assert client.get(f"/api/collections/{cid}/export?format=zzz").status_code == 400
    assert client.get("/api/collections/nope/export").status_code == 404
    apply(client, [src("postman", "environment.json"), src("postman", "globals.json")])
    eid = client.get("/api/workspace").get_json()["environments"][0]["id"]
    e = json.loads(client.get(f"/api/environments/{eid}/export").data)
    assert e["_postman_variable_scope"] == "environment" and next(v for v in e["values"] if v["key"] == "api_token")["value"] == ""
    g = json.loads(client.get("/api/globals/export").data)
    assert g["_postman_variable_scope"] == "globals" and next(v for v in g["values"] if v["key"] == "global_secret")["value"] == ""
    assert client.get("/api/environments/nope/export").status_code == 404


def test_export_requires_session_token(client):
    anon = client.application.test_client()
    for url in ("/api/workspace/export", "/api/globals/export", "/api/collections/x/export", "/api/import/preview"):
        assert anon.get(url).status_code in (401, 405)
