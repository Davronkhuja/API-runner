"""UI audit tuzatishlari (v2.4.0): Import dialogi, muhit quick-look, muharrirlar (qator raqami/xato/qidiruv), javob Headers, Sozlamalar avtosaqlash, resizer hover, Tarix komponenti, nom tozalash."""
import json
import re
import time

import pytest
from playwright.sync_api import expect

from conftest import E2E_TOKEN, set_body_mode

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
PM = {"info": {"name": "Import sinov", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
      "item": [{"name": "Papka", "item": [{"name": "A", "request": {"method": "GET", "url": {"raw": "http://x/a"}}}, {"name": "B", "request": {"method": "POST", "url": {"raw": "http://x/b"}}}]}, {"name": "C", "request": {"method": "GET", "url": {"raw": "http://x/c"}}}]}


@pytest.fixture
def ui(app, page, echo_server):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.echo = echo_server
    return page


def new_post(p, path="/echo"):
    T(p, "new-tab").click()
    p.select_option("[data-testid=method]", "POST")
    p.fill("[data-testid=url]", p.echo + path)


# ── Import dialogi ──
def test_import_paste_postman_json_shows_preview_then_imports(ui, app):
    T(ui, "import-btn").click()
    ui.click("[data-tab=text]")
    T(ui, "import-text").fill(json.dumps(PM))
    T(ui, "import-add-text").click()
    expect(T(ui, "import-preview")).to_contain_text("1 papka, 3 so'rov")                        # oldindan ko'rish
    expect(T(ui, "import-total")).to_contain_text("1")
    T(ui, "import-confirm").click()
    expect(T(ui, "import-dialog")).to_have_count(0)
    names = [c["name"] for c in app.api("GET", "/api/workspace")["collections"]]
    assert "Import sinov" in names


def test_import_file_drop_target_and_input_and_invalid_text_error(ui, tmp_path):
    f = tmp_path / "pm.json"
    f.write_text(json.dumps(PM))
    T(ui, "import-btn").click()
    expect(T(ui, "import-drop")).to_be_visible()
    T(ui, "import-dlg-file").set_input_files(str(f))
    expect(T(ui, "import-preview")).to_contain_text("3 so'rov")
    ui.click("[data-tab=text]")
    T(ui, "import-text").fill("bu JSON ham emas, cURL ham emas")
    T(ui, "import-add-text").click()
    expect(T(ui, "import-error")).to_be_visible()
    expect(T(ui, "import-confirm")).to_be_enabled()                                            # yaroqli manba bor — import mumkin


def test_import_curl_text_opens_a_request_tab_and_url_import_works(ui, app):
    T(ui, "import-btn").click()
    ui.click("[data-tab=text]")
    T(ui, "import-text").fill("curl -X POST 'https://api.example.test/v1/x' -H 'X-A: 1' -d '{\"a\":1}'")
    T(ui, "import-add-text").click()
    expect(T(ui, "import-preview")).to_contain_text("cURL")
    T(ui, "import-confirm").click()
    expect(T(ui, "url")).to_have_text("https://api.example.test/v1/x")
    expect(T(ui, "method")).to_have_value("POST")
    T(ui, "import-btn").click()
    ui.click("[data-tab=url]")
    T(ui, "import-url").fill(ui.echo + "/postman.json")
    T(ui, "import-add-url").click()
    expect(T(ui, "import-preview")).to_contain_text("1 papka, 2 so'rov")
    T(ui, "import-confirm").click()
    expect(ui.locator("[data-name='Uzoqdagi collection']")).to_be_visible()


# ── Muhit quick-look ──
def test_env_eye_opens_popover_with_env_and_globals_and_edits_in_place(ui, app):
    eid = app.api("POST", "/api/environments", {"name": "Dev"})["id"]
    e = app.api("GET", f"/api/environments/{eid}")
    e["values"] = [{"key": "host", "value": "h.io", "enabled": True, "type": "default"}, {"key": "tok", "value": "T0", "enabled": True, "type": "secret"}]
    app.api("PUT", f"/api/environments/{eid}", e)
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    app.api("PUT", "/api/globals", {**app.api("GET", "/api/globals"), "values": [{"key": "g1", "value": "GV", "enabled": True, "type": "default"}]})
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    T(ui, "env-vars-btn").click()
    q = T(ui, "env-quicklook")
    expect(q).to_be_visible()
    expect(q).to_contain_text("Faol muhit — Dev")
    expect(q.locator("[data-testid=ql-env] [data-testid=ql-row]")).to_have_count(2)
    expect(q.locator("[data-testid=ql-globals] [data-testid=ql-row]")).to_have_count(1)
    assert q.locator("[data-testid=ql-env] input").nth(1).get_attribute("type") == "password"       # secret maskalangan
    cur = q.locator("[data-testid=ql-env] [data-testid=ql-cur]").first
    cur.fill("new.host")
    cur.press("Enter")
    end = time.time() + 5
    while time.time() < end and app.api("GET", f"/api/environments/{eid}")["values"][0].get("current") != "new.host":
        time.sleep(0.1)
    v = app.api("GET", f"/api/environments/{eid}")["values"][0]
    assert v["current"] == "new.host" and v["value"] == "h.io"                                      # joriy o'zgardi, boshlang'ich tegilmadi
    ui.keyboard.press("Escape")
    expect(q).to_have_count(0)


# ── Muharrirlar ──
def test_body_editor_has_line_numbers_fold_gutter_and_json_error_is_marked(ui):
    new_post(ui)
    ui.click("[data-section=body]")
    ui.locator("[data-testid=body-raw]").click()
    ui.keyboard.insert_text('{\n  "a": 1,\n  "b": [1, 2]\n  "c": 3\n}')                           # 3-qatordan keyin vergul yo'q
    expect(ui.locator(".body-editor .cm-lineNumbers")).to_be_visible()
    expect(ui.locator(".body-editor .cm-foldGutter")).to_be_visible()
    expect(ui.locator(".body-editor .cm-lintRange-error").first).to_be_visible(timeout=5000)      # xato joyi belgilangan
    T(ui, "beautify").click()
    expect(ui.locator(".toast")).to_contain_text("4-qator")                                        # Beautify xabarida qator raqami


def test_json_variables_are_not_flagged_as_errors(ui):
    new_post(ui)
    ui.click("[data-section=body]")
    ui.locator("[data-testid=body-raw]").click()
    ui.keyboard.insert_text('{"id": {{id}}, "name": "{{name}}"}')
    ui.wait_for_timeout(700)
    expect(ui.locator(".body-editor .cm-lintRange-error")).to_have_count(0)


def test_editor_search_panel_opens_with_ctrl_f(ui):
    new_post(ui)
    ui.click("[data-section=body]")
    ui.locator("[data-testid=body-raw]").click()
    ui.keyboard.insert_text('{"needle": 1}')
    ui.keyboard.press("ControlOrMeta+f")
    expect(ui.locator(".body-editor .cm-search")).to_be_visible()


def test_scripts_snippet_goes_to_cursor_position_and_snippets_panel_is_readable(ui):
    T(ui, "new-tab").click()
    ui.click("[data-section=scripts]")
    T(ui, "script-pre").click()
    ui.keyboard.type("// bosh\n")
    T(ui, "snippet").first.click()
    expect(T(ui, "script-pre")).to_contain_text("// bosh")
    assert len(T(ui, "script-pre").inner_text()) > len("// bosh") + 5                              # snippet qo'shildi
    w = ui.locator("[data-testid=snippets]").bounding_box()["width"]
    assert 215 <= w <= 262
    fs = ui.evaluate("parseFloat(getComputedStyle(document.querySelector('[data-testid=snippet]')).fontSize)")
    assert fs >= 13


# ── Javob paneli ──
def test_response_headers_tab_search_copy_fixed_key_column_and_wrapping(ui):
    T(ui, "new-tab").click()
    ui.fill("[data-testid=url]", ui.echo + "/echo?z=1")
    with ui.expect_response(lambda r: r.url.endswith("/run_one")):
        T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("200")
    T(ui, "rp-headers-tab").click()
    n = T(ui, "rp-header-row").count()
    assert n >= 3
    T(ui, "rp-headers-search").fill("content-type")
    expect(T(ui, "rp-header-row")).to_have_count(1)
    T(ui, "rp-headers-search").fill("")
    widths = {round(c.bounding_box()["width"]) for c in ui.locator("[data-testid=rp-header-row] td.hk").all()}
    assert len(widths) == 1                                                                         # kalit ustuni o'zgarmas kenglikda
    ui.context.grant_permissions(["clipboard-read", "clipboard-write"])
    T(ui, "rp-header-copy").first.click()
    expect(ui.locator(".toast")).to_contain_text("nusxalandi")
    T(ui, "rp-headers-copy-all").click()
    expect(ui.locator(".toast")).to_contain_text(f"{n} ta header")
    assert ui.evaluate("getComputedStyle(document.querySelector('[data-testid=rp-header-row] td.hv')).overflowWrap") in ("anywhere", "break-word")


def test_response_tabs_keep_the_toolbar_row_so_content_does_not_jump(ui):
    T(ui, "new-tab").click()
    ui.fill("[data-testid=url]", ui.echo + "/echo?z=1")
    with ui.expect_response(lambda r: r.url.endswith("/run_one")):
        T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("200")
    ys = {}
    for tab, tools in (("rp-body-tab", ".rp-tools"), ("rp-headers-tab", "[data-testid=rp-headers-tools]"), ("rp-cookies-tab", "[data-testid=rp-cookies-tools]"), ("rp-tests-tab", "[data-testid=rp-tests-tools]")):
        T(ui, tab).click()
        b = ui.locator(tools).first.bounding_box()
        ys[tab] = (round(b["y"]), round(b["height"]))
    assert len({v for v in ys.values()}) == 1, ys                                                   # bir xil joy va balandlik
    T(ui, "rp-headers-tab").click()
    expect(ui.locator("[data-mode=pretty]")).to_have_count(0)                                       # Pretty/Raw/Preview faqat Body'da


# ── Sozlamalar ──
def test_settings_autosave_left_nav_and_narrow_text_column(ui, app):
    T(ui, "settings-btn").click()
    expect(T(ui, "settings-nav")).to_be_visible()
    assert [b.strip() for b in ui.locator("[data-testid=settings-nav] button").all_inner_texts()] == ["Ko'rinish", "So'rov", "Skriptlar", "Fayllar", "Ma'lumotlar", "Import / Eksport", "Zaxiralar"]
    assert ui.locator(".settings-main").bounding_box()["width"] <= 722
    ui.select_option("[data-testid=gset-follow_redirects]", "false")
    expect(T(ui, "gset-saved")).to_contain_text("Saqlandi")
    assert app.api("GET", "/api/workspace")["meta"]["settings"] == {"follow_redirects": False}
    assert ui.locator("button", has_text=re.compile(r"^Saqlash$")).count() == 0                     # alohida "Saqlash" tugmalari yo'q
    ui.click("[data-nav=s-backups]")
    expect(ui.locator("#s-backups")).to_be_in_viewport()


# ── Resizer ──
def test_resizer_line_gets_thicker_and_accent_on_hover(ui):
    new_post(ui)
    line = "getComputedStyle(document.querySelector('[data-testid=resp-resizer]'), '::before')"
    base = ui.evaluate(f"[{line}.height, {line}.backgroundColor]")
    ui.locator("[data-testid=resp-resizer]").hover(position={"x": 60, "y": 5})
    ui.wait_for_timeout(250)                                                                        # transition tugashi
    hov = ui.evaluate(f"[{line}.height, {line}.backgroundColor]")
    assert float(base[0][:-2]) == 2 and float(hov[0][:-2]) == 3 and hov[1] != base[1]
    assert ui.locator("[data-testid=resp-resizer]").bounding_box()["height"] >= 10


# ── Tarix: bitta komponent ──
def test_sidebar_history_uses_the_shared_list_with_status_host_path_and_grouping(ui, app):
    db = app.flask.extensions["db"]
    now = time.time()
    for i in range(3):
        db.add_history("request", {"method": "GET", "url": "https://api.online-mahalla.uz/api/v1/gcp/pinfl", "headers": [], "params": [{"name": "p", "value": "1"}], "status": 200, "time": 0.1, "size": 10}, ts=now - i)
    db.add_history("request", {"method": "POST", "url": "https://api.online-mahalla.uz/api/v1/x", "headers": [], "params": [], "status": 500, "time": 0.1, "size": 10}, ts=now - 100)
    T(ui, "sb-history").click()
    expect(T(ui, "history-row").first).to_be_visible()
    expect(T(ui, "sh-day").first).to_have_text(re.compile("Bugun", re.I))
    row = T(ui, "history-row").filter(has_text="/api/v1/gcp/pinfl").first
    expect(row.locator("[data-testid=sh-host]")).to_contain_text("api.online-mahalla.uz")
    expect(row.locator("[data-testid=sh-path]")).to_have_text("/api/v1/gcp/pinfl?p=1")
    expect(row.locator("[data-testid=sh-status]")).to_have_text("200")
    expect(T(ui, "sh-repeat")).to_have_text("×3")
    T(ui, "history-row").filter(has_text="/api/v1/x").first.click()
    expect(T(ui, "url")).to_have_text("https://api.online-mahalla.uz/api/v1/x")


# ── Nomlarni tozalash ──
def test_url_named_requests_get_a_one_time_cleanup_offer_with_preview_and_backup(app, page):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "u1", "name": "https://api.online-mahalla.uz/api/v1/hm/projects?x=1", "request": {"method": "GET", "header": [], "url": {"raw": "http://h/a"}}, "response": []},
                   {"id": "u2", "name": "{{base}}/v1/other", "request": {"method": "GET", "header": [], "url": {"raw": "http://h/b"}}, "response": []},
                   {"id": "ok", "name": "Oddiy nom", "request": {"method": "GET", "header": [], "url": {"raw": "http://h/c"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    expect(T(page, "nameclean-offer")).to_contain_text("2 ta so'rov nomi")
    T(page, "nameclean-open").click()
    rows = T(page, "nameclean-row")
    expect(rows).to_have_count(2)
    expect(rows.first).to_contain_text("api/v1/hm/projects")
    before = len(app.api("GET", "/api/backups"))
    T(page, "nameclean-apply").click()
    expect(T(page, "nameclean-dialog")).to_have_count(0)
    names = {i["id"]: i["name"] for i in app.api("GET", f"/api/collections/{cid}")["item"]}
    assert names == {"u1": "api/v1/hm/projects", "u2": "v1/other", "ok": "Oddiy nom"}
    assert len(app.api("GET", "/api/backups")) > before                                              # zaxira olindi
    expect(T(page, "nameclean-offer")).to_have_count(0)
