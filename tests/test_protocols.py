"""WebSocket va SSE sessiyalari: lokal serverlar bilan (tashqi tarmoq yo'q)."""
import base64
import json
import time

import pytest


def connect(client, kind, url, headers=None, options=None, **spec):
    body = {"kind": kind, "spec": {"url": url, "method": "GET", "headers": [{"name": k, "value": v} for k, v in (headers or {}).items()], "params": [], "env_vars": spec.pop("env_vars", {}), **spec}, "options": options or {}}
    return client.post("/api/protocols/connect", json=body)


def wait(client, sid, pred, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        d = client.get(f"/api/protocols/{sid}/events").get_json()
        if pred(d):
            return d
        time.sleep(0.03)
    raise AssertionError("shart bajarilmadi: " + json.dumps(client.get(f"/api/protocols/{sid}/events").get_json())[:800])


def types(d):
    return [e["type"] for e in d["events"]]


def msgs(d, direction=None):
    return [e for e in d["events"] if e["type"] == "message" and (direction is None or e["dir"] == direction)]


def send(client, sid, data, kind="text", **kw):
    return client.post(f"/api/protocols/{sid}/send", json={"data": data, "kind": kind, **kw})


# ── WebSocket ──
def test_ws_connect_send_receive_text_json_binary_and_close(client, ws_server):
    r = connect(client, "ws", ws_server.url + "/echo")
    assert r.status_code == 200, r.get_data(as_text=True)
    sid = r.get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "open")
    assert types(d)[:2] == ["connecting", "open"]
    assert send(client, sid, "hello").status_code == 200
    assert send(client, sid, '{"a": 1}', "json").status_code == 200
    assert send(client, sid, base64.b64encode(b"\x00\x01\xfe").decode(), "binary", encoding="base64").status_code == 200
    assert send(client, sid, "00 ff 10", "binary", encoding="hex").status_code == 200
    d = wait(client, sid, lambda d: len(msgs(d, "in")) == 4)
    out, inn = msgs(d, "out"), msgs(d, "in")
    assert [m["data"] for m in out[:2]] == ["hello", '{"a": 1}'] and [m["kind"] for m in out] == ["text", "text", "binary", "binary"]
    assert [m["data"] for m in inn[:2]] == ["hello", '{"a": 1}']
    assert base64.b64decode(inn[2]["data"]) == b"\x00\x01\xfe" and inn[2]["size"] == 3 and inn[3]["kind"] == "binary" and base64.b64decode(inn[3]["data"]) == b"\x00\xff\x10"
    assert out[0]["size"] == 5 and d["counts"]["in"] == 4 and d["counts"]["bytes_out"] == 5 + 8 + 3 + 3
    assert client.post(f"/api/protocols/{sid}/close").status_code == 200
    d = wait(client, sid, lambda d: d["status"] == "closed")
    assert types(d)[-2:] == ["close", "closed"] and d["events"][-2]["code"] == 1000


def test_ws_headers_subprotocol_and_variables(client, ws_server):
    r = connect(client, "ws", ws_server.url + "/headers?x={{q}}", headers={"X-Token": "{{tok}}", "X-Plain": "p"}, options={"subprotocols": ["chat", "json.v1"]}, env_vars={"q": "7", "tok": "abc"})
    sid = r.get_json()["id"]
    d = wait(client, sid, lambda d: len(msgs(d, "in")) == 1)
    got = json.loads(msgs(d, "in")[0]["data"])
    h = {k.lower(): v for k, v in got["headers"].items()}
    assert h["x-token"] == "abc" and h["x-plain"] == "p" and got["subprotocol"] == "chat" and got["path"] == "/headers?x=7"
    opened = next(e for e in d["events"] if e["type"] == "open")
    assert opened["subprotocol"] == "chat" and opened["status"] == 101
    client.post(f"/api/protocols/{sid}/close")


def test_ws_message_variables_are_substituted_including_dynamic(client, ws_server):
    sid = connect(client, "ws", ws_server.url + "/echo", env_vars={"user": "Ali"}).get_json()["id"]
    wait(client, sid, lambda d: d["status"] == "open")
    send(client, sid, '{"hi": "{{user}}", "id": "{{$guid}}"}', "json")
    d = wait(client, sid, lambda d: len(msgs(d, "in")) == 1)
    got = json.loads(msgs(d, "in")[0]["data"])
    assert got["hi"] == "Ali" and len(got["id"]) == 36
    client.post(f"/api/protocols/{sid}/close")


def test_ws_auth_bearer_and_rejection(client, ws_server):
    bad = connect(client, "ws", ws_server.url + "/secure").get_json()["id"]
    d = wait(client, bad, lambda d: d["status"] == "closed")
    assert any("HTTP 401" in e.get("message", "") for e in d["events"] if e["type"] == "error")
    ok = connect(client, "ws", ws_server.url + "/secure", authorization="Bearer s3cret").get_json()["id"]
    wait(client, ok, lambda d: d["status"] == "open")
    client.post(f"/api/protocols/{ok}/close")
    jwt = connect(client, "ws", ws_server.url + "/headers", auth_config={"type": "jwt", "secret": "k", "payload": '{"a":1}'}).get_json()["id"]
    d = wait(client, jwt, lambda d: len(msgs(d, "in")) == 1)
    assert {k.lower(): v for k, v in json.loads(msgs(d, "in")[0]["data"])["headers"].items()}["authorization"].startswith("Bearer eyJ")
    client.post(f"/api/protocols/{jwt}/close")


def test_ws_digest_auth_is_rejected_with_explanation(client, ws_server):
    r = connect(client, "ws", ws_server.url + "/echo", auth_config={"type": "digest", "username": "a", "password": "b"})
    assert r.status_code == 400 and "Digest" in r.get_json()["error"]


def test_ws_server_close_code_and_reason(client, ws_server):
    sid = connect(client, "ws", ws_server.url + "/bye").get_json()["id"]
    wait(client, sid, lambda d: d["status"] == "open")
    send(client, sid, "anything")
    d = wait(client, sid, lambda d: d["status"] == "closed")
    c = next(e for e in d["events"] if e["type"] == "close")
    assert c["code"] == 4001 and c["reason"] == "bye now"


def test_ws_auto_reconnect_after_abnormal_drop_with_limits(client, ws_server):
    opts = {"reconnect": {"enabled": True, "delay_ms": 30, "max_attempts": 2}}
    sid = connect(client, "ws", ws_server.url + "/drop", options=opts).get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "closed")
    assert types(d).count("open") == 3 and types(d).count("reconnecting") == 2                # 1 + 2 urinish, keyin to'xtadi
    assert any("tugadi" in e.get("message", "") for e in d["events"] if e["type"] == "error")
    assert ws_server.connections == 3


def test_ws_no_reconnect_when_disabled_or_user_closes(client, ws_server):
    sid = connect(client, "ws", ws_server.url + "/drop").get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "closed")
    assert types(d).count("open") == 1 and "reconnecting" not in types(d)
    sid = connect(client, "ws", ws_server.url + "/echo", options={"reconnect": {"enabled": True, "delay_ms": 20, "max_attempts": 5, "always": True}}).get_json()["id"]
    wait(client, sid, lambda d: d["status"] == "open")
    client.post(f"/api/protocols/{sid}/close")
    d = wait(client, sid, lambda d: d["status"] == "closed")
    assert "reconnecting" not in types(d)                                                       # foydalanuvchi yopsa qayta ulanmaydi


def test_ws_errors_connection_refused_bad_scheme_closed_send(client, ws_server):
    sid = connect(client, "ws", "ws://127.0.0.1:1/x").get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "closed")
    assert any(e["type"] == "error" for e in d["events"])
    r = connect(client, "ws", "ftp://x/y")
    assert r.status_code == 400 and "ws://" in r.get_json()["error"]
    assert connect(client, "ws", "http://127.0.0.1:1/x").status_code == 200                      # http:// -> ws:// ga o'tkaziladi
    s2 = connect(client, "ws", ws_server.url + "/echo").get_json()["id"]
    wait(client, s2, lambda d: d["status"] == "open")
    client.post(f"/api/protocols/{s2}/close")
    wait(client, s2, lambda d: d["status"] == "closed")
    r = send(client, s2, "late")
    assert r.status_code == 400 and "ochiq emas" in r.get_json()["error"]
    assert send(client, "nope", "x").status_code == 404
    s3 = connect(client, "ws", ws_server.url + "/echo").get_json()["id"]
    wait(client, s3, lambda d: d["status"] == "open")
    assert send(client, s3, "{bad", "json").status_code == 400 and send(client, s3, "zz", "binary", encoding="base64").status_code == 400
    client.post(f"/api/protocols/{s3}/close")


def test_ws_stream_endpoint_resumes_from_sequence_and_ends_after_close(client, ws_server):
    sid = connect(client, "ws", ws_server.url + "/greet").get_json()["id"]
    wait(client, sid, lambda d: len(msgs(d, "in")) == 1)
    client.post(f"/api/protocols/{sid}/close")
    wait(client, sid, lambda d: d["status"] == "closed")
    r = client.get(f"/api/protocols/{sid}/stream?from=2")
    body = r.get_data(as_text=True)
    evs = [json.loads(l[6:]) for l in body.splitlines() if l.startswith("data: ")]
    assert evs and evs[0]["seq"] == 2 and evs[-1]["type"] == "closed"
    all_events = client.get(f"/api/protocols/{sid}/events").get_json()["events"]
    assert [e["seq"] for e in all_events] == list(range(len(all_events)))


def test_ws_export_json_and_txt(client, ws_server):
    sid = connect(client, "ws", ws_server.url + "/echo").get_json()["id"]
    wait(client, sid, lambda d: d["status"] == "open")
    send(client, sid, "exported")
    wait(client, sid, lambda d: len(msgs(d, "in")) == 1)
    client.post(f"/api/protocols/{sid}/close")
    wait(client, sid, lambda d: d["status"] == "closed")
    j = client.get(f"/api/protocols/{sid}/export")
    assert j.headers["Content-Disposition"].endswith(f'ws-{sid}.json"') and any(e.get("data") == "exported" for e in json.loads(j.data)["events"])
    t = client.get(f"/api/protocols/{sid}/export?format=txt")
    assert b"-> message exported" in t.data and b"<- message exported" in t.data


# ── SSE ──
def test_sse_parses_events_comments_multiline_retry_ids(client, sse_server):
    sid = connect(client, "sse", sse_server + "/sse/basic").get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "closed")
    ev = [e for e in d["events"] if e["type"] == "event"]
    assert [(e["event"], e["id"], e["data"]) for e in ev] == [("tick", "1", "one"), ("message", "2", "line a\nline b"), ("message", "2", '{"k": 1}')]
    assert [e["data"] for e in d["events"] if e["type"] == "comment"] == ["hello comment"]
    opened = next(e for e in d["events"] if e["type"] == "open")
    assert opened["status"] == 200 and "text/event-stream" in opened["content_type"] and opened["warning"] is None
    assert d["counts"]["in"] == 3 and ev[1]["size"] == len("line a\nline b")


def test_sse_crlf_line_endings(client, sse_server):
    sid = connect(client, "sse", sse_server + "/sse/crlf").get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "closed")
    ev = [e for e in d["events"] if e["type"] == "event"]
    assert [(e["event"], e["data"]) for e in ev] == [("win", "x"), ("message", "y")]


def test_sse_reconnects_with_last_event_id_and_server_retry(client, sse_server):
    import requests
    sid = connect(client, "sse", sse_server + "/sse/resume", options={"reconnect": {"enabled": True, "delay_ms": 1000, "max_attempts": 2}}).get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "closed")                                   # 2 ta qayta ulanishdan keyin to'xtaydi (urinishlar tugadi)
    data = [e["data"] for e in d["events"] if e["type"] == "event"]
    assert data == ["msg 1", "msg 2", "msg 3", "msg 4", "msg 5", "msg 6"]                      # davom ettirildi, takror yo'q
    assert any("tugadi" in e.get("message", "") for e in d["events"] if e["type"] == "error")
    assert requests.get(sse_server + "/sse/seen").json() == ["", "2", "4"]
    rec = [e for e in d["events"] if e["type"] == "reconnecting"]
    assert rec[0]["delay"] == pytest.approx(0.05) and rec[0]["last_event_id"] == "2"           # `retry: 50` server ko'rsatmasi hisobga olindi


def test_sse_initial_last_event_id_headers_auth_and_post_body(client, sse_server):
    sid = connect(client, "sse", sse_server + "/sse/headers", headers={"X-Custom": "{{v}}"}, env_vars={"v": "val"}, options={"last_event_id": "42"}).get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "closed")
    h = {k.lower(): v for k, v in json.loads(next(e for e in d["events"] if e["type"] == "event")["data"]).items()}
    assert h["x-custom"] == "val" and h["last-event-id"] == "42" and h["accept"] == "text/event-stream"
    sid = connect(client, "sse", sse_server + "/sse/secure", authorization="Bearer s3cret").get_json()["id"]
    assert [e["data"] for e in wait(client, sid, lambda d: d["status"] == "closed")["events"] if e["type"] == "event"] == ["secret ok"]
    sid = connect(client, "sse", sse_server + "/sse/post", method="POST", body='{"q":"{{v}}"}', body_type="json", env_vars={"v": "z"}).get_json()["id"]
    assert [e["data"] for e in wait(client, sid, lambda d: d["status"] == "closed")["events"] if e["type"] == "event"] == ['{"q":"z"}']


def test_sse_http_errors_content_type_warning_and_retry_on_5xx(client, sse_server):
    sid = connect(client, "sse", sse_server + "/sse/status/404").get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "closed")
    err = next(e for e in d["events"] if e["type"] == "error")
    assert "HTTP 404" in err["message"] and "boom body" in err["message"] and "reconnecting" not in types(d)
    sid = connect(client, "sse", sse_server + "/sse/secure").get_json()["id"]
    assert any("401" in e["message"] for e in wait(client, sid, lambda d: d["status"] == "closed")["events"] if e["type"] == "error")
    sid = connect(client, "sse", sse_server + "/sse/plain").get_json()["id"]
    d = wait(client, sid, lambda d: d["status"] == "closed")
    assert next(e for e in d["events"] if e["type"] == "open")["warning"].startswith("Content-Type text/event-stream emas")
    sid = connect(client, "sse", sse_server + "/sse/flaky", options={"reconnect": {"enabled": True, "delay_ms": 20, "max_attempts": 3}}).get_json()["id"]
    d = wait(client, sid, lambda d: any(e["type"] == "event" for e in d["events"]))
    client.post(f"/api/protocols/{sid}/close")
    d = wait(client, sid, lambda d: d["status"] == "closed")
    assert d["events"][[e["type"] for e in d["events"]].index("event")]["data"] == "recovered" and types(d).count("reconnecting") >= 1       # 503 dan keyin qayta urinildi
    sid = connect(client, "sse", sse_server + "/sse/status/204").get_json()["id"]
    assert "204" in next(e for e in wait(client, sid, lambda d: d["status"] == "closed")["events"] if e["type"] == "error")["message"]


def test_sse_stop_during_stream_and_bad_urls(client, sse_server):
    sid = connect(client, "sse", sse_server + "/sse/forever").get_json()["id"]
    wait(client, sid, lambda d: len([e for e in d["events"] if e["type"] == "event"]) >= 3)
    client.post(f"/api/protocols/{sid}/close")
    d = wait(client, sid, lambda d: d["status"] == "closed")
    assert types(d)[-1] == "closed" and "reconnecting" not in types(d)
    n = len([e for e in d["events"] if e["type"] == "event"])
    time.sleep(0.2)
    assert len([e for e in client.get(f"/api/protocols/{sid}/events").get_json()["events"] if e["type"] == "event"]) == n       # to'xtagach yangi hodisa yo'q
    assert connect(client, "sse", "ws://x/y").status_code == 400
    assert connect(client, "sse", "x/y").status_code == 400
    assert connect(client, "xx", "http://x").status_code == 400
    assert connect(client, "sse", "").status_code == 400
    assert send(client, sid, "x").status_code == 400
    sid = connect(client, "sse", "http://127.0.0.1:1/x").get_json()["id"]
    assert any("Ulanib bo'lmadi" in e["message"] for e in wait(client, sid, lambda d: d["status"] == "closed")["events"] if e["type"] == "error")


# ── pre-request skriptlari ──
def test_prerequest_script_changes_header_before_connect(client, ws_server):
    from apirunner.core import scripting
    if not scripting.available():
        pytest.skip("quickjs-ng yo'q")
    body = {"kind": "ws", "spec": {"url": ws_server.url + "/headers", "method": "GET", "headers": [], "params": [], "env_vars": {}}, "options": {},
            "scripts": {"prerequest": [{"source": "pm.request.headers.add({key: 'X-From-Script', value: 'yes'}); console.log('pre ran')", "kind": "prerequest", "scope": "request", "name": "R", "id": "r"}], "test": []}}
    r = client.post("/api/protocols/connect", json=body).get_json()
    assert r["scripts"]["console"][0]["text"] == "pre ran"
    d = wait(client, r["id"], lambda d: len(msgs(d, "in")) == 1)
    assert {k.lower(): v for k, v in json.loads(msgs(d, "in")[0]["data"])["headers"].items()}["x-from-script"] == "yes"
    client.post(f"/api/protocols/{r['id']}/close")
