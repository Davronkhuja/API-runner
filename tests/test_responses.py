"""Saqlangan javoblar (SQLite): 5 MB chegara, binary, run_one integratsiyasi, endpointlar, qayta ishga tushganda saqlanishi."""
import io

from apirunner.storage import db as dbm


def run(client, url, **kw):
    return client.post("/run_one", json={"url": url, "store_response": True, **kw}).get_json()


def test_text_response_is_stored_and_readable_by_id(client, echo):
    d = run(client, echo + "/status/400")
    assert d["status"] == 400 and isinstance(d["response_id"], int)
    r = client.get(f"/api/responses/{d['response_id']}").get_json()
    assert r["status"] == "400" and '"code":400' in r["body"] and not r["truncated"] and not r["binary"] and r["size"] == d["size"]


def test_not_stored_unless_requested_and_unknown_id_is_404(client, echo):
    d = client.post("/run_one", json={"url": echo + "/echo"}).get_json()
    assert "response_id" not in d
    assert client.get("/api/responses/999999").status_code == 404


def test_over_5mb_keeps_first_5mb_and_flags_truncation(client, echo):
    d = run(client, echo + "/bigtext?mb=6")
    r = client.get(f"/api/responses/{d['response_id']}").get_json()
    assert d["size"] > 5 * 1024 * 1024 and d["stored_truncated"] is True
    assert r["truncated"] and r["stored"] == dbm.MAX_RESPONSE and len(r["body"]) == dbm.MAX_RESPONSE and r["size"] == d["size"]


def test_binary_response_is_stored_as_bytes_and_served_raw(client, echo):
    d = run(client, echo + "/png")
    assert d["binary"] is True and d["content_type"].startswith("image/png") and "binary" in d["response"]
    r = client.get(f"/api/responses/{d['response_id']}").get_json()
    assert r["binary"] and r["body"] is None
    raw = client.get(f"/api/responses/{d['response_id']}/raw")
    assert raw.status_code == 200 and raw.data.startswith(b"\x89PNG") and raw.headers["Content-Type"].startswith("image/png")
    assert raw.headers["Content-Security-Policy"] == "sandbox"


def test_empty_204_response_is_stored(client, echo):
    d = run(client, echo + "/nocontent")
    assert d["status"] == 204 and client.get(f"/api/responses/{d['response_id']}").get_json()["size"] == 0


def test_stored_response_survives_server_restart(make_client, echo, isolated):
    c = make_client()
    rid = run(c, echo + "/status/418")["response_id"]
    c2 = make_client()                                                       # xuddi shu workspace, yangi app
    assert '"code":418' in c2.get(f"/api/responses/{rid}").get_json()["body"]


def test_prune_keeps_only_recent_rows(tmp_path):
    s = dbm.StateDB(str(tmp_path / "s.db"))
    ids = [s.save_response(200, {}, "text/plain", 1, b"x", False) for _ in range(dbm.RESPONSE_KEEP + 5)]
    assert s.get_response(ids[0]) is None and s.get_response(ids[-1]) is not None
