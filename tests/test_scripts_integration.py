"""Skriptlar engine va API bilan: /run_one, /run (batch, concurrency=10), saqlash qoidalari, limitlar, sendRequest sozlamalari."""
import json

import pytest

from apirunner.core import scripting
from apirunner.core.scripted import scripts_chain

pytestmark = pytest.mark.skipif(not scripting.available(), reason="quickjs-ng o'rnatilmagan")


def S(src, kind="test", scope="request", name="Req", sid="r1"):
    return {"source": src, "kind": kind, "scope": scope, "name": name, "id": sid}


def run_one(client, echo, path="/echo", pre=(), test=(), **cfg):
    d = client.post("/run_one", json={"url": echo + path, "method": "GET", "scripts": {"prerequest": list(pre), "test": list(test)}, **cfg}).get_json()
    return d


def world(client, echo):
    """Collection (o'zgaruvchi) + faol muhit + globals."""
    cid = client.post("/api/collections", json={"name": "C"}).get_json()["id"]
    col = client.get(f"/api/collections/{cid}").get_json()
    col["variable"] = [{"key": "base", "value": echo}]
    col["item"] = [{"id": "r1", "name": "Req", "request": {"method": "GET", "header": [], "url": {"raw": "{{base}}/echo"}}, "response": []}]
    client.put(f"/api/collections/{cid}", json=col)
    eid = client.post("/api/environments", json={"name": "E"}).get_json()["id"]
    env = client.get(f"/api/environments/{eid}").get_json()
    env["values"] = [{"key": "tok", "value": "T0", "enabled": True, "type": "default"}, {"key": "sec", "value": "S", "enabled": True, "type": "secret"}]
    client.put(f"/api/environments/{eid}", json=env)
    client.put("/api/workspace/meta", json={"active_environment_id": eid})
    client.put("/api/globals", json={"values": [{"key": "g0", "value": "G0", "enabled": True, "type": "default"}]})
    return cid, eid


def env_vals(client, eid):
    return {v["key"]: v for v in client.get(f"/api/environments/{eid}").get_json()["values"]}


# ── /run_one ──
def test_tests_tab_data_and_script_errors_do_not_stop_request(client, echo):
    d = run_one(client, echo, test=[S("pm.test('ok', () => pm.response.to.have.status(200)); pm.test('bad', () => pm.expect(1).to.equal(2)); console.log('hi'); undefinedFn()")])
    assert d["status"] == 200
    sc = d["scripts"]
    assert [(t["name"], t["passed"]) for t in sc["tests"]] == [("ok", True), ("bad", False)]
    assert sc["errors"][0]["name"] == "ReferenceError" and sc["errors"][0]["line"] == 1 and sc["errors"][0]["origin"]["scope"] == "request"
    assert [l["text"] for l in sc["console"]] == ["hi"] and sc["available"] is True and "response" not in sc


def test_scripts_run_in_given_order_with_origin_and_share_state(client, echo):
    d = run_one(client, echo, pre=[S("console.log('c-pre'); pm.variables.set('x', 'from-col')", "prerequest", "collection", "Col", "c"),
                                   S("console.log('f-pre', pm.variables.get('x')); pm.variables.set('x', 'from-folder')", "prerequest", "folder", "Fold", "f"),
                                   S("console.log('r-pre', pm.variables.get('x'))", "prerequest", "request", "Req", "r")],
                test=[S("console.log('c-test')", "test", "collection", "Col", "c"), S("console.log('r-test')", "test", "request", "Req", "r")])
    logs = d["scripts"]["console"]
    assert [l["text"] for l in logs] == ["c-pre", "f-pre from-col", "r-pre from-folder", "c-test", "r-test"]
    assert [l["origin"]["scope"] for l in logs] == ["collection", "folder", "request", "collection", "request"]
    assert [l["origin"]["kind"] for l in logs] == ["prerequest"] * 3 + ["test"] * 2


def test_scripts_chain_from_collection_tree_matches_postman_order(client, echo):
    cid, _ = world(client, echo)
    col = client.get(f"/api/collections/{cid}").get_json()
    ev = lambda k, code: [{"listen": k, "script": {"type": "text/javascript", "exec": code.split("\n")}}]  # noqa: E731
    col["event"] = ev("prerequest", "// c") + ev("test", "// ct")
    col["item"] = [{"id": "f1", "name": "F", "event": ev("prerequest", "// f"), "item": [
        {"id": "f2", "name": "G", "event": ev("test", "// gt"), "item": [{"id": "r9", "name": "Deep", "event": ev("prerequest", "// r") + ev("test", "// rt"), "request": {"method": "GET", "header": [], "url": {"raw": "x"}}, "response": []}]}]}]
    ch = scripts_chain(col, "r9")
    assert [(s.scope, s.name) for s in ch["prerequest"]] == [("collection", "C"), ("folder", "F"), ("request", "Deep")]
    assert [(s.scope, s.name) for s in ch["test"]] == [("collection", "C"), ("folder", "G"), ("request", "Deep")]


def test_request_mutation_by_pre_request_is_sent(client, echo):
    d = run_one(client, echo, path="/echo", params=[{"name": "keep", "value": "1"}], headers=[{"name": "X-Old", "value": "1"}],
                pre=[S("""pm.request.headers.add({key: 'X-New', value: pm.variables.replaceIn('{{$guid}}').length + ''}); pm.request.headers.remove('X-Old');
                          pm.request.url.query.add({key: 'added', value: 'a b'}); pm.request.method = 'POST'; pm.request.body.update('{"k":1}')""", "prerequest")],
                method="GET", body_type="json")
    r = d["response"]
    assert r["method"] == "POST" and r["json"] == {"k": 1} and r["headers"]["X-New"] == "36" and "X-Old" not in r["headers"]
    assert r["args"] == {"keep": ["1"], "added": ["a b"]}


def test_unmodified_request_is_not_touched(client, echo, tmp_path):
    f = tmp_path / "u.txt"
    f.write_text("hello")
    up = client.post("/upload_temp", data={"file": (f.open("rb"), "u.txt")}).get_json()
    d = run_one(client, echo, method="POST", params=[{"name": "file", "value": f"{up['path']}::u.txt", "type": "file"}], pre=[S("console.log('noop')", "prerequest")])
    assert d["status"] == 200 and d["response"]["files"]["file"]["content"] == "hello"


def test_variables_set_by_pre_request_are_used_in_url_and_persisted_in_workspace(client, echo):
    cid, eid = world(client, echo)
    d = client.post("/run_one", json={"url": "{{base}}/echo/{{sub}}", "ref": f"{cid}:r1", "env_vars": {"base": echo},
                                      "scripts": {"prerequest": [S("pm.environment.set('sub', 'x1'); pm.variables.set('base', pm.collectionVariables.get('base'))", "prerequest")], "test": []}}).get_json()
    assert d["status"] == 404 and d["url"].endswith("/echo/x1")                      # echo'da /echo/x1 yo'q, lekin {{sub}} yechildi
    assert env_vals(client, eid)["sub"]["current"] == "x1" and env_vals(client, eid)["sub"]["value"] == ""                               # skript yozgan o'zgaruvchi muhitga saqlandi


def test_persistence_rules_env_globals_collection_but_not_data_local(client, echo):
    cid, eid = world(client, echo)
    d = run_one(client, echo, ref=f"{cid}:r1", row={"rowvar": "r"}, test=[S("""
        pm.environment.set('tok', 'T1'); pm.environment.set('new_env', 42); pm.environment.unset('sec');
        pm.globals.set('g1', {a: 1}); pm.globals.unset('g0'); pm.collectionVariables.set('cv', 'C1');
        pm.variables.set('local_only', 'L'); pm.iterationData.set && 0;""")])
    assert d["scripts"]["changed"] == ["environment", "globals", "collection"]
    ev = env_vals(client, eid)
    assert ev["tok"]["current"] == "T1" and ev["new_env"]["current"] == "42" and "sec" not in ev and ev["new_env"]["enabled"] is True
    g = {v["key"]: v["current"] for v in client.get("/api/globals").get_json()["values"]}
    assert g == {"g1": '{"a": 1}'}                                                     # g0 o'chirildi, obyekt JSON sifatida
    col = client.get(f"/api/collections/{cid}").get_json()
    assert {v["key"]: v["value"] for v in col["variable"]} == {"base": echo, "cv": "C1"}
    assert "local_only" not in json.dumps(client.get("/api/workspace").get_json()) and "rowvar" not in json.dumps(client.get("/api/workspace").get_json())


def test_unchanged_scripts_do_not_write_to_workspace(client, echo):
    cid, eid = world(client, echo)
    rev = lambda: client.get(f"/api/environments/{eid}").get_json()  # noqa: E731
    r0 = rev()
    run_one(client, echo, ref=f"{cid}:r1", test=[S("pm.environment.set('tok', pm.environment.get('tok')); pm.test('t', () => {})")])
    assert rev() == r0


def test_no_active_environment_changes_are_run_local(client, echo):
    d = run_one(client, echo, test=[S("pm.environment.set('a', 1); pm.test('visible in run', () => pm.expect(pm.environment.get('a')).to.equal(1))")])
    assert d["scripts"]["changed"] == [] and d["scripts"]["tests"][0]["passed"]
    assert any("Faol muhit" in l["text"] for l in d["scripts"]["console"])
    assert client.get("/api/workspace").get_json()["environments"] == []


def test_skip_request_does_not_call_the_server_and_set_next_request_is_reported(client, echo):
    d = client.post("/run_one", json={"url": "http://127.0.0.1:9/never", "scripts": {"prerequest": [S("pm.execution.skipRequest(); pm.execution.setNextRequest('After')", "prerequest")], "test": [S("pm.test('not run', () => {})")]}}).get_json()
    assert d["status"] == "SKIPPED" and d["scripts"]["skipped"] and d["scripts"]["tests"] == [] and d["scripts"]["next_request"] == "After" and d["scripts"]["next_set"]


def test_network_error_skips_test_scripts_but_reports_error(client):
    d = client.post("/run_one", json={"url": "http://127.0.0.1:9/x", "scripts": {"prerequest": [], "test": [S("pm.test('should not run', () => {})")]}, "timeout": 2}).get_json()
    assert d["status"] == "ERR" and d["scripts"]["tests"] == []


def test_scripts_unavailable_still_sends_request_and_explains(client, echo, monkeypatch):
    from apirunner.core.scripting import sandbox
    monkeypatch.setattr(sandbox, "quickjs", None)
    d = run_one(client, echo, test=[S("pm.test('x', () => {})")])
    assert d["status"] == 200 and d["scripts"]["available"] is False and "quickjs-ng" in d["scripts"]["message"] and "pip install" in d["scripts"]["install"]
    st = client.get("/api/scripts/status").get_json()
    assert st["available"] is False and "pip install quickjs-ng" in st["install"]


def test_requests_without_scripts_are_unchanged_and_carry_no_scripts_key(client, echo):
    d = client.post("/run_one", json={"url": echo + "/echo"}).get_json()
    assert d["status"] == 200 and d["scripts"] is None


# ── limitlar (Sozlamalar → Skriptlar) ──
def test_limits_api_clamps_and_applies(client, echo):
    st = client.get("/api/scripts/status").get_json()
    assert st["available"] and st["version"] and st["limits"] == st["defaults"] == {"timeout_ms": 10000, "memory_mb": 64, "max_requests": 10}
    r = client.put("/api/workspace/meta", json={"script_limits": {"timeout_ms": 1, "memory_mb": 24, "max_requests": 2}}).get_json()
    assert r["meta"]["script_limits"] == {"timeout_ms": 100, "memory_mb": 24, "max_requests": 2}
    d = run_one(client, echo, test=[S("while(true){}")])
    assert d["status"] == 200 and d["scripts"]["errors"][0]["name"] == "TimeoutError" and "100 ms" in d["scripts"]["errors"][0]["message"]
    client.put("/api/workspace/meta", json={"script_limits": {"timeout_ms": 8000, "memory_mb": 24, "max_requests": 2}})   # xotira chegarasi vaqt chegarasidan oldin urilsin (yuklama ostida 100 ms yetmaydi)
    d = run_one(client, echo, test=[S("const a=[]; while(true) a.push(new Array(10000).fill(1))")])
    assert d["scripts"]["errors"][0]["name"] == "MemoryError" and "24 MB" in d["scripts"]["errors"][0]["message"]
    client.put("/api/workspace/meta", json={"script_limits": {"timeout_ms": 5000, "memory_mb": 64, "max_requests": 2}})
    d = run_one(client, echo, test=[S("for (let i = 0; i < 4; i++) pm.sendRequest('%s/echo', (e) => console.log(i, e ? 'limit' : 'ok'))" % echo)])
    assert sorted(l["text"] for l in d["scripts"]["console"]) == ["0 ok", "1 ok", "2 limit", "3 limit"]


# ── pm.sendRequest: asosiy engine orqali ──
def test_send_request_uses_engine_cookie_jar_settings_and_variables(client, echo):
    cid, eid = world(client, echo)
    d = run_one(client, echo, path="/cookie/echo", ref=f"{cid}:r1",
                pre=[S("await pm.sendRequest(pm.variables.replaceIn('{{base}}/cookie/set?name=sid&value=jar1'));", "prerequest")],
                test=[S("""const r = await pm.sendRequest({url: pm.collectionVariables.get('base') + '/cookie/echo', method: 'GET'}); pm.test('same cookie jar', () => pm.expect(r.json()).to.eql({sid: 'jar1'}));
                           const rd = await pm.sendRequest(pm.collectionVariables.get('base') + '/redirect'); pm.test('redirects followed by default', () => pm.expect(rd.code).to.equal(200))""")])
    assert d["response"] == {"sid": "jar1"} and all(t["passed"] for t in d["scripts"]["tests"]), d["scripts"]
    client.put("/api/workspace/meta", json={"settings": {"follow_redirects": False}})
    d = run_one(client, echo, ref=f"{cid}:r1", test=[S("const rd = await pm.sendRequest(pm.collectionVariables.get('base') + '/redirect'); pm.test('global setting applies', () => pm.expect(rd.code).to.equal(302))")])
    assert d["scripts"]["tests"][0]["passed"], d["scripts"]


def test_send_request_body_modes_auth_and_errors(client, echo):
    d = run_one(client, echo, test=[S("""
      const u = '%s/echo';
      const a = await pm.sendRequest({url: u, method: 'POST', header: {'X-A': '1'}, body: {mode: 'urlencoded', urlencoded: [{key: 'a', value: 'b c'}]}, auth: {type: 'bearer', bearer: [{key: 'token', value: 'TKN'}]}});
      const b = await pm.sendRequest({url: u, method: 'POST', body: {mode: 'graphql', graphql: {query: '{ q }', variables: '{"x":1}'}}});
      const c = await pm.sendRequest({url: u, method: 'POST', body: {mode: 'formdata', formdata: [{key: 'f', value: 'v', type: 'text'}]}});
      pm.test('shapes', () => { pm.expect(a.json().form).to.eql({a: ['b c']}); pm.expect(a.json().headers.Authorization).to.equal('Bearer TKN'); pm.expect(a.json().headers['X-A']).to.equal('1');
        pm.expect(b.json().json).to.eql({query: '{ q }', variables: {x: 1}}); pm.expect(c.json().form).to.eql({f: ['v']}) });
      let err; try { await pm.sendRequest('http://127.0.0.1:9/none') } catch (e) { err = e.message } pm.test('rejects on network error', () => pm.expect(err).to.be.a('string').and.not.empty);
    """ % echo)])
    assert all(t["passed"] for t in d["scripts"]["tests"]), d["scripts"]


# ── batch (/run), concurrency=10 ──
def stream_results(client, cfg):
    jid = client.post("/run", json=cfg).get_json()["job_id"]
    raw = client.get(f"/stream/{jid}").get_data(as_text=True)
    out = []
    for line in raw.splitlines():
        if line.startswith("data: ") and '"index"' in line:
            out.append(json.loads(line[6:]))
    return sorted(out, key=lambda r: r["index"])


def test_batch_runs_scripts_per_row_with_iteration_data(client, echo):
    rows = [{"id": str(i), "n": i} for i in range(1, 7)]
    res = stream_results(client, {"url": echo + "/echo?id={{id}}", "rows": rows, "concurrency": 1, "scripts": {"prerequest": [S("pm.variables.set('seen', pm.iterationData.get('id') + '!')", "prerequest")],
                                  "test": [S("pm.test('row ' + pm.info.iteration, () => { pm.expect(pm.response.json().args.id[0]).to.equal(pm.iterationData.get('id')); pm.expect(pm.variables.get('seen')).to.equal(pm.iterationData.get('id') + '!') }); console.log(pm.info.iteration + '/' + pm.info.iterationCount)")]}})
    assert len(res) == 6
    for i, r in enumerate(res):
        assert r["status"] == 200 and r["scripts"]["tests"][0]["passed"], r["scripts"]
        assert r["scripts"]["console"][0]["text"] == "%d/6" % i


def test_batch_with_scripts_at_concurrency_10_is_thread_safe_and_persists_all_keys(client, echo):
    cid, eid = world(client, echo)
    rows = [{"id": str(i)} for i in range(40)]
    res = stream_results(client, {"url": echo + "/echo?id={{id}}", "ref": f"{cid}:r1", "rows": rows, "concurrency": 10, "scripts": {"prerequest": [S("await new Promise(r => setTimeout(r, 5)); pm.variables.set('mine', pm.iterationData.get('id'))", "prerequest")],
        "test": [S("""pm.test('isolated', () => { pm.expect(pm.variables.get('mine')).to.equal(pm.iterationData.get('id')); pm.expect(pm.response.json().args.id[0]).to.equal(pm.iterationData.get('id')) });
                      const r = await pm.sendRequest(pm.variables.replaceIn('%s/echo?via={{id}}')); pm.test('sendRequest', () => pm.expect(r.json().args.via[0]).to.equal(pm.iterationData.get('id')));
                      pm.environment.set('row_' + pm.iterationData.get('id'), 'x'); require('lodash').sum([1])""" % echo)]}})
    assert len(res) == 40
    bad = [r for r in res if r["status"] != 200 or r["scripts"]["errors"] or not all(t["passed"] for t in r["scripts"]["tests"])]
    assert not bad, bad[:2]
    keys = {k for k in env_vals(client, eid) if k.startswith("row_")}
    assert keys == {"row_%d" % i for i in range(40)}                                  # har bir iteratsiya o'z kalitini yozdi, hech biri yo'qolmadi (qulf)
    assert {"tok", "sec"} <= set(env_vals(client, eid))                                # mavjud o'zgaruvchilar buzilmadi


def test_send_request_goes_through_the_configured_proxy_and_cookie_jar(client, echo):
    import http.server
    import threading

    import httpx

    class Proxy(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            r = httpx.get(self.path, trust_env=False)
            self.send_response(r.status_code)
            self.send_header("X-Proxied", "yes")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(r.content)))
            self.end_headers()
            self.wfile.write(r.content)

        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        client.put("/api/workspace/meta", json={"settings": {"proxy": f"http://127.0.0.1:{srv.server_port}"}})
        d = run_one(client, echo, test=[S("const r = await pm.sendRequest('%s/echo'); pm.test('via proxy', () => pm.expect(r.headers.get('X-Proxied')).to.equal('yes'));" % echo)])
        assert d["scripts"]["tests"][0]["passed"], d["scripts"]
    finally:
        srv.shutdown()


def test_sandbox_bookkeeping_is_not_bounded_by_the_script_time_budget():
    """Regressiya (beqaror test sababi): yuklama ostida tayyorlash/`set_event` 100 ms byudjetdan o'tib ketsa ScriptTimeout 500 xatoga aylanardi."""
    import time
    from apirunner.core.scripting.sandbox import Limits, ScriptSession, ScriptSource
    scopes = {k: {} for k in ("globals", "collection", "environment", "data", "local")}
    s = ScriptSession(scopes, {}, {}, Limits(timeout_ms=100), host=None)
    time.sleep(0.25)                                              # byudjet tugadi
    s.set_event("test")                                           # ichki chaqiruvlar baribir ishlaydi
    s.set_response({"code": 200, "headers": [], "body": ""})
    s.run(ScriptSource("pm.test('late', () => {})", "test"))     # foydalanuvchi skripti esa byudjet tugagani uchun TimeoutError oladi
    rep = s.collect()
    assert rep.errors and rep.errors[0]["name"] == "TimeoutError"
