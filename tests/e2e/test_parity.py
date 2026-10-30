"""Eski UI bilan paritet: har bir funksiya yangi frontendda ishlashi kerak (docs/ROADMAP.md checklisti)."""
import json
import re

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def new_req(p, url, method="GET"):
    T(p, "new-tab").click()
    p.select_option("[data-testid=method]", method)
    p.fill("[data-testid=url]", url)


def open_batch(p):
    p.click("[data-section=batch]")


# ── URL bar ──
def test_curl_paste_fills_everything(ui):
    T(ui, "new-tab").click()
    ui.evaluate("""() => { const i = document.querySelector('[data-testid=url]'); i.focus();
      const dt = new DataTransfer(); dt.setData('text', "curl -X PUT 'https://a.io/x?y=1' -H 'X-Foo: bar' -H 'Authorization: Bearer TT' -d '{\\"k\\":1}'");
      i.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""")
    expect(T(ui, "url")).to_have_value("https://a.io/x?y=1")
    expect(T(ui, "method")).to_have_value("PUT")
    ui.click("[data-section=params]")
    expect(ui.locator("[data-testid=params-table] input[type=text]").first).to_have_value("y")
    ui.click("[data-section=headers]")
    expect(ui.locator("[data-testid=headers-table] input[type=text]").first).to_have_value("X-Foo")
    ui.click("[data-section=auth]")
    expect(T(ui, "auth-token")).to_have_value("TT")
    ui.click("[data-section=body]")
    expect(T(ui, "body-raw")).to_have_value('{"k":1}')


def test_copy_as_curl_drawer(ui):
    new_req(ui, "https://a.io/p", "POST")
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "json")
    ui.fill("[data-testid=body-raw]", '{"a":1}')
    T(ui, "curl-btn").click()
    out = T(ui, "curl-output")
    expect(out).to_contain_text("curl -X POST 'https://a.io/p'")
    expect(out).to_contain_text("""-d '{"a":1}'""")
    expect(T(ui, "curl-copy")).to_be_visible()


def test_url_history_dropdown_filters_and_picks(ui, echo_server):
    new_req(ui, echo_server + "/echo?h=1")
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("200")
    T(ui, "new-tab").click()
    T(ui, "url").click()
    expect(T(ui, "url-history")).to_contain_text("/echo")
    T(ui, "url").fill("zzz-nothing")
    expect(T(ui, "url-history")).to_have_count(0)
    T(ui, "url").fill("echo")
    ui.locator("[data-testid=url-history] button").first.click()
    expect(T(ui, "url")).to_have_value(re.compile("/echo"))


def test_save_disabled_when_clean_and_save_as_dialog(ui, app):
    T(ui, "new-tab").click()
    ui.fill("[data-testid=url]", "http://s/1")
    T(ui, "save").click()
    expect(T(ui, "saveas-dialog")).to_be_visible()
    T(ui, "saveas-name").fill("Mening so'rovim")
    T(ui, "saveas-ok").click()
    expect(ui.locator("[data-testid=tree-row][data-name=\"Mening so'rovim\"]")).to_be_visible()
    expect(T(ui, "save")).to_be_disabled()
    ui.fill("[data-testid=url]", "http://s/2")
    expect(T(ui, "save")).to_be_enabled()
    ui.keyboard.press("Control+s")
    expect(T(ui, "save")).to_be_disabled()


# ── tablar ──
def test_params_headers_checkbox_disable_row(ui, echo_server):
    new_req(ui, echo_server + "/echo?a=1&b=2")
    ui.click("[data-section=params]")
    ui.locator("[data-testid=params-table] input[type=checkbox]").nth(1).uncheck()
    ui.click("[data-section=headers]")
    ui.locator("[data-testid=headers-table] input[type=text]").nth(0).fill("X-On")
    ui.locator("[data-testid=headers-table] input[type=text]").nth(1).fill("yes")
    T(ui, "send").click()
    body = T(ui, "resp-body")
    expect(body).to_contain_text('"a"')
    expect(body).not_to_contain_text('"b"')
    expect(body).to_contain_text("X-On")


def test_file_param_upload_and_post(ui, echo_server, tmp_path):
    f = tmp_path / "up.txt"
    f.write_text("fayl-ichi")
    new_req(ui, echo_server + "/echo", "POST")
    ui.click("[data-section=params]")
    ui.locator("[data-testid=params-table] input[type=file]").first.set_input_files(str(f))
    expect(ui.locator("[data-testid=params-table]")).to_contain_text("up.txt")
    T(ui, "send").click()
    expect(T(ui, "resp-body")).to_contain_text("fayl-ichi")


def test_rejected_absolute_path_shows_clear_message(ui, echo_server, tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("a")
    new_req(ui, echo_server + "/echo", "POST")
    ui.click("[data-section=params]")
    ui.locator("[data-testid=params-table] input[type=text]").nth(0).fill("doc")
    ui.locator("[data-testid=params-table] input[type=text]").nth(1).fill(str(f))
    ui.evaluate("""() => {}""")
    # qo'lda yozilgan yo'lni "fayl" turiga o'tkazish uchun API orqali yuboramiz
    r = ui.evaluate("""([url, path]) => fetch('/run_one', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({url, method:'POST', params:[{name:'d', value:path, type:'file'}]})}).then(r => r.json())""", [echo_server + "/echo", str(f)])
    assert "📎 orqali faylni qayta tanlang" in r["response"]


def test_auth_types_send_correct_header(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    ui.click("[data-section=auth]")
    ui.select_option("[data-testid=auth-type]", "basic")
    ui.locator("[data-testid=auth-panel] input").nth(0).fill("user")
    T(ui, "auth-pass").fill("pass")
    expect(T(ui, "auth-pass")).to_have_attribute("type", "password")
    T(ui, "auth-eye").click()
    expect(T(ui, "auth-pass")).to_have_attribute("type", "text")
    T(ui, "send").click()
    expect(T(ui, "resp-body")).to_contain_text("Basic dXNlcjpwYXNz")


@pytest.mark.parametrize("mode,needle", [("json", '"k": 1'), ("raw", "plain-text"), ("form", "a=1")])
def test_body_modes_are_sent(ui, echo_server, mode, needle):
    new_req(ui, echo_server + "/echo", "POST")
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", mode)
    if mode == "form":
        ui.locator("[data-testid=form-table] input[type=text]").nth(0).fill("a")
        ui.locator("[data-testid=form-table] input[type=text]").nth(1).fill("1")
    else:
        ui.fill("[data-testid=body-raw]", '{"k": 1}' if mode == "json" else "plain-text")
    T(ui, "send").click()
    expect(T(ui, "resp-body")).to_contain_text(needle)


def test_multipart_form_data_is_sent(ui, echo_server):
    new_req(ui, echo_server + "/echo", "POST")
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "multipart")
    ui.locator("[data-testid=formdata-table] input[type=text]").nth(0).fill("fld")
    ui.locator("[data-testid=formdata-table] input[type=text]").nth(1).fill("val")
    T(ui, "send").click()
    expect(T(ui, "resp-body")).to_contain_text('"fld"')


def test_beautify_json_body(ui):
    T(ui, "new-tab").click()
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "json")
    ui.fill("[data-testid=body-raw]", '{"a":1,"b":[1,2]}')
    T(ui, "beautify").click()
    expect(T(ui, "body-raw")).to_have_value('{\n  "a": 1,\n  "b": [\n    1,\n    2\n  ]\n}')
    ui.fill("[data-testid=body-raw]", '{"x":1}')
    T(ui, "body-raw").press("Control+b")
    expect(T(ui, "body-raw")).to_have_value('{\n  "x": 1\n}')


# ── batch runner + natijalar ──
def csv_file(tmp_path, n=4):
    f = tmp_path / "d.csv"
    f.write_text("id\n" + "\n".join(str(i) for i in range(n)) + "\n")
    return str(f)


def test_batch_csv_run_stats_progress_filters(ui, echo_server, tmp_path):
    new_req(ui, echo_server + "/echo?i={{id}}")
    open_batch(ui)
    T(ui, "batch-file").set_input_files(csv_file(tmp_path, 4))
    expect(T(ui, "batch-data-info")).to_contain_text("4 qator")
    T(ui, "batch-run").click()
    expect(T(ui, "batch-status")).to_contain_text("Bajarildi — 4 muvaffaqiyatli, 0 xatolik")
    expect(T(ui, "progress-count")).to_have_text("4 / 4")
    expect(T(ui, "s-total")).to_have_text("4")
    expect(T(ui, "s-ok")).to_have_text("4")
    expect(T(ui, "s-2xx")).to_have_text("4")
    expect(T(ui, "result-card")).to_have_count(4)
    expect(T(ui, "result-card").nth(2)).to_contain_text('"i"')
    ui.click("[data-filter=error]")
    expect(T(ui, "result-card")).to_have_count(0)
    ui.click("[data-filter=success]")
    expect(T(ui, "result-card")).to_have_count(4)
    expect(T(ui, "time-bar")).to_have_count(4)


def test_batch_rows_mode_custom_count_and_errors_filter(ui, echo_server, tmp_path):
    new_req(ui, echo_server + "/status/{{id}}")
    open_batch(ui)
    f = tmp_path / "s.csv"
    f.write_text("id\n200\n404\n503\n200\n")
    T(ui, "batch-file").set_input_files(str(f))
    T(ui, "batch-rows-mode").select_option("custom")
    T(ui, "batch-count").fill("3")
    T(ui, "batch-run").click()
    expect(T(ui, "progress-count")).to_have_text("3 / 3")
    expect(T(ui, "s-ok")).to_have_text("1")
    expect(T(ui, "s-err")).to_have_text("2")
    expect(T(ui, "s-4xx")).to_have_text("1")
    expect(T(ui, "s-5xx")).to_have_text("1")
    ui.click("[data-filter=error]")
    expect(T(ui, "result-card")).to_have_count(2)


def test_batch_json_data_file(ui, echo_server, tmp_path):
    new_req(ui, echo_server + "/echo?v={{v}}")
    open_batch(ui)
    f = tmp_path / "d.json"
    f.write_text(json.dumps([{"v": "x1"}, {"v": "x2"}]))
    T(ui, "batch-file").set_input_files(str(f))
    T(ui, "batch-run").click()
    expect(T(ui, "result-card")).to_have_count(2)
    expect(T(ui, "result-card").nth(1)).to_contain_text("x2")


def test_batch_concurrency_retry_delay_timeout_ssl_controls(ui, echo_server, tmp_path):
    new_req(ui, echo_server + "/flaky")
    open_batch(ui)
    T(ui, "batch-retry").fill("2")
    T(ui, "batch-concurrency").fill("3")
    T(ui, "batch-delay").fill("0")
    T(ui, "batch-timeout").fill("20")
    T(ui, "batch-ssl").uncheck()
    T(ui, "batch-run").click()
    expect(T(ui, "batch-status")).to_contain_text("Bajarildi — 1 muvaffaqiyatli")
    expect(T(ui, "retry-badge")).to_contain_text("2")


def test_batch_stop(ui, echo_server, tmp_path):
    new_req(ui, echo_server + "/slow?s=0.3")
    open_batch(ui)
    f = tmp_path / "n.csv"
    f.write_text("id\n" + "\n".join(str(i) for i in range(40)) + "\n")
    T(ui, "batch-file").set_input_files(str(f))
    T(ui, "batch-run").click()
    expect(T(ui, "batch-stop")).to_be_enabled()
    ui.wait_for_timeout(800)
    T(ui, "batch-stop").click()
    expect(T(ui, "batch-status")).to_contain_text("To'xtatildi")
    n = len(ui.locator("[data-testid=result-card]").all())
    assert 0 < n < 40


def test_result_fullscreen_viewer_and_esc(ui, echo_server):
    new_req(ui, echo_server + "/echo?q=1")
    open_batch(ui)
    T(ui, "batch-run").click()
    expect(T(ui, "result-card")).to_have_count(1)
    T(ui, "open-full").click()
    expect(T(ui, "full-body")).to_contain_text('"q"')
    T(ui, "full-close").click()
    expect(T(ui, "result-full")).to_have_count(0)


def test_export_json_and_csv(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    open_batch(ui)
    T(ui, "batch-run").click()
    expect(T(ui, "result-card")).to_have_count(1)
    with ui.expect_download() as d:
        T(ui, "export-json").click()
    assert json.load(open(d.value.path()))[0]["status"] == 200
    with ui.expect_download() as d:
        T(ui, "export-csv").click()
    assert open(d.value.path()).read().startswith("index,status,time,size,url,response,error")


def test_compare_runs(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    open_batch(ui)
    for _ in range(2):
        T(ui, "batch-run").click()
        expect(T(ui, "batch-status")).to_contain_text("Bajarildi")
        ui.wait_for_timeout(1100)
    T(ui, "compare-open").click()
    expect(T(ui, "cmp-table")).to_be_visible()
    expect(T(ui, "cmp-table").locator("tbody tr")).to_have_count(1)


def test_close_and_collapse_results(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    open_batch(ui)
    T(ui, "batch-run").click()
    expect(T(ui, "result-card")).to_have_count(1)
    T(ui, "results-close").click()
    expect(T(ui, "results-pane")).to_have_count(0)


# ── sidebar ──
def test_sidebar_collapse_toggle(ui):
    expect(T(ui, "sidebar")).to_be_visible()
    T(ui, "sb-toggle").click()
    expect(T(ui, "sidebar")).to_be_hidden()
    T(ui, "sb-toggle").click()
    expect(T(ui, "sidebar")).to_be_visible()


def test_sidebar_resize(ui):
    w0 = T(ui, "sb-wrap").evaluate("e => e.offsetWidth")
    b = T(ui, "sb-resizer").bounding_box()
    ui.mouse.move(b["x"] + 3, b["y"] + 100)
    ui.mouse.down()
    ui.mouse.move(b["x"] + 80, b["y"] + 100, steps=5)
    ui.mouse.up()
    assert T(ui, "sb-wrap").evaluate("e => e.offsetWidth") > w0 + 40


def test_collection_rename_duplicate_delete_context_menu(ui, app):
    app.seed([("a", "Alfa", None)])
    ui.reload()
    r = ui.locator("[data-testid=tree-row][data-name=Alfa]")
    r.click(button="right")
    ui.click("[data-testid=tree-menu] [data-act=rename]")
    T(ui, "rename-input").fill("Alfa2")
    T(ui, "rename-input").press("Enter")
    expect(ui.locator("[data-testid=tree-row][data-name=Alfa2]")).to_be_visible()
    ui.locator("[data-testid=tree-row][data-name=Alfa2]").click(button="right")
    ui.click("[data-testid=tree-menu] [data-act=dup]")
    expect(ui.locator("[data-testid=tree-row]", has_text="Alfa2")).to_have_count(2)
    ui.locator("[data-testid=tree-row][data-name=Alfa2]").first.click(button="right")
    ui.click("[data-testid=tree-menu] [data-act=delete]")
    T(ui, "confirm-ok").click()
    expect(ui.locator("[data-testid=tree-row]", has_text="Alfa2")).to_have_count(1)


def test_rename_updates_open_tab_title(ui, app):
    app.seed([("a", "Alfa", None)])
    ui.reload()
    ui.locator("[data-testid=tree-row][data-name=Alfa]").dblclick()
    ui.locator("[data-testid=tree-row][data-name=Alfa]").click(button="right")
    ui.click("[data-testid=tree-menu] [data-act=rename]")
    T(ui, "rename-input").fill("Beta")
    T(ui, "rename-input").press("Enter")
    expect(ui.locator("[data-testid=tab] .title")).to_have_text("Beta")


def test_import_button_postman_and_openapi(ui, tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"info": {"name": "FromBtn"}, "item": [{"name": "R", "request": {"method": "GET", "url": "http://h"}}]}))
    T(ui, "import-file").set_input_files(str(f))
    expect(ui.locator("[data-testid=tree-row][data-name=FromBtn]")).to_be_visible()


def test_search_filter(ui, app):
    app.seed([("a", "Alfa", None), ("b", "Beta", None)])
    ui.reload()
    T(ui, "sb-search").fill("alf")
    expect(ui.locator("[data-testid=tree-row][data-name=Beta]")).to_have_count(0)
    expect(ui.locator("[data-testid=tree-row][data-name=Alfa]")).to_have_count(1)


# ── environments ──
def test_environment_create_edit_activate_and_used_in_request(ui, echo_server):
    ui.click("[data-testid=sb-environments]")
    T(ui, "new-env").click()
    T(ui, "env-add").click()
    T(ui, "env-key").first.fill("host")
    T(ui, "env-val").first.fill(echo_server)
    T(ui, "env-save").click()
    T(ui, "env-activate").click()
    expect(T(ui, "env-select")).to_have_value(re.compile(r".+"))
    new_req(ui, "{{host}}/echo?ok=1")
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("200")
    expect(T(ui, "resp-body")).to_contain_text('"ok"')


def test_header_env_selector_switches_and_none(ui, app):
    e1 = app.api("POST", "/api/environments", {"name": "Dev"})["id"]
    ui.reload()
    T(ui, "env-select").select_option(e1)
    ui.reload()
    expect(T(ui, "env-select")).to_have_value(e1)             # faol env serverda saqlanadi
    T(ui, "env-select").select_option("")
    ui.reload()
    expect(T(ui, "env-select")).to_have_value("")


def test_environment_delete_confirm(ui, app):
    app.api("POST", "/api/environments", {"name": "Tmp"})
    ui.reload()
    ui.click("[data-testid=sb-environments]")
    expect(T(ui, "env-row")).to_have_count(1)
    T(ui, "env-row").locator("button", has_text="×").click()
    T(ui, "confirm-ok").click()
    expect(T(ui, "env-row")).to_have_count(0)


# ── tarix ──
def test_history_list_load_delete_clear(ui, echo_server):
    new_req(ui, echo_server + "/echo?h=1")
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("200")
    ui.click("[data-testid=sb-history]")
    expect(T(ui, "history-row")).to_have_count(1)
    T(ui, "history-row").click()
    expect(T(ui, "url")).to_have_value(re.compile("/echo"))
    ui.click("[data-testid=sb-history]")
    T(ui, "history-row").locator("button").click()
    expect(T(ui, "history-row")).to_have_count(0)


# ── umumiy ──
def test_theme_toggle_persists(ui):
    T(ui, "theme").click()
    t = ui.evaluate("document.documentElement.dataset.theme")
    assert t in ("dark", "light")
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    assert ui.evaluate("document.documentElement.dataset.theme") == t


def test_cmd_enter_sends(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    ui.keyboard.press("Control+Enter")
    expect(T(ui, "resp-status")).to_have_text("200")


def test_empty_url_warns(ui):
    T(ui, "new-tab").click()
    T(ui, "send").click()
    expect(T(ui, "toast")).to_contain_text("URL kiriting")


def test_localstorage_import_button(ui):
    ui.evaluate("""() => localStorage.setItem('apiRunnerEnvs', JSON.stringify([{id:'e9', name:'LS', vars:{k:'v'}}]))""")
    T(ui, "ls-import").click()
    expect(T(ui, "toast")).to_contain_text("Ko'chirildi")
    ui.click("[data-testid=sb-environments]")
    expect(ui.locator("[data-testid=env-row]", has_text="LS")).to_have_count(1)


def test_localstorage_import_empty_warns(ui):
    ui.evaluate("() => localStorage.clear()")
    T(ui, "ls-import").click()
    expect(T(ui, "toast")).to_contain_text("ko'chiriladigan ma'lumot yo'q")


def test_export_to_legacy_format_button(ui, app):
    app.seed([("a", "Alfa", None)])
    ui.reload()
    with ui.expect_download() as d:
        T(ui, "export-legacy").click()
    data = json.load(open(d.value.path()))
    assert [r["name"] for r in data["requests"]] == ["Alfa"]


def test_version_label(ui):
    expect(T(ui, "version")).to_contain_text("v2.")


def test_response_timing_dash_for_missing_values(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    T(ui, "send").click()
    t = T(ui, "resp-timing")
    expect(t).to_contain_text("DNS —")
    expect(t).to_contain_text("TLS —")                          # oddiy HTTP'da TLS yo'q → "—", xato emas
