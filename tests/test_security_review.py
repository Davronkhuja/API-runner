"""Bosqich 8 xavfsizlik ko'rigi (docs/security-review.md): Origin, sarlavhalar, token jurnali, fayl siyosati, zip, Markdown XSS, port bog'lanishi."""
import io
import json
import logging
import os
import zipfile

import pytest
import requests

from apirunner.api import security
from apirunner.docs_gen import md
from tests.conftest import TOKEN


# ── Origin / Host / sarlavhalar / jurnal ──
@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:9999", "null", "https://evil.example", "http://localhost.evil.com"])
def test_origin_must_be_exactly_this_server(client, origin):
    r = client.post("/api/collections", json={"name": "x"}, headers={"Origin": origin, "Host": "127.0.0.1:5050"})
    assert r.status_code == 403


def test_same_origin_with_port_is_accepted(client):
    r = client.get("/api/workspace", headers={"Origin": "http://127.0.0.1:5050", "Host": "127.0.0.1:5050"})
    assert r.status_code == 200


def test_dot_localhost_hosts_are_allowed_but_lookalikes_are_not(client):
    assert client.get("/saved", headers={"Host": "api-runner.localhost"}).status_code == 200
    assert client.get("/saved", headers={"Host": "api-runner.localhost", "Origin": "http://api-runner.localhost"}).status_code == 200
    for h in ("localhost.evil.com", "evil.localhost.com", "notlocalhost", "x.localhost.evil.com"):
        assert client.get("/saved", headers={"Host": h}).status_code == 403, h


def test_security_headers_on_api_and_index(client):
    for path in ("/api/workspace", "/"):
        h = client.get(path).headers
        assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY" and "frame-ancestors 'none'" in h["Content-Security-Policy"]


def test_token_is_redacted_from_access_log():
    rec = logging.LogRecord("werkzeug", logging.INFO, "", 0, '%s - - "%s" %s', ("127.0.0.1", "GET /stream/x?token=SECRET123&a=1 HTTP/1.1", "200"), None)
    for f in logging.getLogger("werkzeug").filters:
        f.filter(rec)
    assert "SECRET123" not in rec.getMessage() and "a=1" in rec.getMessage()


# ── mock va proxy faqat loopback'da ──
def test_mock_and_proxy_bind_to_loopback_only(client):
    col = {"info": {"_postman_id": "s1", "name": "S"}, "item": [{"id": "a", "name": "A", "request": {"method": "GET", "header": [], "url": {"raw": "http://x/a"}},
                                                                "response": [{"name": "ok", "code": 200, "header": [], "body": "{}", "originalRequest": {"method": "GET", "url": {"raw": "x"}}}]}]}
    client.app.extensions["workspace"].save_collection(col)
    m = client.post("/api/mocks", json={"collection_id": "s1", "host": "0.0.0.0"}).get_json()        # host parametri e'tiborga olinmaydi
    srv = client.app.extensions["mocks"].get(m["id"]).srv
    assert srv.server_address[0] == "127.0.0.1"
    client.post(f"/api/mocks/{m['id']}/stop")
    p = client.post("/api/proxy/start", json={"port": 0, "host": "0.0.0.0"}).get_json()
    try:
        assert client.app.extensions["proxy"].proxy.srv.server_address[0] == "127.0.0.1" and p["url"].startswith("http://127.0.0.1:")
    finally:
        client.post("/api/proxy/stop")


def test_proxy_rejects_relative_paths(client):
    p = client.post("/api/proxy/start", json={}).get_json()
    try:
        assert requests.get(p["url"] + "/etc/passwd", timeout=3).status_code == 400
    finally:
        client.post("/api/proxy/stop")


# ── fayl yo'llari ──
def test_file_policy_does_not_allow_workspace_database_or_json(client, echo):
    ws_root = client.app.extensions["workspace"].root
    secret = os.path.join(ws_root, "state.db")
    from apirunner.core.engine import ExecContext, FilePolicyError, _resolve_file
    roots = client.app.extensions["jobs"].allowed_file_roots
    ctx = ExecContext(variables={}, allowed_file_roots=roots)
    with pytest.raises(FilePolicyError):
        _resolve_file(secret, ctx)
    with pytest.raises(FilePolicyError):
        _resolve_file(os.path.join(ws_root, "workspace.json"), ctx)
    with pytest.raises(FilePolicyError):
        _resolve_file("/etc/passwd", ctx)
    managed = os.path.join(ws_root, "files", "a" * 64)
    assert _resolve_file(managed, ctx) == os.path.realpath(managed)


def test_adopt_only_from_upload_dir(client):
    assert client.post("/api/files/adopt", json={"path": "/etc/passwd"}).status_code == 400
    assert client.post("/api/files/adopt", json={"path": "../../etc/passwd"}).status_code == 400


# ── zip import ──
def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n, d in entries.items():
            z.writestr(n, d)
    return buf.getvalue()


def test_zip_import_ignores_traversal_names_and_never_writes_outside(isolated, make_client):
    from apirunner.exporters.workspace import KIND
    manifest = json.dumps({"kind": KIND, "app_version": "x"})
    evil = _zip({"manifest.json": manifest, "files/../../pwned.txt": "x", "files/..\\..\\pwned2.txt": "x", "/abs/pwned3.txt": "x",
                 "collections/../../evil.json": json.dumps({"info": {"name": "E"}, "item": []}), "files/" + "b" * 64 + "/ok.txt": "fine"})
    c = make_client()
    r = c.post("/api/import/apply", json={"sources": [{"name": "evil.zip", "content": __import__("base64").b64encode(evil).decode(), "encoding": "base64"}]})
    for p in isolated.rglob("pwned*"):
        pytest.fail(f"zip tashqariga yozdi: {p}")
    assert not (isolated.parent / "evil.json").exists() and not (isolated / "evil.json").exists()
    assert r.status_code == 200 and not r.get_json().get("errors"), r.get_json()


def test_read_zip_drops_dotdot_entries():
    from apirunner.exporters.workspace import KIND, read_zip
    data = _zip({"manifest.json": json.dumps({"kind": KIND}), "files/../x": "1", "files/" + "c" * 64 + "/f": "2", "collections/../../e.json": "{}"})
    z = read_zip(data)
    assert list(z["files"]) == ["files/" + "c" * 64 + "/f"] and z["collections"] == []


# ── Markdown XSS (docs generatsiyasi) ──
PAYLOADS = ["<img src=x onerror=alert(1)>", "<script>alert(1)</script>", "[x](javascript:alert(1))", '[x](https://a.com" onmouseover="alert(1))',
            "[x](data:text/html;base64,PHNjcmlwdD4=)", "**<b onclick=1>**", "`<svg onload=1>`", "```\n</code></pre><script>1</script>\n```",
            "| a |\n|---|\n| <img src=x onerror=1> |", "> <iframe src=javascript:1>", "\x000\x00", "[a](<javascript:1>)"]


@pytest.mark.parametrize("src", PAYLOADS)
def test_markdown_output_never_contains_active_html(src):
    import re
    out = md(src)
    stripped = re.sub(r"</?(p|strong|em|del|code|pre|a|blockquote|ul|ol|li|h[1-6]|hr|br|table|thead|tbody|tr|th|td)\b[^>]*>", "", out)
    assert "<" not in stripped, (src, out)                                      # faqat ruxsat etilgan teglar; qolgani escape qilingan
    assert not re.search(r'<a [^>]*href="(?!https?:|mailto:)', out) and not re.search(r'<[^>]* on\w+=', out), (src, out)


def test_generated_docs_escape_names_descriptions_and_example_bodies():
    from apirunner.docs_gen import build_docs
    x = "<script>alert(1)</script>"
    col = {"info": {"_postman_id": "d1", "name": x, "description": x}, "item": [{"id": "a", "name": x, "request": {"method": "GET", "header": [{"key": x, "value": x}], "url": {"raw": "http://h/" + x}, "description": x},
                                                                           "response": [{"name": x, "code": 200, "header": [{"key": x, "value": x}], "body": x, "originalRequest": {"method": "GET", "url": {"raw": "x"}}}]}]}
    html = build_docs(col, None)
    assert "<script>alert" not in html and "&lt;script&gt;" in html
