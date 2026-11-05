"""Run engine (server tomonida): oqim, SQLite, SSE, eksport, solishtirish, setNextRequest, to'xtash, o'zgaruvchilarni tiklash."""
import json
import time
import xml.etree.ElementTree as ET


def item(i, name, url, method="GET", scripts=None):
    return {"id": i, "name": name, "method": method, "ref": f"C:{i}", "spec": {"method": method, "url": url, "params": [], "headers": []}, "scripts": scripts}


def start(client, items, **kw):
    plan = {"scope": "C", "scope_name": "Col", "items": items, "settings": kw.pop("settings", {}), **kw}
    r = client.post("/api/runs", json=plan)
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def wait(client, rid, secs=20):
    end = time.time() + secs
    while time.time() < end:
        r = client.get(f"/api/runs/{rid}").get_json()
        if r["status"] != "running":
            return r
        time.sleep(0.05)
    raise AssertionError("run tugamadi")


def test_run_executes_items_iterations_rows_and_stores_results(client, echo):
    d = start(client, [item("a", "A", echo + "/echo?x=1"), item("b", "B", echo + "/status/404")], iterations=2, rows=[{"k": "1"}, {"k": "2"}])
    run = wait(client, d["id"])
    assert run["number"] == 1 and run["status"] == "done" and len(run["results"]) == 4
    s = run["summary"]
    assert s["completed"] == 4 and s["successful"] == 2 and s["failed"] == 2
    assert [r["status"] for r in run["results"]] == ["200", "404", "200", "404"] and run["results"][0]["iter"] == 1 and run["results"][2]["iter"] == 2
    d2 = start(client, [item("a", "A", echo + "/echo")])
    assert wait(client, d2["id"])["number"] == 2                                     # run raqami scope bo'yicha oshadi


def test_sse_stream_emits_start_steps_and_done(client, echo):
    d = start(client, [item("a", "A", echo + "/echo"), item("b", "B", echo + "/echo")])
    body = client.get(f"/api/runs/{d['id']}/stream").get_data(as_text=True)
    kinds = [b.split("\n")[0] for b in body.split("\n\n") if b.startswith("event:")]
    assert kinds == ["event: start", "event: step", "event: step", "event: done"]
    done = json.loads([b for b in body.split("\n\n") if b.startswith("event: done")][0].split("data: ", 1)[1])
    assert done["completed"] == 2 and done["status"] == "done"


def test_tests_column_and_set_next_request_and_skip(client, echo):
    S = lambda src, kind: {"source": src, "kind": kind, "scope": "request", "name": "x", "id": "x"}  # noqa: E731
    items = [item("a", "A", echo + "/echo", scripts={"prerequest": [], "test": [S("pm.test('ok', () => pm.response.to.have.status(200)); pm.test('bad', () => { throw new Error('x') }); pm.execution.setNextRequest('C')", "test")]}),
             item("b", "B", echo + "/echo"), item("c", "C", echo + "/echo")]
    run = wait(client, start(client, items)["id"])
    assert [r["name"] for r in run["results"]] == ["A", "C"]                         # B o'tkazib yuborildi
    assert run["summary"]["tests_passed"] == 1 and run["summary"]["tests_failed"] == 1
    assert [t["passed"] for t in run["results"][0]["tests"]] == [True, False]


def test_stop_on_error_and_stop_endpoint(client, echo):
    run = wait(client, start(client, [item("a", "A", echo + "/status/500"), item("b", "B", echo + "/echo")], settings={"stop_on_error": True})["id"])
    assert len(run["results"]) == 1
    d = start(client, [item("s", "S", echo + "/slow?s=0.3")], iterations=30)
    time.sleep(0.5)
    client.post(f"/api/runs/{d['id']}/stop")
    r = wait(client, d["id"])
    assert r["status"] == "stopped" and len(r["results"]) < 30


def test_parallel_runs_all_steps(client, echo):
    run = wait(client, start(client, [item("a", "A", echo + "/slow?s=0.2"), item("b", "B", echo + "/slow?s=0.2"), item("c", "C", echo + "/slow?s=0.2")], settings={"parallel": 3})["id"])
    assert len(run["results"]) == 3 and run["summary"]["max_time"] < 0.6 * 3


def test_responses_saved_and_exports_and_compare(client, echo):
    a = wait(client, start(client, [item("a", "A", echo + "/echo?v=1"), item("b", "B", echo + "/status/404")], settings={"save_responses": True})["id"])
    b = wait(client, start(client, [item("a", "A", echo + "/echo?v=1"), item("b", "B", echo + "/echo")], settings={"save_responses": False})["id"])
    full = client.get(f"/api/runs/{a['id']}/export?format=json").get_json()
    assert '"v"' in full["results"][0]["body"] and full["results"][0]["resp_headers"]
    assert client.get(f"/api/runs/results/{b['results'][0]['id']}").get_json()["body"] in (None, "")           # saqlanmadi
    x = ET.fromstring(client.get(f"/api/runs/{a['id']}/export?format=junit").get_data(as_text=True))
    assert x.tag == "testsuites" and x.find("testsuite").get("failures") == "1"
    h = client.get(f"/api/runs/{a['id']}/export?format=html").get_data(as_text=True)
    assert "run #1" in h and "404" in h
    cmp = client.get(f"/api/runs/{a['id']}/compare/{b['id']}").get_json()
    assert cmp["changed"] == 1 and cmp["rows"][1]["a"]["status"] == "404" and cmp["rows"][1]["b"]["status"] == "200"


def test_save_vars_off_restores_environment_after_run(client, echo):
    eid = client.post("/api/environments", json={"name": "E"}).get_json()["id"]
    e = client.get(f"/api/environments/{eid}").get_json()
    e["values"] = [{"key": "tok", "value": "A", "enabled": True, "type": "default"}]
    client.put(f"/api/environments/{eid}", json=e)
    client.put("/api/workspace/meta", json={"active_environment_id": eid})
    S = {"prerequest": [{"source": "pm.environment.set('tok', 'CHANGED')", "kind": "prerequest", "scope": "request", "name": "x", "id": "x"}], "test": []}
    wait(client, start(client, [item("a", "A", echo + "/echo", scripts=S)], settings={"save_vars": False})["id"])
    assert client.get(f"/api/environments/{eid}").get_json()["values"][0].get("current") in (None, "") and client.get(f"/api/environments/{eid}").get_json()["values"][0]["value"] == "A"
    wait(client, start(client, [item("a", "A", echo + "/echo", scripts=S)], settings={"save_vars": True})["id"])
    assert client.get(f"/api/environments/{eid}").get_json()["values"][0]["current"] == "CHANGED"


def test_last_results_and_last_run_for_scope(client, echo):
    wait(client, start(client, [item("a", "A", echo + "/echo"), item("b", "B", echo + "/status/500")])["id"])
    d = client.get("/api/last-results?refs=C:a,C:b,C:zz&scope=C").get_json()
    assert d["results"]["C:a"]["status"] == "200" and d["results"]["C:b"]["status"] == "500" and "C:zz" not in d["results"]
    assert [i["status"] for i in d["run"]["items"]] == ["200", "500"]
    client.post("/run_one", json={"url": echo + "/status/404", "ref": "C:zz"})
    assert client.get("/api/last-results?refs=C:zz").get_json()["results"]["C:zz"]["status"] == "404"


def test_run_requires_items_and_unknown_run_is_404(client):
    assert client.post("/api/runs", json={"scope": "C", "items": []}).status_code == 400
    assert client.get("/api/runs/999").status_code == 404 and client.get("/api/runs/999/stream").status_code == 404


def test_data_row_fills_variables_without_scripts(client, echo):
    d = start(client, [item("a", "A", echo + "/status/{{code}}")], iterations=2, rows=[{"code": "201"}, {"code": "404"}])
    r = wait(client, d["id"])
    assert [str(x["status"]) for x in r["results"]] == ["201", "404"]
