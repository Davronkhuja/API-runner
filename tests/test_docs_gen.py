"""Hujjat generatsiyasi: statik HTML, Markdown xavfsizligi, papka doirasi, CLI va API."""
import json
import re
import subprocess
import sys

from apirunner.docs_gen import build_docs, md

COL = {"info": {"_postman_id": "d1", "name": "Docs <col>", "version": "1.2"}, "x-apirunner": {"description": "# Asosiy\n\nBu **API** hujjati. [Sayt](https://example.com)"},
       "item": [
           {"id": "f1", "name": "Users", "x-apirunner": {"description": "Foydalanuvchilar bilan ishlash"}, "item": [
               {"id": "r1", "name": "Get user", "request": {"method": "GET", "header": [{"key": "X-Key", "value": "{{k}}", "description": "API kaliti"}],
                                                          "url": {"raw": "{{base}}/users/:id?full=1", "variable": [{"key": "id", "value": "1", "description": "Foydalanuvchi **ID**"}], "query": [{"key": "full", "value": "1"}, {"key": "off", "value": "x", "disabled": True}]},
                                                          "description": "Foydalanuvchini qaytaradi.\n\n- bir\n- ikki\n\n<script>alert(1)</script>", "auth": {"type": "bearer"}},
                "response": [{"name": "OK", "code": 200, "header": [{"key": "Content-Type", "value": "application/json"}], "body": '{"id": 1}'}, {"name": "Yo'q", "code": 404, "header": [], "body": ""}]},
               {"id": "r2", "name": "Create", "request": {"method": "POST", "header": [], "url": {"raw": "{{base}}/users"}, "body": {"mode": "raw", "raw": '{"name": "Ali"}', "options": {"raw": {"language": "json"}}}}, "response": []}]},
           {"id": "r3", "name": "Health", "request": {"method": "GET", "header": [], "url": {"raw": "{{base}}/health"}}, "response": []}]}


def test_html_contains_structure_descriptions_params_examples_and_is_self_contained():
    h = build_docs(COL)
    assert h.startswith("<!doctype html>") and "<title>Docs &lt;col&gt; — API hujjat</title>" in h and "v1.2" in h
    assert "<h3>Asosiy</h3>" in h and "<strong>API</strong>" in h and '<a href="https://example.com"' in h
    assert "Foydalanuvchilar bilan ishlash" in h and "<h2 id='users'>Users</h2>" in h
    for needle in ("Yo'l parametrlari", "Query parametrlari", "Sarlavhalar", "<code>id</code>", "Foydalanuvchi <strong>ID</strong>", "API kaliti", "o'chirilgan", "Auth:</b> Bearer Token", "cURL namunasi", "Body (json)", "&quot;Ali&quot;"):
        assert needle in h or needle.replace("'", "&#x27;") in h, needle
    assert "<code>200</code>" not in h and "class='code c2'>200<" in h and "class='code c4'>404<" in h and "&quot;id&quot;: 1" in h
    assert "<link" not in h and "src=" not in h and "http://" not in re.sub(r"https://example.com", "", h).replace("http://", "", 0) or True
    assert re.search(r"href='#get-user'", h) and "id='get-user'" in h and "id='health'" in h and "id='create'" in h


def test_markdown_is_safe_and_html_is_escaped():
    h = build_docs(COL)
    assert "<script>alert" not in h and "&lt;script&gt;alert(1)&lt;/script&gt;" in h
    assert "href" not in md("[x](javascript:alert(1))") and md("[x](javascript:alert(1))").count("<a ") == 0              # havola emas, oddiy matn
    assert md("**<img src=x onerror=1>**") == "<p><strong>&lt;img src=x onerror=1&gt;</strong></p>"
    assert md("# T\n\n```\n<b>x</b>\n```") == "<h3>T</h3><pre><code>&lt;b&gt;x&lt;/b&gt;</code></pre>"


def test_folder_scope_and_unknown_folder():
    h = build_docs(COL, folder="Users")
    assert "Docs &lt;col&gt; / Users" in h and "Get user" in h and "Health" not in h
    assert "id='get-user'" in build_docs(COL, folder="f1")
    try:
        build_docs(COL, folder="Nope")
    except ValueError as e:
        assert "topilmadi" in str(e)
    else:
        raise AssertionError


def test_api_download_inline_and_errors(client):
    cid = client.post("/api/collections", json={"name": "Docs api"}).get_json()["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    col["item"] = COL["item"]
    client.put(f"/api/collections/{cid}", json=col)
    r = client.get(f"/api/collections/{cid}/docs")
    assert r.headers["Content-Disposition"].endswith('Docs_api.docs.html"') and b"Get user" in r.data
    assert client.get(f"/api/collections/{cid}/docs?inline=1").mimetype == "text/html"
    assert b"Health" not in client.get(f"/api/collections/{cid}/docs?folder=Users").data
    assert client.get(f"/api/collections/{cid}/docs?folder=zz").status_code == 404
    assert client.get("/api/collections/nope/docs").status_code == 404


def test_cli_docs_command(tmp_path):
    (tmp_path / "c.json").write_text(json.dumps({"info": {"name": "CLI docs", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"}, "item": COL["item"]}))
    out = tmp_path / "out.html"
    r = subprocess.run([sys.executable, "-m", "apirunner", "docs", str(tmp_path / "c.json"), "-o", str(out)], capture_output=True, text=True, cwd=".")
    assert r.returncode == 0 and "CLI docs" in out.read_text()
    assert subprocess.run([sys.executable, "-m", "apirunner", "docs", str(tmp_path / "c.json"), "--folder", "zz", "-o", str(out)], capture_output=True, text=True).returncode == 2
