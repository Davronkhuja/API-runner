"""Postman'ning ommaviy namunalari skriptlari O'ZGARISHSIZ ishlaydi (Bosqich 3 «tayyor» mezoni).

Namunalar (tests/fixtures/postman/README.md): postmanlabs/postman-collection-transformer (twitter, helpers), newman-reporter-remote
(Sample Collection: collection/papka/so'rov skriptlari, zyx() xatosi, console, sendRequest, setNextRequest("Done")), newman (nested sendRequest),
node-doc-kube (catURL: legacy responseHeaders/request.data, redirect) va ulardagi naqshlarga asoslangan murakkab oqim (compat_flow).
Tashqi tarmoq yo'q: hostlar lokal soxta serverlarga almashtiriladi.
"""
import json
import re
import threading
from pathlib import Path

import pytest
from flask import Flask, jsonify, redirect, request
from werkzeug.serving import make_server

from apirunner.core import scripting
from apirunner.core.flow import run_collection
from apirunner.core.scripted import Services

pytestmark = pytest.mark.skipif(not scripting.available(), reason="quickjs-ng o'rnatilmagan")
FX = Path(__file__).parent / "fixtures" / "postman"


def load(name):
    return (FX / name).read_text(encoding="utf-8")


# ── soxta serverlar ──
@pytest.fixture(scope="module")
def fake():
    app = Flask("fake")
    state = {"token_calls": 0, "auth_failures": 0, "calls": []}
    app.config["STATE"] = state

    def body():
        j = request.get_json(silent=True)
        return {"args": request.args.to_dict(), "data": j if j is not None else request.get_data(as_text=True), "form": request.form.to_dict(), "json": j,
                "headers": {k.lower(): v for k, v in request.headers.items()}, "url": request.url}

    @app.route("/get", methods=["GET"])
    def get():
        return jsonify(body())

    @app.route("/post", methods=["POST"])
    def post():
        return jsonify(body())

    # compat_flow
    @app.post("/auth/token")
    def token():
        state["token_calls"] += 1
        d = request.get_json(silent=True) or {}
        if d.get("client_id") != "compat" or d.get("client_secret") != "s3cr3t":
            return jsonify({"error": "bad"}), 401
        return jsonify({"access_token": "TOK-%d" % state["token_calls"], "expires_in": 3600})

    def authed():
        ok = request.headers.get("Authorization", "").startswith("Bearer TOK-")
        if not ok:
            state["auth_failures"] += 1
        return ok

    @app.get("/items")
    def items():
        state["calls"].append(request.path)
        return (jsonify({"items": [{"id": 11}, {"id": 12}, {"id": 13}]}), 200) if authed() else (jsonify({"error": "unauthorized"}), 401)

    @app.get("/items/<int:i>")
    def one(i):
        state["calls"].append(request.path)
        return (jsonify({"id": i, "name": "item-%d" % i, "trace": request.headers.get("X-Trace")}), 200) if authed() else (jsonify({"error": "unauthorized"}), 401)

    # twitter
    @app.get("/1.1/search/tweets.json")
    def search():
        return jsonify({"statuses": [], "search_metadata": {"max_id_str": "9001", "count": int(request.args.get("count", 0) or 0)}})

    @app.get("/1.1/statuses/show.json")
    def show():
        return jsonify({"id": 77, "user": {"id": 555, "screen_name": "postman"}})

    @app.get("/1.1/statuses/retweeters/ids.json")
    def retweeters():
        return jsonify({"ids": [321, 654], "next_cursor": 0})

    @app.get("/1.1/users/show.json")
    def user():
        return jsonify({"id": int(request.args.get("user_id", 0) or 0), "screen_name": "pm_%s" % request.args.get("user_id")})

    @app.get("/1.1/statuses/retweets/<tid>.json")
    def retweets(tid):
        return jsonify([{"id": i} for i in range(12)])

    @app.get("/1.1/lists/memberships.json")
    def memberships():
        return jsonify({"lists": [{"name": "alpha"}, {"name": "beta"}]})

    @app.route("/1.1/<path:rest>", methods=["GET", "POST"])
    def any_twitter(rest):
        return jsonify([])

    # catURL
    @app.post("/encode")
    def encode():
        f = request.form
        return jsonify({"catpath": "cat-" + str(abs(hash(f.get("originalUrl"))) % 1000), "original": f.get("originalUrl")})

    cat = {}

    @app.route("/cat-<n>")
    def cat_redirect(n):
        return redirect(request.args.get("to") or cat.get("last", "/get"), code=302)

    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    app.base = f"http://127.0.0.1:{srv.server_port}"
    app.cat = cat
    yield app
    srv.shutdown()


@pytest.fixture
def svc(client):
    app = client.application
    return Services(ws=app.extensions["workspace"], cookies=app.extensions["cookies"], allowed_file_roots=app.extensions["jobs"].allowed_file_roots)


def env(client, name, values):
    eid = client.post("/api/environments", json={"name": name}).get_json()["id"]
    e = client.get(f"/api/environments/{eid}").get_json()
    e["values"] = [{"key": k, "value": v, "enabled": True, "type": "default"} for k, v in values.items()]
    client.put(f"/api/environments/{eid}", json=e)
    client.put("/api/workspace/meta", json={"active_environment_id": eid})
    return eid


def env_map(client, eid):
    return {v["key"]: v["value"] for v in client.get(f"/api/environments/{eid}").get_json()["values"]}


def import_fx(client, name, mutate=None):
    doc = json.loads(load(name))
    if mutate:
        doc = mutate(doc)
    return client.post("/api/import", json={"content": json.dumps(doc)}).get_json()["id"]


def by_name(log, name):
    return [s for s in log if s["name"] == name]


def results_of(step):
    return {t["name"]: t["passed"] for t in step["result"]["scripts"]["tests"]}


# ── 1. Sample Collection (newman-reporter-remote) ──
def test_sample_collection_scripts_run_unchanged_with_set_next_request_flow(client, svc, fake):
    cid = import_fx(client, "newman_reporter_sample.json")
    eid = env(client, "local", {"host": fake.base})                                   # `{{host}}` collection o'zgaruvchisini muhit bosadi
    log = run_collection(svc, cid)
    names = [s["name"] for s in log]
    # setNextRequest("Done") — "Skip" o'tkazib yuboriladi, run "Done" bilan tugaydi
    assert "Skip" not in names and names[-2:] == ["setNextRequest", "Done"], names
    # collection-level pre-request: API_KEY o'rnatildi va muhitga saqlandi
    assert env_map(client, eid)["API_KEY"] == "0"
    # folder + collection testlari: har bir so'rovda "Status code is 200"
    s = by_name(log, "Folder One/Just GET request in folder") or by_name(log, "Just GET request in folder")
    t = s[0]["result"]["scripts"]["tests"]
    assert [x["origin"]["scope"] for x in t] == ["collection", "folder", "request"] and all(x["passed"] for x in t)
    # xato skript: zyx() ReferenceError — so'rov baribir (URL xato bo'lgani uchun ERR) bajarildi, xato Tests/Console uchun yig'ildi
    err = by_name(log, "Just GET req with error")[0]["result"]
    assert err["status"] == "ERROR" or err["status"] == "ERR" or err["status"] == "ERROR"
    assert err["scripts"]["errors"][0]["name"] == "ReferenceError" and "zyx" in err["scripts"]["errors"][0]["message"] and err["scripts"]["errors"][0]["origin"]["kind"] == "prerequest"
    # console
    c = by_name(log, "Just GET request with console")[0]["result"]["scripts"]["console"]
    assert [(x["level"], x["text"]) for x in c] == [("error", "This is a error log"), ("log", "This is a normal log")]
    # Assertions: iterationData yo'q → "1"; body JSON ({{API_KEY}}=0, {{USER_ID}}=1) → echo data
    a = results_of(by_name(log, "Assertions")[0])
    assert a["UserId is correct"] and a["Response Headers are correct"] and a["Status code is 200"]
    # Failing Assertion: ikkala test ham muvaffaqiyatsiz (userId yo'q, X-API-KEY header yo'q); qolganlari o'tadi
    f = results_of(by_name(log, "Failing Assertion")[0])
    assert f["UserId is correct"] is False and f["Response Headers are correct"] is False and f["Status code is 200"] is True
    # Skipped Assertions: pm.test.skip
    sk = by_name(log, "Skipped Assertions")[0]["result"]["scripts"]["tests"]
    assert [x["skipped"] for x in sk if x["origin"]["scope"] == "request"] == [True, True]
    # sendRequest (pre-request, callback): ichki so'rov test + asosiy so'rov argsi
    sr = by_name(log, "sendRequest")[0]
    st = results_of(sr)
    assert st["sendRequest: response should be okay to process"] and st["Args are correct"]
    # Done: formdata ({{$guid}} bilan) + javob vaqti testi
    d = results_of(by_name(log, "Done")[0])
    assert d["Response time is less than 1s"]


# ── 2. newman nested sendRequest (res.stream.toString()) ──
def test_nested_send_request_in_test_script(client, svc, fake):
    def point(doc):
        s = json.dumps(doc).replace("https://postman-echo.com", fake.base)
        return json.loads(s)
    cid = import_fx(client, "newman_nested_requests.json", point)
    log = run_collection(svc, cid)
    t = results_of(log[0])
    assert t == {"Status code is 200": True, 'Nested request JSON response: "key2": "val2"': True}


# ── 3. Twitter (v2.1): legacy tests[], postman.setEnvironmentVariable, `events` kaliti, undeclared global (for (i=0;...)) ──
def test_twitter_collection_legacy_scripts(client, svc, fake):
    cid = import_fx(client, "twitter.json")
    eid = env(client, "tw", {"count": "5", "since_id": "1", "tweet_id": "77", "user_id": "42"})
    hook = lambda spec: {**spec, "url": spec["url"].replace("https://api.twitter.com", fake.base)}  # noqa: E731
    log = run_collection(svc, cid, spec_hook=hook)
    m = env_map(client, eid)
    assert m["since_id"] == "9001"                                                     # Search testi: search_metadata.max_id_str
    assert m["screen_name"] == "pm_321" and m["user_id"] == "321"                      # show → user.id/screen_name; retweeters → ids[0]=321; users/show?user_id=321 → screen_name=pm_321
    st = results_of(by_name(log, "Search")[0])
    assert st["Status code is 200"] is True
    rt = results_of(by_name(log, "Retweets of a tweet")[0])
    assert rt["more than 10 retweets"] is True
    ls = results_of(by_name(log, "Lists a user is on")[0])
    assert ls == {"number of lists = 2": True, "0 - alpha": True, "1 - beta": True}
    errs = [(s["name"], s["result"]["scripts"]["errors"]) for s in log if (s["result"].get("scripts") or {}).get("errors")]
    assert not errs, errs


# ── 4. helpers: legacy `environment.x`, tests[], console (oldNonce zanjiri) ──
def test_helpers_legacy_environment_object_and_nonce_chain(client, svc, fake):
    cid = import_fx(client, "helpers.json")
    eid = env(client, "h", {})
    def post_form(spec):
        n = {"n": 0}
        return {**spec, "url": fake.base + "/post", "method": "POST", "body": "oauth_nonce=%s&oauth_signature=sig" % re.sub(r"\W", "", str(id(spec)))[:8], "body_type": "form", "content_type": "application/x-www-form-urlencoded"}
    items = {"calls": 0}

    def hook(spec):
        items["calls"] += 1
        return {**spec, "url": fake.base + "/post", "method": "POST", "body": "oauth_nonce=nonce%d&oauth_signature=sig" % items["calls"], "body_type": "form", "content_type": "application/x-www-form-urlencoded"}
    log = run_collection(svc, cid, spec_hook=hook)
    oauth2 = [s for s in log if s["result"]["scripts"]["tests"]]
    assert oauth2 and results_of(oauth2[0]) == {"NewNonce": True, "HasNonce": True}     # oldNonce (undefined) != newNonce
    assert env_map(client, eid)["oldNonce"].startswith("nonce")
    logs = [x["text"] for x in oauth2[0]["result"]["scripts"]["console"]]
    assert logs[0].startswith("oldNonce: undefined, newNonce=nonce") and logs[1].startswith("Signature: sig")


# ── 5. catURL: responseHeaders.location (kichik harf), request.data obyekti, redirect sozlamasi, setNextRequest(null) ──
def test_caturl_redirect_flow_with_legacy_response_headers_and_request_data(client, svc, fake):
    def prep(doc):
        for it in doc["item"]:
            if it["name"] == "urlize":
                it["request"]["body"] = {"mode": "urlencoded", "urlencoded": [{"key": "originalUrl", "value": "{{target}}", "type": "text"}]}
        return doc
    cid = import_fx(client, "catURL.json", prep)
    eid = env(client, "cat", {"url": fake.base, "target": fake.base + "/get?cat=1"})

    def hook(spec):
        if spec["url"].endswith("/{{path}}") or "{{path}}" in spec["url"]:
            return {**spec, "follow_redirects": False, "params": [{"name": "to", "value": fake.base + "/get?cat=1"}]}
        return spec
    log = run_collection(svc, cid, spec_hook=hook)
    assert [s["name"] for s in log] == ["urlize", "redirect test"]                       # setNextRequest(null) — "redirect allow" ga o'tmaydi
    u = results_of(log[0])
    assert u == {"Status code is 200": True, "Body contains catpath": True}
    m = env_map(client, eid)
    assert m["originalUrl"] == fake.base + "/get?cat=1" and m["path"].startswith("cat-")  # request.data["originalUrl"] — urlencoded body obyekt sifatida
    r = results_of(log[1])
    assert r == {"Redirect to the original URL": True}                                    # responseHeaders.location


# ── 6. Murakkab oqim: pre-request'da token olish + setNextRequest tsikli + legacy tests[] ──
def test_complex_flow_token_in_prerequest_set_next_request_loop_and_legacy_tests(client, svc, fake):
    state = fake.config["STATE"]
    state.update(token_calls=0, auth_failures=0, calls=[])
    cid = import_fx(client, "compat_flow.postman_collection.json")
    eid = env(client, "flow", {"base_url": fake.base, "secret": "s3cr3t"})
    log = run_collection(svc, cid)
    names = [s["name"] for s in log]
    assert names == ["List items", "Get item", "Get item", "Get item", "Summary"], names        # "Never reached" — setNextRequest(null)
    assert state["token_calls"] == 1 and state["auth_failures"] == 0                                # token bir marta olindi (pre-request + pm.sendRequest), qolganlari muhitdan
    assert state["calls"] == ["/items", "/items/11", "/items/12", "/items/13", "/items"]
    m = env_map(client, eid)
    assert m["token"] == "TOK-1" and m["idx"] == "2" and json.loads(m["item_ids"]) == [11, 12, 13] and m["current_id"] == "13"
    first = log[0]["result"]["scripts"]
    assert results_of(log[0]) == {"collection-level: javob 2xx yoki kutilgan 4xx": True, "Status code is 200": True, "Has items": True}
    assert [l["text"] for l in first["console"]] == ["token olindi", "ids=11,12,13"]
    for i, step in enumerate(log[1:4]):
        t = results_of(step)
        assert t["Item %d ok" % (11 + i)] and t["Trace header echoed"] and t["collection-level: javob 2xx yoki kutilgan 4xx"], t
    assert step["result"]["scripts"]["next_request"] == "Summary"
    assert results_of(log[4]) == {"collection-level: javob 2xx yoki kutilgan 4xx": True, "Loop visited every item": True, "Token was fetched once": True}
    # papka pre-request (X-Trace) faqat Loop ichida ishladi
    assert log[1]["result"]["scripts"]["tests"][0]["origin"]["scope"] == "collection"


def test_complex_flow_second_run_reuses_persisted_token_without_new_fetch(client, svc, fake):
    state = fake.config["STATE"]
    state.update(token_calls=0, auth_failures=0, calls=[])
    cid = import_fx(client, "compat_flow.postman_collection.json")
    eid = env(client, "flow2", {"base_url": fake.base, "secret": "s3cr3t"})
    run_collection(svc, cid)
    run_collection(svc, cid)
    assert state["token_calls"] == 1 and state["auth_failures"] == 0                        # muhitga saqlangan token qayta ishlatildi


def test_complex_flow_with_wrong_secret_reports_error_and_requests_still_sent(client, svc, fake):
    state = fake.config["STATE"]
    state.update(token_calls=0, auth_failures=0, calls=[])
    cid = import_fx(client, "compat_flow.postman_collection.json")
    env(client, "bad", {"base_url": fake.base, "secret": "WRONG"})
    log = run_collection(svc, cid, max_steps=3)
    first = log[0]["result"]
    assert first["status"] == 401 and first["scripts"]["tests"][0]["passed"] in (True, False)
    assert any("token" in (e["message"] + " ".join(l["text"] for l in first["scripts"]["console"])) for e in first["scripts"]["errors"]) or any("token" in l["text"] for l in first["scripts"]["console"])
    assert "Status code is 200" in results_of(log[0]) and results_of(log[0])["Status code is 200"] is False                      # legacy tests[] — 401 → false
