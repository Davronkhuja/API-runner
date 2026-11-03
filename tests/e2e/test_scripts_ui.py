"""Bosqich 3 UI: skript muharriri, Testlar tabi, Console paneli, Sozlamalar → Skriptlar, Runner oqimi, quickjs-ng yo'q holat."""
import json
import re

import pytest
from playwright.sync_api import expect

from apirunner.core import scripting
from tests.e2e.conftest import eventually

pytestmark = pytest.mark.skipif(not scripting.available(), reason="quickjs-ng o'rnatilmagan")
T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


def ev(kind, code):
    return {"listen": kind, "script": {"type": "text/javascript", "exec": code.split("\n")}}


def req(i, name, url="{{base}}/echo", events=(), method="GET"):
    return {"id": i, "name": name, "request": {"method": method, "header": [], "url": {"raw": url}}, "response": [], **({"event": list(events)} if events else {})}


@pytest.fixture
def world(app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base", "value": echo_server}]
    col["item"] = [req("a", "Alpha"), req("b", "Beta"), req("c", "Gamma"), req("d", "Delta")]
    app.api("PUT", f"/api/collections/{cid}", col)
    eid = app.api("POST", "/api/environments", {"name": "E"})["id"]
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    return cid, eid


@pytest.fixture
def ui(app, page, world):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def open_req(p, name):
    p.locator(f"[data-name='{name}']").dblclick()
    expect(T(p, "request-editor")).to_be_visible()


def send(p):
    with p.expect_response(lambda r: r.url.endswith("/run_one")) as i:
        T(p, "send").click()
    return i.value.json()


def script_section(p):
    p.click("[data-section=scripts]")
    expect(T(p, "scripts-panel")).to_be_visible()


def write(p, kind, code):
    T(p, f"script-tab-{kind}").click()
    T(p, f"script-{kind}").fill(code)


# ── muharrir ──
def test_scripts_section_edit_save_persists_as_postman_events_and_marks_dot(ui, app, world):
    cid, _ = world
    open_req(ui, "Alpha")
    expect(T(ui, "scripts-dot")).to_have_count(0)
    script_section(ui)
    write(ui, "pre", "console.log('pre')\npm.variables.set('a', 1)")
    write(ui, "test", "pm.test('ok', () => {})")
    expect(T(ui, "scripts-dot")).to_have_count(1)
    expect(T(ui, "dirty-dot")).to_have_count(1)
    T(ui, "save").click()
    eventually(lambda: len(app.api("GET", f"/api/collections/{cid}")["item"][0].get("event", [])) == 2)
    e = {x["listen"]: x["script"]["exec"] for x in app.api("GET", f"/api/collections/{cid}")["item"][0]["event"]}
    assert e == {"prerequest": ["console.log('pre')", "pm.variables.set('a', 1)"], "test": ["pm.test('ok', () => {})"]}
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    open_req(ui, "Alpha")
    script_section(ui)
    expect(T(ui, "script-pre")).to_contain_text("pm.variables.set")
    T(ui, "script-tab-test").click()
    expect(T(ui, "script-test")).to_contain_text("pm.test('ok'")


def test_unsaved_script_edits_survive_reload_as_dirty_draft(ui):
    open_req(ui, "Alpha")
    script_section(ui)
    write(ui, "test", "// qoralama")
    ui.wait_for_timeout(400)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    expect(T(ui, "request-editor")).to_be_visible()
    ui.click("[data-section=scripts]")
    T(ui, "script-tab-test").click()
    expect(T(ui, "script-test")).to_contain_text("// qoralama")


def test_snippets_insert_at_cursor(ui):
    open_req(ui, "Alpha")
    script_section(ui)
    T(ui, "script-tab-test").click()
    T(ui, "snippet").filter(has_text="Status kodi 200").click()
    expect(T(ui, "script-test")).to_contain_text("pm.response.to.have.status(200)")
    T(ui, "script-tab-pre").click()
    expect(T(ui, "snippet").filter(has_text="Status kodi 200")).to_have_count(0)           # test snippetlari pre-request'da yo'q
    expect(T(ui, "snippet").filter(has_text="token bo'lmasa olish")).to_have_count(1)


def test_autocomplete_offers_pm_api(ui):
    open_req(ui, "Alpha")
    script_section(ui)
    T(ui, "script-pre").click()
    ui.keyboard.type("pm.environment.s")
    tip = ui.locator(".cm-tooltip-autocomplete")
    expect(tip).to_be_visible()
    expect(tip).to_contain_text("pm.environment.set")
    ui.keyboard.press("Enter")
    expect(T(ui, "script-pre")).to_contain_text("pm.environment.set")


# ── Testlar tabi ──
def test_tests_tab_shows_pass_fail_skip_with_origin_and_errors_link_to_line(ui, world):
    cid, _ = world
    open_req(ui, "Alpha")
    script_section(ui)
    write(ui, "test", "pm.test('status ok', () => pm.response.to.have.status(200));\n"
                      "pm.test('bad one', () => pm.expect(1).to.equal(2));\n"
                      "pm.test.skip('later', () => {});\n"
                      "tests['legacy ok'] = true;\n"
                      "undefinedCall();")
    d = send(ui)
    assert d["status"] == 200 and d["scripts"]["tests"]
    expect(T(ui, "rp-tests-badge")).to_have_text("2/3")                                    # o'tgan / (jami - skip)
    T(ui, "rp-tests-tab").click()
    expect(T(ui, "tests-summary")).to_contain_text("2 o'tdi")
    expect(T(ui, "tests-summary")).to_contain_text("1 muvaffaqiyatsiz")
    rows = T(ui, "test-row")
    expect(rows).to_have_count(4)
    expect(rows.nth(0)).to_have_attribute("data-status", "pass")
    expect(rows.nth(1)).to_have_attribute("data-status", "fail")
    expect(rows.nth(1)).to_contain_text("expected 1 to equal 2")
    expect(rows.nth(2)).to_have_attribute("data-status", "skip")
    expect(rows.nth(3)).to_have_attribute("data-status", "pass")
    expect(rows.nth(0)).to_contain_text("So'rov")
    err = T(ui, "script-error")
    expect(err).to_have_count(1)
    expect(err).to_contain_text("ReferenceError")
    expect(err).to_contain_text("undefinedCall")
    expect(T(ui, "script-error-origin")).to_contain_text("Tests")
    T(ui, "script-error-link").click()                                                      # → muharrir, 4-qator belgilanadi
    expect(T(ui, "scripts-panel")).to_be_visible()
    expect(T(ui, "script-test")).to_be_focused()
    expect(ui.locator(".cm-err-line").filter(has_text="undefinedCall")).to_have_count(1)             # xato qatori
    expect(ui.locator(".cm-err-line").filter(has_text="bad one")).to_have_count(1)                   # muvaffaqiyatsiz test qatori ham belgilangan


def test_failing_test_link_jumps_to_its_line(ui):
    open_req(ui, "Alpha")
    script_section(ui)
    write(ui, "test", "// 1\n// 2\npm.test('boom', () => { throw new Error('xato') });")
    send(ui)
    T(ui, "rp-tests-tab").click()
    expect(T(ui, "test-error")).to_contain_text("Error: xato")
    T(ui, "test-error-link").click()
    expect(ui.locator(".cm-err-line")).to_contain_text("pm.test('boom'")


def test_no_scripts_hint_and_success_badge(ui):
    open_req(ui, "Beta")
    send(ui)
    expect(T(ui, "rp-tests-badge")).to_have_text("0")
    T(ui, "rp-tests-tab").click()
    expect(T(ui, "rp-tests-none")).to_be_visible()


def test_collection_and_folder_scripts_run_in_order_and_error_links_open_their_tab(ui, app, world):
    cid, _ = world
    col = app.api("GET", f"/api/collections/{cid}")
    col["event"] = [ev("test", "pm.test('col test', () => {});\nboomCollection();")]
    col["item"] = [{"id": "f1", "name": "Fold", "event": [ev("prerequest", "console.log('folder pre')")], "item": [req("x", "Inner", events=[ev("test", "pm.test('req test', () => {})")])]}] + col["item"]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    open_req(ui, "Inner")
    send(ui)
    T(ui, "rp-tests-tab").click()
    expect(T(ui, "test-origin")).to_have_text(["Collection", "So'rov"])
    expect(T(ui, "script-error-origin")).to_contain_text("Collection «Col»")
    T(ui, "script-error-link").click()
    expect(T(ui, "tab-collection")).to_be_visible()                                         # collection sozlamalari tabi, Scripts bo'limi
    expect(T(ui, "script-test")).to_contain_text("boomCollection()")
    expect(ui.locator(".cm-err-line")).to_contain_text("boomCollection")


# ── muhit o'zgaruvchilari ──
def test_script_variables_are_saved_to_active_environment_and_visible_in_ui(ui, app, world):
    _, eid = world
    open_req(ui, "Alpha")
    script_section(ui)
    write(ui, "test", "pm.environment.set('from_script', pm.response.code)")
    send(ui)
    eventually(lambda: any(v["key"] == "from_script" and v["value"] == "200" for v in app.api("GET", f"/api/environments/{eid}")["values"]))
    T(ui, "env-vars-btn").click()
    expect(T(ui, "env-tab")).to_be_visible()
    expect(ui.locator("[data-testid=env-key]").last).to_have_value("from_script")


def test_variables_set_in_pre_request_are_used_by_the_request(ui):
    open_req(ui, "Alpha")
    ui.fill("[data-testid=url]", "{{base}}/echo?who={{who}}")
    script_section(ui)
    write(ui, "pre", "pm.variables.set('who', 'script-' + pm.info.requestName)")
    d = send(ui)
    assert d["response"]["args"] == {"who": ["script-Alpha"]}


# ── Console paneli ──
def test_console_panel_collects_request_logs_script_logs_and_errors(ui):
    open_req(ui, "Alpha")
    script_section(ui)
    write(ui, "test", "console.log('salom', {a: 1});\nconsole.warn('ehtiyot');\nconsole.error('xato!');\nmissing();")
    expect(T(ui, "console")).to_have_count(0)
    send(ui)
    expect(T(ui, "console-unread")).to_be_visible()                                         # panel yopiq: o'qilmagan xatolar
    T(ui, "console-btn").click()
    expect(T(ui, "console")).to_be_visible()
    expect(T(ui, "console-unread")).to_have_count(0)
    texts = [e for e in T(ui, "console-text").all_inner_texts()]
    assert any(t.startswith("GET ") for t in texts) and any(t.startswith("200") for t in texts)
    assert "salom {\n  \"a\": 1\n}" in texts and "ehtiyot" in texts and "xato!" in texts
    assert any(t.startswith("ReferenceError") for t in texts)
    levels = [e.get_attribute("data-level") for e in T(ui, "console-entry").all()]
    assert {"request", "response", "log", "warn", "error", "script-error"} <= set(levels)
    expect(T(ui, "console-origin").first).to_contain_text("So'rov «Alpha» · Tests")
    ui.click("[data-filter=warn]")                                                          # ogohlantirishlarni yashirish
    expect(T(ui, "console-entry").filter(has_text="ehtiyot")).to_have_count(0)
    ui.click("[data-filter=warn]")
    T(ui, "console-search").fill("salom")
    expect(T(ui, "console-entry")).to_have_count(1)
    T(ui, "console-search").fill("")
    T(ui, "console-goto").first.click()                                                      # xato qatoriga o'tish
    expect(ui.locator(".cm-err-line")).to_have_count(1)
    T(ui, "console-clear").click()
    expect(T(ui, "console-empty")).to_be_visible()
    T(ui, "console-close").click()
    expect(T(ui, "console")).to_have_count(0)


def test_console_shows_unsupported_api_warnings(ui):
    open_req(ui, "Alpha")
    script_section(ui)
    write(ui, "test", "pm.visualizer.set('<b>x</b>'); require('cheerio');")
    send(ui)
    T(ui, "console-btn").click()
    warns = T(ui, "console-entry").filter(has=ui.locator("[data-level=warn]"))
    texts = " ".join(T(ui, "console-text").all_inner_texts())
    assert "pm.visualizer" in texts and "cheerio" in texts and "qo'llab-quvvatlanmaydi" in texts


# ── Sozlamalar → Skriptlar ──
def test_settings_script_limits_save_apply_and_reset(ui, app):
    T(ui, "settings-btn").click()
    expect(T(ui, "script-status")).to_contain_text("quickjs-ng")
    T(ui, "script-limit-timeout").fill("150")
    T(ui, "script-limit-memory").fill("32")
    T(ui, "script-limit-requests").fill("1")
    T(ui, "script-limits-save").click()
    eventually(lambda: app.api("GET", "/api/workspace")["meta"].get("script_limits") == {"timeout_ms": 150, "memory_mb": 32, "max_requests": 1})
    open_req(ui, "Alpha")
    script_section(ui)
    write(ui, "test", "while (true) {}")
    d = send(ui)
    assert d["status"] == 200 and d["scripts"]["errors"][0]["name"] == "TimeoutError"
    T(ui, "rp-tests-tab").click()
    expect(T(ui, "script-error")).to_contain_text("150 ms")
    ui.locator("[data-testid=tab]").filter(has_text="Sozlamalar").click()
    T(ui, "script-limits-reset").click()
    expect(T(ui, "script-limit-timeout")).to_have_value("10000")
    T(ui, "script-limits-save").click()
    eventually(lambda: app.api("GET", "/api/workspace")["meta"]["script_limits"] == {"timeout_ms": 10000, "memory_mb": 64, "max_requests": 10})


# ── quickjs-ng yo'q ──
def test_unavailable_state_shows_explanation_and_install_command(app, page, world, monkeypatch):
    from apirunner.core.scripting import sandbox
    monkeypatch.setattr(sandbox, "quickjs", None)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    open_req(page, "Alpha")
    page.click("[data-section=scripts]")
    expect(T(page, "scripts-off")).to_contain_text("Skriptlar o'chiq")
    expect(T(page, "scripts-install-cmd")).to_contain_text("pip install quickjs-ng")
    expect(T(page, "script-tab-pre")).to_be_visible()                                       # tablar ko'rinadi, matn saqlanadi
    write(page, "test", "pm.test('x', () => {})")
    d = send(page)
    assert d["status"] == 200 and d["scripts"]["available"] is False
    T(page, "rp-tests-tab").click()
    expect(T(page, "rp-scripts-off")).to_contain_text("quickjs-ng")
    T(page, "settings-btn").click()
    expect(T(page, "script-status")).to_contain_text("o'chiq")
    expect(T(page, "script-install-cmd")).to_contain_text("pip install quickjs-ng")
    T(page, "console-btn").click()
    expect(T(page, "console-text").filter(has_text="Skriptlar o'chiq")).to_have_count(1)


# ── Runner oqimi ──
def run_collection_ui(p):
    p.locator("[data-name='Col']").click(button="right")
    p.click("[data-act=runner]")
    expect(T(p, "runner-tab")).to_be_visible()
    T(p, "runner-run").click()
    expect(T(p, "runner-run")).to_be_enabled(timeout=20000)


def names(p):
    return [x.strip() for x in T(p, "runner-row").locator("span:nth-child(3)").all_inner_texts()]


def test_runner_set_next_request_skip_request_and_variables_between_requests(ui, app, world):
    cid, eid = world
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [
        req("a", "Alpha", "{{base}}/echo", [ev("test", "pm.environment.set('carry', 'from-alpha');\npm.execution.setNextRequest('Gamma');")]),
        req("b", "Beta", "{{base}}/echo", [ev("test", "console.log('beta must not run')")]),
        req("c", "Gamma", "{{base}}/echo", [ev("prerequest", "pm.execution.skipRequest()")]),
        req("d", "Delta", "{{base}}/echo?carry={{carry}}", [ev("test", "pm.test('carried', () => pm.expect(pm.response.json().args.carry[0]).to.equal('from-alpha'));")]),
    ]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    run_collection_ui(ui)
    assert names(ui) == ["Alpha", "Gamma", "Delta"]                                          # Beta o'tkazib yuborildi (setNextRequest); Gamma skipRequest; Delta oldingi o'zgaruvchini ko'radi
    assert T(ui, "runner-result").all_inner_texts() == ["200", "SKIPPED", "200"]
    expect(T(ui, "runner-s-fail")).to_have_text("0")                                         # SKIPPED xato hisoblanmaydi
    eventually(lambda: any(v["key"] == "carry" for v in app.api("GET", f"/api/environments/{eid}")["values"]))


def test_runner_infinite_set_next_request_loop_is_stopped_with_message(ui, app, world):
    cid, _ = world
    ui.add_init_script("window.__MAX_RUN_STEPS = 25")
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [req("a", "Alpha", events=[ev("test", "pm.execution.setNextRequest('Alpha')")])]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    run_collection_ui(ui)
    assert T(ui, "runner-row").count() == 25
    T(ui, "console-btn").click()
    expect(T(ui, "console-text").filter(has_text="cheksiz tsikl himoyasi")).to_have_count(1)


def test_runner_set_next_request_null_stops_run_and_unknown_name_reports(ui, app, world):
    cid, _ = world
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [req("a", "Alpha", events=[ev("test", "pm.execution.setNextRequest(null)")]), req("b", "Beta")]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    run_collection_ui(ui)
    assert names(ui) == ["Alpha"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"][0]["event"] = [ev("test", "pm.execution.setNextRequest('Yo\\'q')")]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    run_collection_ui(ui)
    assert names(ui) == ["Alpha"]
    T(ui, "console-btn").click()
    expect(T(ui, "console-text").filter(has_text="topilmadi")).to_have_count(1)


def test_runner_iterations_with_data_rows_reach_scripts(ui, app, world, tmp_path):
    cid, _ = world
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [req("a", "Alpha", "{{base}}/echo?id={{id}}", [ev("test", "pm.test('row data', () => pm.expect(pm.response.json().args.id[0]).to.equal(pm.iterationData.get('id')));\nconsole.log('iter ' + pm.info.iteration + '/' + pm.info.iterationCount + ' id=' + pm.iterationData.get('id'))")])]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='Col']").click(button="right")
    ui.click("[data-act=runner]")
    f = tmp_path / "d.csv"
    f.write_text("id\n7\n8\n9\n")
    T(ui, "runner-file").set_input_files(str(f))
    T(ui, "runner-run").click()
    expect(T(ui, "runner-row")).to_have_count(3, timeout=20000)
    T(ui, "console-btn").click()
    texts = T(ui, "console-text").all_inner_texts()
    assert [t for t in texts if t.startswith("iter ")] == ["iter 0/3 id=7", "iter 1/3 id=8", "iter 2/3 id=9"]


# ── Batch ──
def test_batch_rows_run_scripts_and_show_test_badges(ui, tmp_path):
    open_req(ui, "Alpha")
    ui.fill("[data-testid=url]", "{{base}}/echo?id={{id}}")
    script_section(ui)
    write(ui, "test", "pm.test('id echoed', () => pm.expect(pm.response.json().args.id[0]).to.equal(pm.iterationData.get('id')));\npm.test('always fails', () => pm.expect(0).to.equal(1));")
    ui.click("[data-section=batch]")
    f = tmp_path / "d.csv"
    f.write_text("id\n1\n2\n3\n")
    T(ui, "batch-file").set_input_files(str(f))
    T(ui, "batch-concurrency").fill("3")
    T(ui, "batch-run").click()
    expect(T(ui, "batch-status")).to_contain_text("Bajarildi")
    badges = T(ui, "result-tests")
    expect(badges).to_have_count(3)
    expect(badges.first).to_contain_text("tests 1/2")
    expect(badges.first).to_have_class(re.compile("badge-err"))
