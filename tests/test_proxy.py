"""Proxy capture: HTTP forward + yozib olish, CONNECT tunnel, collection'ga saqlash."""
import pytest
import requests

from apirunner.proxy import ProxyServer, entries_to_items


@pytest.fixture
def proxy():
    p = ProxyServer().start()
    yield p
    p.stop()


def via(p):
    return {"http": p.url}


def test_forwards_and_captures_request_and_response(proxy, echo):
    r = requests.post(echo + "/echo?a=1", json={"x": 1}, headers={"X-T": "v"}, proxies=via(proxy))
    assert r.status_code == 200 and r.json()["json"] == {"x": 1} and r.json()["args"] == {"a": ["1"]}
    e = proxy.entries(full=True)[0]
    assert e["method"] == "POST" and e["url"].endswith("/echo?a=1") and e["status"] == 200 and e["kind"] == "http"
    assert ("X-T", "v") in [tuple(h) for h in e["request_headers"]] and '"x": 1' in e["request_body"] and '"json"' in e["response_body"]
    assert "request_body" not in proxy.entries()[0]                        # ro'yxat yengil


def test_upstream_error_is_502_and_logged(proxy):
    r = requests.get("http://127.0.0.1:1/x", proxies=via(proxy))
    assert r.status_code == 502
    assert proxy.entries()[0]["status"] == 502


def test_connect_tunnel_is_logged_without_body(proxy, echo):
    import socket
    host, port = echo.replace("http://", "").split(":")
    s = socket.create_connection(("127.0.0.1", proxy.port))
    s.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
    assert b"200" in s.recv(1024)
    s.sendall(b"GET /echo HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n")
    assert b"200 OK" in s.recv(4096)
    s.close()
    e = proxy.entries()[0]
    assert e["kind"] == "tunnel" and e["method"] == "CONNECT"
    assert entries_to_items(proxy.entries(full=True)) == []                # tunnel collection'ga saqlanmaydi


def test_api_start_stop_save_to_collection(client, echo):
    assert client.get("/api/proxy").get_json()["running"] is False
    assert client.post("/api/proxy/save", json={}).status_code == 409
    d = client.post("/api/proxy/start", json={}).get_json()
    assert d["running"] and client.post("/api/proxy/start", json={}).status_code == 400
    try:
        requests.get(echo + "/echo?q=2", proxies={"http": d["url"]})
        requests.get(echo + "/text", proxies={"http": d["url"]})
        st = client.get("/api/proxy").get_json()
        assert len(st["entries"]) == 2 and client.get(f"/api/proxy?from={st['next']}").get_json()["entries"] == []
        cid = client.post("/api/collections", json={"name": "Cap"}).get_json()["id"]
        r = client.post("/api/proxy/save", json={"collection_id": cid, "seqs": [st["entries"][0]["seq"]], "folder_name": "Sessiya"})
        assert r.get_json()["saved"] == 1
        col = client.get(f"/api/collections/{cid}").get_json()
        f = col["item"][-1]
        assert f["name"] == "Sessiya" and f["item"][0]["request"]["method"] == "GET" and f["item"][0]["response"][0]["code"] == 200
        assert f["item"][0]["request"]["url"]["query"] == [{"key": "q", "value": "2"}]
        assert client.post("/api/proxy/save", json={"collection_id": "nope"}).status_code == 404
    finally:
        assert client.post("/api/proxy/stop").get_json()["ok"]
    assert client.get("/api/proxy").get_json()["running"] is False
    assert client.post("/api/proxy/start", json={"port": 70000}).status_code == 400
