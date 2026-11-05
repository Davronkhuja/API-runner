"""Workspace bo'ylab Find & Replace: qidirish, oldindan ko'rish, tanlangan almashtirish, zaxira, maxfiy qiymatlar."""
import os

import pytest


def seed(client):
    cid = client.post("/api/collections", json={"name": "Col"}).get_json()["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    col["variable"] = [{"key": "host", "value": "api.old.example", "type": "default"}]
    col["item"] = [
        {"id": "r1", "name": "Old users", "request": {"method": "GET", "header": [{"key": "X-Host", "value": "api.old.example"}], "description": "calls api.old.example",
                                                      "url": {"raw": "https://api.old.example/v1/users?host=api.old.example", "query": [{"key": "host", "value": "api.old.example"}]},
                                                      "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "tok-api.old.example", "type": "string"}]},
                                                      "body": {"mode": "raw", "raw": '{"u": "https://api.old.example"}'}},
         "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": ["const h = 'api.old.example';", "pm.test('x', () => {});"]}}], "response": []},
        {"id": "f", "name": "Folder", "item": [{"id": "r2", "name": "Other", "request": {"method": "POST", "header": [], "url": {"raw": "https://keep.example/x"}}, "response": []}]},
    ]
    client.put(f"/api/collections/{cid}", json=col)
    eid = client.post("/api/environments", json={"name": "Dev"}).get_json()["id"]
    env = client.get(f"/api/environments/{eid}").get_json()
    env["values"] = [{"key": "base", "value": "https://api.old.example", "current": "https://api.old.example/cur", "enabled": True, "type": "default"},
                     {"key": "secret", "value": "s-api.old.example", "enabled": True, "type": "secret"}]
    client.put(f"/api/environments/{eid}", json=env)
    return cid, eid


def search(client, **kw):
    r = client.post("/api/find-replace/search", json={"query": "api.old.example", "replacement": "api.new.example", **kw})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def test_search_lists_fields_with_previews_and_masks_secrets(client):
    seed(client)
    d = search(client)
    fields = {(r["owner_name"], r["field"]) for r in d["results"]}
    assert ("Old users", "URL") in fields and ("Old users", "Header · X-Host (value)") in fields and ("Old users", "Body") in fields
    assert ("Old users", "Skript · test") in fields and ("Old users", "Tavsif") in fields and ("Col", "O'zgaruvchi · host (value)") in fields
    assert any(r["field"].startswith("Param · host") for r in d["results"]) and any(r["field"].startswith("Auth · bearer") for r in d["results"])
    url = next(r for r in d["results"] if r["field"] == "URL")
    assert url["count"] == 2 and url["snippets"][0]["replacement"] == "api.new.example"
    sec = next(r for r in d["results"] if r["secret"] and r["doc_kind"] == "environment")
    assert sec["snippets"] == []                                                  # maxfiy qiymat ko'rsatilmaydi
    assert not any(r["owner_name"] == "Other" for r in d["results"])
    assert d["total"] >= 10


def test_targets_and_collection_scope_filter(client):
    cid, _ = seed(client)
    only_url = search(client, targets=["url"])
    assert {r["field"] for r in only_url["results"]} == {"URL"}
    env_only = search(client, targets=["environments"])
    assert {r["doc_kind"] for r in env_only["results"]} == {"environment"}
    scoped = search(client, collection_ids=[cid])
    assert all(r["doc_kind"] == "collection" for r in scoped["results"])         # collection tanlansa muhitlarga tegilmaydi


def test_case_word_and_regex_options(client):
    seed(client)
    assert search(client, query="API.OLD.EXAMPLE", case=True)["results"] == []
    assert search(client, query="API.OLD.EXAMPLE")["results"]
    assert search(client, query="old", word=True, targets=["name"])["results"][0]["owner_name"] == "Old users"
    assert search(client, query="ol", word=True, targets=["name"])["results"] == []
    d = search(client, query=r"api\.(\w+)\.example", replacement=r"api.\1-v2.example", regex=True, targets=["url"])
    assert d["results"][0]["snippets"][0]["replacement"] == "api.old-v2.example"
    r = client.post("/api/find-replace/search", json={"query": "(", "regex": True})
    assert r.status_code == 400 and "Regex" in r.get_json()["error"]
    assert client.post("/api/find-replace/search", json={"query": ""}).status_code == 400


def test_apply_selected_only_makes_backup_and_keeps_structure(client):
    cid, eid = seed(client)
    d = search(client)
    pick = [r["id"] for r in d["results"] if r["field"] in ("URL", "Body") or r["field"] == "Skript · test"]
    r = client.post("/api/find-replace/apply", json={"query": "api.old.example", "replacement": "api.new.example", "ids": pick})
    j = r.get_json()
    assert r.status_code == 200 and j["replacements"] >= 4 and j["skipped"] == [] and j["backup"].endswith("pre-find-replace")
    col = client.get(f"/api/collections/{cid}").get_json()
    req = col["item"][0]["request"]
    assert req["url"]["raw"] == "https://api.new.example/v1/users?host=api.new.example"
    assert req["body"]["raw"] == '{"u": "https://api.new.example"}'
    assert col["item"][0]["event"][0]["script"]["exec"] == ["const h = 'api.new.example';", "pm.test('x', () => {});"]      # qatorlar ro'yxati saqlandi
    assert req["header"][0]["value"] == "api.old.example"                         # tanlanmagan tegilmadi
    assert col["variable"][0]["value"] == "api.old.example"
    assert col["item"][0]["id"] == "r1" and req["method"] == "GET"
    assert os.path.isdir(os.path.join(client.app.extensions["backup_dir"], j["backup"]))
    again = search(client)
    assert not any(r["field"] == "URL" for r in again["results"])


def test_apply_all_including_environment_and_secret(client):
    cid, eid = seed(client)
    ids = [r["id"] for r in search(client)["results"]]
    j = client.post("/api/find-replace/apply", json={"query": "api.old.example", "replacement": "api.new.example", "ids": ids}).get_json()
    assert j["documents"] == 2
    env = client.get(f"/api/environments/{eid}").get_json()
    assert env["values"][0]["value"] == "https://api.new.example" and env["values"][0]["current"] == "https://api.new.example/cur"
    assert env["values"][1]["value"] == "s-api.new.example"                      # maxfiy qiymat ham (ko'rsatilmasa-da) almashtiriladi
    assert search(client)["results"] == []


def test_apply_requires_ids_bad_backref_and_stale_ids(client):
    seed(client)
    assert client.post("/api/find-replace/apply", json={"query": "x", "ids": []}).status_code == 400
    ids = [r["id"] for r in search(client, query="api.old.example", targets=["url"])["results"]]
    bad = client.post("/api/find-replace/apply", json={"query": "(old)", "regex": True, "replacement": r"\2", "ids": ids})
    assert bad.status_code == 400
    j = client.post("/api/find-replace/apply", json={"query": "api.old.example", "replacement": "z", "ids": ids + ["c:nope:x:y"]}).get_json()
    assert j["skipped"] == ["c:nope:x:y"]


def test_literal_replacement_is_not_regex_expanded(client):
    cid, _ = seed(client)
    ids = [r["id"] for r in search(client, targets=["url"])["results"]]
    client.post("/api/find-replace/apply", json={"query": "api.old.example", "replacement": r"a\1$&b", "ids": ids})
    assert client.get(f"/api/collections/{cid}").get_json()["item"][0]["request"]["url"]["raw"].startswith(r"https://a\1$&b/v1")
