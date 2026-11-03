"""Skript sandbox (ADR 0007): pm.* API, async semantika, require, legacy global'lar, xavfsizlik va limitlar, thread-safety."""
import json
import threading
import time

import pytest

from apirunner.core import scripting
from apirunner.core.scripting.sandbox import Limits, ScriptSession, ScriptSource

pytestmark = pytest.mark.skipif(not scripting.available(), reason="quickjs-ng o'rnatilmagan")


class FakeHost:
    def __init__(self):
        self.sent = []
        self.cookies = {}

    def send(self, req):
        self.sent.append(req)
        if "fail" in req["url"]:
            return {"error": {"message": "ulanib bo'lmadi"}}
        return {"response": {"code": 200, "status": "OK", "headers": {"content-type": "application/json"}, "body": json.dumps({"echo": req["url"], "method": req["method"]}), "time": 3, "size": 20, "cookies": []}}

    def cookie(self, op):
        if op["op"] == "set":
            self.cookies[op["cookie"]["name"]] = op["cookie"]["value"]
            return {"value": None}
        if op["op"] == "get":
            return {"value": self.cookies.get(op["name"])}
        return {"value": list(self.cookies)}


REQ = {"method": "GET", "url": "{{base_url}}/echo?x=1", "headers": [{"key": "Accept", "value": "*/*"}], "body": "", "body_mode": "raw"}
RESP = {"code": 200, "status": "OK", "headers": {"content-type": "application/json", "x-id": "7"}, "body": '{"data":{"id":7,"name":"Ali"},"list":[1,2,3]}', "time": 12, "size": 44, "cookies": [{"name": "sid", "value": "abc"}], "jar": []}


def sess(limits=None, host=None, scopes=None, request=REQ, response=None, active_env=True):
    s = ScriptSession({"globals": {}, "collection": {"base_url": "http://h"}, "environment": {"tok": "T"}, "data": {"row": "r1"}, "local": {}, **(scopes or {})},
                      request, {"iteration": 2, "iterationCount": 5, "requestName": "Req", "requestId": "id1", "eventName": "prerequest"}, limits or Limits(timeout_ms=5000), host or FakeHost(), active_env)
    if response is not None:
        s.set_response(response)
    return s


def run(code, kind="test", response=RESP, **kw):
    s = sess(response=response, **kw)
    s.run(ScriptSource(code, kind, "request", "R", "r1"))
    return s.collect()


def names(r):
    return {t["name"]: t["passed"] for t in r.tests}


# ── pm.* ──
def test_variables_scopes_and_precedence():
    r = run("""
      pm.environment.set('e','E'); pm.globals.set('g','G'); pm.collectionVariables.set('c','C'); pm.variables.set('l','L');
      pm.test('get', () => { pm.expect(pm.environment.get('tok')).to.equal('T'); pm.expect(pm.variables.get('base_url')).to.equal('http://h');
        pm.expect(pm.iterationData.get('row')).to.equal('r1'); pm.expect(pm.variables.get('row')).to.equal('r1') });
      pm.environment.set('base_url', 'http://env'); pm.test('precedence env>collection', () => pm.expect(pm.variables.get('base_url')).to.equal('http://env'));
      pm.variables.set('base_url', 'http://local'); pm.test('local wins', () => pm.expect(pm.variables.replaceIn('{{base_url}}/a')).to.equal('http://local/a'));
      pm.environment.unset('tok'); pm.test('unset/has', () => { pm.expect(pm.environment.has('tok')).to.be.false; pm.expect(pm.environment.toObject()).to.have.property('e') });
    """)
    assert all(names(r).values()), r.tests
    assert r.changed == {"environment": True, "globals": True, "collection": True}
    assert r.scopes["environment"]["e"] == "E" and "tok" not in r.scopes["environment"] and r.scopes["globals"]["g"] == "G" and r.scopes["collection"]["c"] == "C"
    assert r.scopes["local"]["l"] == "L" and "local" not in r.changed and "data" not in r.changed


def test_replace_in_dynamic_and_nested():
    r = run("""pm.variables.set('a','{{b}}'); pm.variables.set('b','deep');
      pm.test('nested', () => pm.expect(pm.variables.replaceIn('{{a}}')).to.equal('deep'));
      pm.test('guid', () => pm.expect(pm.variables.replaceIn('{{$guid}}')).to.match(/^[0-9a-f-]{36}$/));
      pm.test('ts', () => pm.expect(pm.variables.replaceIn('{{$timestamp}}')).to.match(/^\\d+$/));
      pm.test('unknown stays', () => pm.expect(pm.variables.replaceIn('{{nope}}')).to.equal('{{nope}}'))""")
    assert all(names(r).values()), r.tests


def test_response_api_and_chai_assertions():
    r = run("""
      pm.test('code/status', () => { pm.expect(pm.response.code).to.equal(200); pm.expect(pm.response.status).to.equal('OK') });
      pm.test('json/text', () => { pm.expect(pm.response.json().data.name).to.equal('Ali'); pm.expect(pm.response.text()).to.include('Ali') });
      pm.test('headers case-insens', () => { pm.expect(pm.response.headers.get('Content-Type')).to.equal('application/json'); pm.expect(pm.response.headers.has('X-ID')).to.be.true });
      pm.test('time/size', () => { pm.expect(pm.response.responseTime).to.equal(12); pm.expect(pm.response.responseSize).to.equal(44) });
      pm.test('to.have', () => { pm.response.to.have.status(200); pm.response.to.have.status('OK'); pm.response.to.have.header('x-id', '7');
        pm.response.to.have.jsonBody('data.id', 7); pm.response.to.be.ok; pm.response.to.be.success; pm.response.to.be.json; pm.response.to.not.be.error; pm.response.to.have.withBody });
      pm.test('negative to.have fails', () => pm.response.to.have.status(404));
      pm.test('cookies', () => pm.expect(pm.cookies.get('sid')).to.equal('abc'));
      pm.test('info', () => { pm.expect(pm.info.iteration).to.equal(2); pm.expect(pm.info.requestName).to.equal('Req'); pm.expect(pm.info.eventName).to.equal('prerequest') });
    """)
    t = names(r)
    assert t.pop("negative to.have fails") is False and all(t.values()), r.tests
    fail = next(x for x in r.tests if x["name"] == "negative to.have fails")
    assert "404" in fail["error"]["message"] and fail["error"]["line"]


def test_request_view_and_mutation_roundtrip():
    r = run("""
      pm.test('view', () => { pm.expect(pm.request.method).to.equal('GET'); pm.expect(pm.request.url.toString()).to.equal('{{base_url}}/echo?x=1');
        pm.expect(pm.request.headers.get('accept')).to.equal('*/*'); pm.expect(pm.request.url.query.get('x')).to.equal('1'); pm.expect(pm.request.url.getPath()).to.equal('/echo') });
      pm.request.method = 'post'; pm.request.headers.add({key:'X-A', value:'1'}); pm.request.headers.upsert({key:'accept', value:'text/plain'});
      pm.request.url.query.add({key:'y', value:'2'}); pm.request.body.update('{"a":1}');
    """, kind="prerequest", response=None)
    assert r.request["method"] == "POST" and r.request["url"] == "{{base_url}}/echo?x=1&y=2" and r.request["body"]["raw"] == '{"a":1}'
    assert {"key": "X-A", "value": "1"} in r.request["header"] and {"key": "Accept", "value": "text/plain"} in r.request["header"]
    assert all(names(r).values())


def test_unmodified_request_reports_no_change():
    assert run("pm.test('t', () => 1)", kind="prerequest", response=None).request is None


def test_test_async_done_and_skip_and_failures_have_line_numbers():
    r = run("""
      pm.test('async ok', async () => { await new Promise(r => setTimeout(r, 20)); pm.expect(1).to.equal(1) });
      pm.test('async fail', async () => { await Promise.resolve(); pm.expect(1).to.equal(2) });
      pm.test('done ok', (done) => { setTimeout(() => { pm.expect(true).to.be.true; done() }, 10) });
      pm.test('done err', (done) => { setTimeout(() => done(new Error('boom')), 10) });
      pm.test('done never', (done) => { });
      pm.test.skip('skipped', () => { throw new Error('no') });
      pm.test('sync throw', () => {
        throw new TypeError('bad');
      });
    """)
    t = {x["name"]: x for x in r.tests}
    assert t["async ok"]["passed"] and t["done ok"]["passed"]
    assert not t["async fail"]["passed"] and "expected 1 to equal 2" in t["async fail"]["error"]["message"]
    assert not t["done err"]["passed"] and t["done err"]["error"]["message"] == "boom"
    assert not t["done never"]["passed"] and "done()" in t["done never"]["error"]["message"]
    assert t["skipped"]["skipped"]
    assert t["sync throw"]["error"]["name"] == "TypeError" and t["sync throw"]["error"]["line"] == 9     # skript qatori (editor bilan bog'lanadi)


def test_console_levels_with_origin_and_formatting():
    r = run("console.log('a', 1, {b:2}); console.info('i'); console.warn('w'); console.error(new Error('e')); console.debug([1])")
    assert [(l["level"]) for l in r.logs] == ["log", "info", "warn", "error", "debug"]
    assert r.logs[0]["text"].startswith("a 1 {") and r.logs[0]["origin"]["scope"] == "request"
    assert "Error: e" in r.logs[3]["text"]


# ── asinxron semantika ──
def test_send_request_callback_promise_and_event_loop_waits_for_everything():
    h = FakeHost()
    r = run("""
      pm.sendRequest('http://x/a', (err, res) => { console.log('cb', err, res.code, res.json().echo); pm.environment.set('cb', res.json().echo) });
      pm.sendRequest({url: 'http://x/b', method: 'POST', header: {'X-T': '1'}, body: {mode: 'raw', raw: 'hi'}}).then(res => console.log('then', res.json().method));
      const r2 = await pm.sendRequest('http://x/c'); console.log('await', r2.code);
      pm.sendRequest('http://x/fail', (err, res) => console.log('err', err.message, res));
      setTimeout(() => { console.log('t1'); setTimeout(() => console.log('t2'), 30) }, 20);
      Promise.resolve().then(() => console.log('micro'));
    """, host=h)
    texts = [l["text"] for l in r.logs]
    for expect in ("cb null 200 http://x/a", "then POST", "await 200", "err ulanib bo'lmadi undefined", "t1", "t2", "micro"):
        assert expect in texts, texts
    assert texts.index("t1") < texts.index("t2") and r.scopes["environment"]["cb"] == "http://x/a"
    assert [q["url"] for q in h.sent] == ["http://x/a", "http://x/b", "http://x/c", "http://x/fail"]
    assert h.sent[1]["header"] == [{"key": "X-T", "value": "1"}] and h.sent[1]["body"]["raw"] == "hi"


def test_send_request_count_and_depth_limits():
    h = FakeHost()
    r = run("for (let i = 0; i < 5; i++) pm.sendRequest('http://x/' + i, (e, res) => console.log(i, e ? e.message : 'ok'))", host=h, limits=Limits(timeout_ms=5000, max_requests=3))
    texts = [l["text"] for l in r.logs]
    assert sum("ok" in t for t in texts) == 3 and sum("chegarasi (3)" in t for t in texts) == 2 and len(h.sent) == 3
    r = run("const go = d => pm.sendRequest('http://x/' + d, (e, res) => { if (e) console.log('stopped at', d, e.message); else go(d + 1) }); go(1)", host=FakeHost())
    assert any("chuqurligi chegarasi (5)" in l["text"] for l in r.logs)


def test_timers_interval_clear_and_total_timeout_includes_async():
    r = run("let n = 0; const id = setInterval(() => { n++; if (n === 3) { clearInterval(id); console.log('done', n) } }, 5)")
    assert [l["text"] for l in r.logs] == ["done 3"] and not r.errors
    t = time.perf_counter()
    r = run("await new Promise(r => setTimeout(r, 5000))", limits=Limits(timeout_ms=300))
    assert time.perf_counter() - t < 1.5 and r.errors[0]["name"] == "TimeoutError" and r.aborted


def test_script_errors_do_not_stop_other_scripts_and_carry_origin_and_line():
    s = sess(response=RESP)
    s.run(ScriptSource("zyx();", "test", "collection", "Col", "c"))
    s.run(ScriptSource("\n\nfoo(", "test", "folder", "Fold", "f"))                     # sintaksis xato
    s.run(ScriptSource("pm.test('still runs', () => {})", "test", "request", "Req", "r"))
    r = s.collect()
    e1, e2 = r.errors
    assert e1["name"] == "ReferenceError" and "zyx" in e1["message"] and e1["line"] == 1 and e1["origin"]["scope"] == "collection"
    assert e2["name"] == "SyntaxError" and e2["origin"]["scope"] == "folder" and e2["line"] in (3, 4)
    assert names(r) == {"still runs": True}


# ── require va kutubxonalar ──
def test_require_vendored_modules_and_unsupported_is_loud():
    r = run("""
      const _ = require('lodash'), CryptoJS = require('crypto-js'), moment = require('moment'), uuid = require('uuid'), chai = require('chai'), xml2js = require('xml2js');
      pm.test('libs', () => { pm.expect(_.chunk([1,2,3], 2)).to.have.lengthOf(2); pm.expect(CryptoJS.MD5('a').toString()).to.equal('0cc175b9c0f1b6a831c399e269772661');
        pm.expect(CryptoJS.HmacSHA256('m','k').toString()).to.have.lengthOf(64); pm.expect(moment('2026-11-03').add(1,'d').format('YYYY-MM-DD')).to.equal('2026-11-04');
        pm.expect(uuid.v4()).to.match(/^[0-9a-f]{8}-/); pm.expect(uuid.validate(uuid.v4())).to.be.true; pm.expect(chai.expect(1).to.equal).to.be.a('function') });
      pm.test('AES roundtrip + random', () => { const c = CryptoJS.AES.encrypt('hello', 'pw').toString(); pm.expect(CryptoJS.AES.decrypt(c, 'pw').toString(CryptoJS.enc.Utf8)).to.equal('hello');
        pm.expect(CryptoJS.AES.encrypt('hello', 'pw').toString()).to.not.equal(c) });
      pm.test('globals _ moment dayjs btoa atob', () => { pm.expect(_.sum([1,2])).to.equal(3); pm.expect(btoa('hi')).to.equal('aGk='); pm.expect(atob('aGk=')).to.equal('hi'); pm.expect(dayjs('2026-01-02').year()).to.equal(2026) });
      pm.test('xml2js', () => { let out; xml2js.parseString('<a x="1"><b>t</b><b>u</b></a>', (e, r) => { out = r }); pm.expect(out.a.b).to.eql(['t','u']); pm.expect(out.a.$.x).to.equal('1') });
      require('cheerio');
    """)
    assert all(names(r).values()), r.tests
    assert r.errors and "cheerio" in r.errors[0]["message"]
    assert any("cheerio" in l["text"] and l["level"] == "warn" for l in r.logs)


# ── legacy ──
def test_legacy_globals_tests_postman_object_and_xml2json():
    r = run("""
      tests["Status code is 200"] = responseCode.code === 200;
      tests["Has Content-Type"] = responseHeaders["Content-Type"] === 'application/json' && responseHeaders['content-type'] === 'application/json';
      tests["Body is json"] = JSON.parse(responseBody).data.id === 7;
      tests["time ok"] = responseTime < 100;
      tests["bad"] = responseBody.indexOf('nope') !== -1;
      tests["env readable"] = environment.tok === 'T' && postman.getEnvironmentVariable('tok') === 'T';
      postman.setEnvironmentVariable('since', JSON.parse(responseBody).data.id); postman.setGlobalVariable('gl', 'x'); postman.clearEnvironmentVariable('tok');
      postman.setNextRequest('Other');
      tests["xml"] = xml2Json('<r><v>1</v></r>').r.v === '1'; tests["lodash global"] = _.isArray([]); tests["moment global"] = moment('2026-01-01').isValid();
      tests["getResponseHeader"] = postman.getResponseHeader('x-id') === '7';
    """)
    t = names(r)
    assert t.pop("bad") is False and all(t.values()), r.tests
    assert r.scopes["environment"] == {"since": "7"} and r.scopes["globals"]["gl"] == "x" and r.next_set and r.next_request == "Other"
    assert next(x for x in r.tests if x["name"] == "bad")["legacy"] is True


def test_set_next_request_variants_and_skip_request_rules():
    assert run("pm.execution.setNextRequest(null)").next_set and run("pm.execution.setNextRequest(null)").next_request is None
    assert run("postman.setNextRequest('X')").next_request == "X"
    assert not run("pm.test('x',()=>{})").next_set
    r = run("pm.execution.skipRequest()", kind="prerequest", response=None)
    assert r.skip
    r = run("pm.execution.skipRequest()", kind="test")
    assert not r.skip and any("skipRequest" in l["text"] for l in r.logs)


def test_unsupported_apis_warn_loudly_and_do_not_throw():
    r = run("pm.visualizer.set('<b>x</b>'); pm.vault.get('k'); const j = pm.cookies.jar(); $; tv4.validate({}, {}); pm.nothingHere.deep.chain();")
    texts = " ".join(l["text"] for l in r.logs)
    for what in ("pm.visualizer", "pm.vault", "tv4", "pm.nothingHere"):
        assert what in texts, texts
    assert all(l["level"] == "warn" for l in r.logs) and not r.errors


def test_cookie_jar_partial_api_uses_host():
    h = FakeHost()
    r = run("""const jar = pm.cookies.jar();
      await new Promise(res => jar.set('http://x.test/', 'k', 'v', res));
      jar.get('http://x.test/', 'k', (e, v) => console.log('got', v)); console.log('all', JSON.stringify(await jar.getAll('http://x.test/')))""", host=h)
    assert h.cookies == {"k": "v"} and any(l["text"] == "got v" for l in r.logs)


def test_no_active_environment_warns_and_keeps_run_local():
    r = run("pm.environment.set('a', 1)", active_env=False)
    assert any("Faol muhit" in l["text"] for l in r.logs) and r.scopes["environment"]["a"] == 1


# ── xavfsizlik ──
def test_no_host_surface_and_constructor_escape_fails():
    r = run("""
      const t = ['require','process','fetch','XMLHttpRequest','Buffer','std','os','WebSocket','window','document','module','exports','__dirname','importScripts','Deno','Bun'].map(n => n + ':' + (n === 'require' ? typeof globalThis.require : typeof globalThis[n]));
      console.log(t.join(','));
      let esc = 'none'; try { esc = this.constructor.constructor('return typeof process')() } catch (e) { esc = 'blocked' } console.log('escape:' + esc);
      let ev = 'none'; try { ev = typeof eval('typeof process') } catch (e) { ev = 'blocked' } console.log('eval:' + ev);
      let imp = 'x'; try { await import('os'); imp = 'LOADED' } catch (e) { imp = 'rejected' } console.log('import:' + imp);
      let w = 'x'; try { w = typeof new Function('return globalThis.process')() } catch (e) { w = 'blocked' } console.log('Function:' + w);
    """)
    out = [l["text"] for l in r.logs]
    assert "require:function" in out[0]            # bizning require (faqat vendored modullar)
    assert all(not x.endswith(":object") and not x.endswith(":function") for x in out[0].split(",") if not x.startswith("require")), out[0]
    assert out[1] == "escape:undefined" and out[2] == "eval:string" and out[3] == "import:rejected" and out[4] == "Function:undefined"
    r = run("require('fs'); ")
    assert "Cannot find module 'fs'" in r.errors[0]["message"]
    r = run("require('child_process').execSync('echo pwned')")
    assert r.errors and "child_process" in r.errors[0]["message"]


def test_cannot_reach_python_or_host_objects():
    r = run("console.log(typeof __send, typeof __libsrc, typeof __rand, typeof __cookie, typeof Python, typeof __S)")
    assert r.logs[0]["text"] == "undefined undefined undefined undefined undefined undefined"


def test_infinite_loop_memory_bomb_and_recursion_are_contained():
    t = time.perf_counter()
    r = run("while (true) {}", limits=Limits(timeout_ms=400))
    assert time.perf_counter() - t < 2 and r.errors[0]["name"] == "TimeoutError" and "400 ms" in r.errors[0]["message"]
    r = run("try { while (true) {} } catch (e) { console.log('swallowed') }", limits=Limits(timeout_ms=300))
    assert r.errors[0]["name"] == "TimeoutError" and not any(l["text"] == "swallowed" for l in r.logs)       # catch yuta olmaydi
    r = run("const a = []; while (true) a.push(new Array(10000).fill(1))", limits=Limits(timeout_ms=5000, memory_mb=24))
    assert r.errors[0]["name"] == "MemoryError" and "24 MB" in r.errors[0]["message"]
    r = run("function f() { return f() + 1 } f()")
    assert r.errors and "stack" in r.errors[0]["message"].lower()
    r = run("pm.test('after recursion ok', () => {})")
    assert names(r) == {"after recursion ok": True}


def test_after_timeout_remaining_scripts_are_skipped_but_results_kept():
    s = sess(limits=Limits(timeout_ms=300), response=RESP)
    s.run(ScriptSource("pm.test('first', () => {}); pm.environment.set('k', 'v')", "test", "collection", "C", "c"))
    s.run(ScriptSource("while (true) {}", "test", "folder", "F", "f"))
    s.run(ScriptSource("pm.test('never', () => {})", "test", "request", "R", "r"))
    r = s.collect()
    assert names(r) == {"first": True} and r.scopes["environment"]["k"] == "v" and r.aborted
    assert [e["name"] for e in r.errors] == ["TimeoutError", "Skipped"]


# ── thread-safety ──
def test_concurrent_sessions_in_10_threads_are_isolated():
    errors, results = [], {}

    def worker(i):
        try:
            for n in range(6):
                s = sess(host=FakeHost(), response=RESP, scopes={"environment": {"me": str(i)}})
                s.run(ScriptSource("""
                  pm.environment.set('mine', pm.environment.get('me') + ':' + %d);
                  await new Promise(r => setTimeout(r, %d));
                  const res = await pm.sendRequest('http://x/' + pm.environment.get('me'));
                  pm.test('own data', () => { pm.expect(pm.environment.get('mine')).to.equal('%d:%d'); pm.expect(res.json().echo).to.equal('http://x/%d') });
                  pm.test('libs', () => pm.expect(require('lodash').sum([%d, 1])).to.equal(%d))
                """ % (n, (i * 3 + n) % 7, i, n, i, i, i + 1), "test", "request", "R", "r"))
                r = s.collect()
                assert not r.errors and all(t["passed"] for t in r.tests) and len(r.tests) == 2 and r.scopes["environment"]["mine"] == "%d:%d" % (i, n), (i, n, r.errors, r.tests)
                results[(i, n)] = True
        except Exception as e:      # noqa: BLE001
            errors.append(repr(e))
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    [t.start() for t in ts]
    [t.join(60) for t in ts]
    assert not errors, errors
    assert len(results) == 60


def test_limits_from_meta_are_clamped():
    assert Limits.from_meta({}).timeout_ms == 10000
    l = Limits.from_meta({"script_limits": {"timeout_ms": 1, "memory_mb": 99999, "max_requests": "7", "bogus": 1}})
    assert (l.timeout_ms, l.memory_mb, l.max_requests) == (100, 1024, 7)
    assert Limits.from_meta({"script_limits": {"timeout_ms": "x"}}).timeout_ms == 10000
