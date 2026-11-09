"""Workspace zip: sukut bo'yicha maxfiy va Current qiymatlarsiz; ixtiyoriy parol bilan AES shifrlash; avtomatik zaxiralar to'liq."""
import base64
import io
import json
import os
import zipfile

import pytest

SECRET, CUR, TOKEN, GSEC = "TOP-SECRET-VALUE", "CURRENT-VALUE", "bearer-token-123", "GLOBAL-SECRET"


@pytest.fixture
def world(client):
    cid = client.post("/api/collections", json={"name": "C"}).get_json()["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    col["auth"] = {"type": "bearer", "bearer": [{"key": "token", "value": TOKEN, "type": "string"}]}
    col["variable"] = [{"key": "cs", "value": "COLL-SECRET", "type": "secret"}, {"key": "pub", "value": "public", "type": "default"}]
    col["item"] = [{"id": "r", "name": "R", "request": {"method": "GET", "header": [], "url": {"raw": "http://x/"}, "auth": {"type": "basic", "basic": [{"key": "username", "value": "bob"}, {"key": "password", "value": "REQ-PASS"}]}}, "response": []}]
    client.put(f"/api/collections/{cid}", json=col)
    eid = client.post("/api/environments", json={"name": "E"}).get_json()["id"]
    env = client.get(f"/api/environments/{eid}").get_json()
    env["values"] = [{"key": "s", "value": SECRET, "current": CUR, "enabled": True, "type": "secret"}, {"key": "p", "value": "init", "current": CUR + "-p", "enabled": True, "type": "default"}]
    client.put(f"/api/environments/{eid}", json=env)
    client.put("/api/globals", json={"values": [{"key": "g", "value": GSEC, "current": GSEC + "-c", "enabled": True, "type": "secret"}, {"key": "gp", "value": "gpub", "enabled": True, "type": "default"}]})
    client.app.extensions["db"].add_history("request", {"method": "GET", "url": "http://x/", "headers": [{"name": "Authorization", "value": "Bearer " + TOKEN}]})
    return cid, eid


def zip_text(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    return {n: z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n != "state.db"}, z.namelist()


def test_default_zip_has_no_secret_current_or_auth_values_and_no_database(client, world):
    r = client.get("/api/workspace/export")
    texts, names = zip_text(r.data)
    blob = "\n".join(texts.values())
    for leak in (SECRET, CUR, TOKEN, GSEC, "COLL-SECRET", "REQ-PASS"):
        assert leak not in blob, leak
    assert "state.db" not in names
    m = json.loads(texts["manifest.json"])
    assert m["secrets_included"] is False and m["includes_state"] is False and m["encrypted"] is False
    cid, eid = world
    env = json.loads(texts[f"environments/{eid}.json"])
    assert [(v["key"], v["value"], "current" in v) for v in env["values"]] == [("s", "", False), ("p", "init", False)]      # Initial qoladi, Current va secret yo'q
    col = json.loads(texts[f"collections/{cid}.json"])
    assert col["auth"]["bearer"][0]["value"] == "" and {v["key"]: v["value"] for v in col["variable"]} == {"cs": "", "pub": "public"}
    basic = {r["key"]: r["value"] for r in col["item"][0]["request"]["auth"]["basic"]}
    assert basic == {"username": "bob", "password": ""}                                    # login nomi qoladi, parol yo'q
    assert [v["value"] for v in json.loads(texts["globals.json"])["values"]] == ["", "gpub"]


def test_state_database_requires_secrets_flag_because_history_holds_tokens(client, world):
    r = client.post("/api/workspace/export", json={"state": True})                       # state so'raldi, lekin maxfiylar yo'q → baza kirmaydi
    assert "state.db" not in zip_text(r.data)[1]
    r = client.post("/api/workspace/export", json={"state": True, "secrets": True})
    assert "state.db" in zip_text(r.data)[1]


def test_opt_in_includes_everything_and_marks_manifest(client, world):
    r = client.post("/api/workspace/export", json={"secrets": True})
    texts, _ = zip_text(r.data)
    blob = "\n".join(texts.values())
    for must in (SECRET, CUR, TOKEN, GSEC, "COLL-SECRET", "REQ-PASS"):
        assert must in blob, must
    assert json.loads(texts["manifest.json"])["secrets_included"] is True


def test_encrypted_zip_is_not_readable_without_password_and_roundtrips_with_it(client, world):
    r = client.post("/api/workspace/export", json={"secrets": True, "password": "correct horse battery"})
    assert r.headers["Content-Disposition"].endswith('.zip.enc"')
    data = r.data
    assert data.startswith(b"APRZENC1") and SECRET.encode() not in data and not zipfile.is_zipfile(io.BytesIO(data))
    with pytest.raises(zipfile.BadZipFile):
        zipfile.ZipFile(io.BytesIO(data))
    payload = {"name": "ws.zip.enc", "content": base64.b64encode(data).decode(), "encoding": "base64"}
    p = client.post("/api/import/preview", json={"sources": [payload]}).get_json()["sources"][0]
    assert p["ok"] is False and p["code"] == "password_required"
    p = client.post("/api/import/preview", json={"sources": [{**payload, "password": "wrong password"}]}).get_json()["sources"][0]
    assert p["ok"] is False and p["code"] == "bad_password"
    p = client.post("/api/import/preview", json={"sources": [{**payload, "password": "correct horse battery"}]}).get_json()["sources"][0]
    assert p["ok"] and p["kind"] == "workspace"
    res = client.post("/api/import/apply", json={"sources": [{**payload, "password": "correct horse battery"}], "decisions": [{"source": 0, "item": i, "action": "copy"} for i in range(len(p["items"]))]}).get_json()
    assert res["ok"]
    envs = {e["name"]: e for e in client.get("/api/workspace").get_json()["environments"]}
    assert envs["E (2)"]["values"][0]["value"] == SECRET and envs["E (2)"]["values"][0]["current"] == CUR       # shifrlangan to'liq zaxira


def test_tampered_encrypted_zip_is_rejected(client, world):
    data = bytearray(client.post("/api/workspace/export", json={"secrets": True, "password": "longenough1"}).data)
    data[-5] ^= 0xFF
    p = client.post("/api/import/preview", json={"sources": [{"name": "a.enc", "content": base64.b64encode(bytes(data)).decode(), "encoding": "base64", "password": "longenough1"}]}).get_json()["sources"][0]
    assert not p["ok"] and p["code"] == "bad_password"


def test_short_password_rejected_and_get_never_takes_password(client, world):
    assert client.post("/api/workspace/export", json={"password": "short"}).status_code == 400
    r = client.get("/api/workspace/export?secrets=1&state=1&password=abcdefghi")             # GET sukut sozlamalardan ortiq narsani qabul qilmaydi
    texts, names = zip_text(r.data)
    assert SECRET not in "\n".join(texts.values()) and "state.db" not in names and r.mimetype == "application/zip"


def test_automatic_backups_remain_full_and_local(client, world):
    r = client.post("/api/backups")
    assert r.status_code == 200
    bdir = client.app.extensions["backup_dir"]
    latest = sorted(os.listdir(bdir))[-1]
    texts = []
    for root, _d, names in os.walk(os.path.join(bdir, latest, "workspace")):
        for n in names:
            if n.endswith(".json"):
                texts.append(open(os.path.join(root, n), encoding="utf-8").read())
    blob = "\n".join(texts)
    assert SECRET in blob and CUR in blob and TOKEN in blob                                # zaxira (backups/) — lokal va to'liq
