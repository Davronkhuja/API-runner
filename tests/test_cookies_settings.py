"""Cookie jar (SQLite) va so'rov sozlamalari: redirect, proxy, CA, mijoz sertifikati."""
import http.server
import json
import shutil
import ssl
import subprocess
import threading

import httpx
import pytest
from werkzeug.serving import make_server

from apirunner.storage.cookies import CookieStore


def post(client, **cfg):
    return client.post("/run_one", json=cfg).get_json()


# ── cookie jar ──
def test_cookie_is_stored_sent_back_and_listed(client, echo):
    d = post(client, url=echo + "/cookie/set?name=sid&value=abc")
    assert d["status"] == 200 and d["set_cookies"] and d["set_cookies"][0].startswith("sid=abc")
    assert post(client, url=echo + "/cookie/echo")["response"] == {"sid": "abc"}
    rows = client.get("/api/cookies").get_json()
    assert [(r["name"], r["value"], r["domain"], r["path"]) for r in rows] == [("sid", "abc", "127.0.0.1", "/")]


def test_use_cookies_false_neither_sends_nor_stores(client, echo):
    post(client, url=echo + "/cookie/set?name=a&value=1")
    assert post(client, url=echo + "/cookie/echo", use_cookies=False)["response"] == {}
    post(client, url=echo + "/cookie/set?name=b&value=2", use_cookies=False)
    assert {r["name"] for r in client.get("/api/cookies").get_json()} == {"a"}


def test_server_side_deletion_removes_cookie_from_store(client, echo):
    post(client, url=echo + "/cookie/set?name=gone&value=1")
    assert len(client.get("/api/cookies").get_json()) == 1
    post(client, url=echo + "/cookie/del?name=gone")
    assert client.get("/api/cookies").get_json() == []
    assert post(client, url=echo + "/cookie/echo")["response"] == {}


def test_httponly_flag_is_recorded(client, echo):
    post(client, url=echo + "/cookie/set?name=h&value=1&httponly=1")
    assert client.get("/api/cookies").get_json()[0]["httponly"] == 1


def test_manual_cookie_crud_and_expiry(client, echo):
    ok = lambda **c: client.post("/api/cookies", json=c).status_code  # noqa: E731
    assert ok(domain="127.0.0.1", name="m1", value="v") == 200 and ok(domain="x.com", name="m2", value="v") == 200
    assert ok(domain="", name="bad") == 400
    assert ok(domain="127.0.0.1", name="old", value="v", expires=1) == 200            # o'tib ketgan — ro'yxatda ko'rinmaydi
    names = {r["name"] for r in client.get("/api/cookies").get_json()}
    assert names == {"m1", "m2"}
    assert post(client, url=echo + "/cookie/echo")["response"] == {"m1": "v"}          # qo'lda qo'shilgani yuboriladi
    assert client.delete("/api/cookies?domain=127.0.0.1&path=/&name=m1").get_json()["deleted"] == 1
    assert client.delete("/api/cookies?domain=x.com").get_json()["deleted"] == 1
    ok(domain="a.com", name="z", value="1")
    assert client.delete("/api/cookies").get_json()["deleted"] == 1
    assert client.get("/api/cookies").get_json() == []


def test_cookies_shared_across_batch_rows_and_survive_restart(client, echo, isolated):
    cfg = {"url": echo + "/cookie/setecho", "rows": [{}, {}], "concurrency": 1}
    jid = client.post("/run", json=cfg).get_json()["job_id"]
    raw = client.get(f"/stream/{jid}").get_data(as_text=True)
    results = [json.loads(l[6:]) for l in raw.splitlines() if l.startswith("data: ") and '"index"' in l]
    results.sort(key=lambda r: r["index"])
    assert results[0]["response"] == {} and results[1]["response"] == {"seen": "yes"}
    again = CookieStore(str(isolated / "workspace" / "state.db"))                     # yangi jarayon: bazadan o'qiydi
    assert [c["name"] for c in again.list()] == ["seen"]


# ── redirect sozlamalari ──
def test_follow_redirects_toggle_and_max_redirects(client, echo):
    assert post(client, url=echo + "/redirect")["status"] == 200
    d = post(client, url=echo + "/redirect", follow_redirects=False)
    assert d["status"] == 302 and d["resp_headers"]["location"].endswith("/echo")
    assert post(client, url=echo + "/redir/3", max_redirects=5)["status"] == 200
    d = post(client, url=echo + "/redir/5", max_redirects=2)
    assert d["status"] == "ERR" and "redirect" in d["response"].lower()
    assert post(client, url=echo + "/redir/2")["redirects"] == 3


# ── proxy ──
class _Proxy(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        r = httpx.get(self.path, trust_env=False)
        self.send_response(r.status_code)
        self.send_header("X-Proxied", "1")
        self.send_header("Content-Type", r.headers.get("content-type", "text/plain"))
        self.send_header("Content-Length", str(len(r.content)))
        self.end_headers()
        self.wfile.write(r.content)

    def log_message(self, *a):
        pass


def test_proxy_is_used(client, echo):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Proxy)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        d = post(client, url=echo + "/echo", proxy=f"http://127.0.0.1:{srv.server_port}")
        assert d["status"] == 200 and d["resp_headers"].get("x-proxied") == "1"
        assert "x-proxied" not in post(client, url=echo + "/echo")["resp_headers"]
    finally:
        srv.shutdown()


# ── CA + mijoz sertifikati (openssl kerak) ──
@pytest.fixture(scope="module")
def tls(tmp_path_factory):
    if not shutil.which("openssl"):
        pytest.skip("openssl yo'q")
    d = tmp_path_factory.mktemp("tls")
    sh = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True)  # noqa: E731
    sh("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.pem", "-days", "2", "-subj", "/CN=TestCA")
    (d / "ext.cnf").write_text("subjectAltName=IP:127.0.0.1\n")
    for name in ("srv", "cli"):
        sh("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", f"{name}.key", "-out", f"{name}.csr", "-subj", f"/CN={name}")
        sh("openssl", "x509", "-req", "-in", f"{name}.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-out", f"{name}.pem", "-days", "2", "-extfile", "ext.cnf")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(d / "srv.pem"), str(d / "srv.key"))
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_verify_locations(str(d / "ca.pem"))
    srv = make_server("127.0.0.1", 0, lambda env, sr: (sr("200 OK", [("Content-Type", "text/plain")]), [b"tls-ok"])[1], ssl_context=ctx)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield {"url": f"https://127.0.0.1:{srv.server_port}/", "dir": d}
    srv.shutdown()


def test_ca_bundle_and_client_cert(client, tls):
    d = str(tls["dir"])
    base = {"url": tls["url"]}
    assert post(client, **base)["status"] == "ERR"                                                          # CA'ga ishonilmaydi
    assert post(client, **base, ca_bundle=d + "/ca.pem")["status"] == "ERR"                                   # mijoz sertifikati talab qilinadi
    ok = post(client, **base, ca_bundle=d + "/ca.pem", cert=d + "/cli.pem", cert_key=d + "/cli.key")
    assert ok["status"] == 200 and ok["response"] == "tls-ok", ok
    assert post(client, **base, ssl_verify=False, cert=d + "/cli.pem", cert_key=d + "/cli.key")["status"] == 200   # tekshiruvsiz, lekin sertifikat bilan


def test_missing_cert_files_give_clear_error(client, tls):
    d = post(client, url=tls["url"], ca_bundle="/no/such/ca.pem")
    assert d["status"] == "ERR" and "CA fayli topilmadi" in d["response"]
    d = post(client, url=tls["url"], cert="/no/cert.pem")
    assert "Sertifikat fayli topilmadi" in d["response"]


def test_settings_roundtrip_in_workspace_meta(client):
    s = {"follow_redirects": False, "proxy": "http://p:1", "max_redirects": 3}
    assert client.put("/api/workspace/meta", json={"settings": s}).get_json()["meta"]["settings"] == s
    assert client.get("/api/workspace").get_json()["meta"]["settings"] == s
