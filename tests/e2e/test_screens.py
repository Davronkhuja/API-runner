"""C guruhi: yangi ekranlar (Folder Overview, Env Initial/Current, Tarix + diff, joylashuv/zich rejim, Body segmentlari, Batch grid)."""
import re
import time

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


def bearer(tok):
    return {"type": "bearer", "bearer": [{"key": "token", "value": tok, "type": "string"}]}


def req(iid, name, method, url, auth=None):
    r = {"method": method, "header": [], "url": {"raw": url}}
    if auth:
        r["auth"] = auth
    return {"id": iid, "name": name, "request": r, "response": []}


@pytest.fixture
def world(app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["auth"] = bearer("COLTOK")
    col["variable"] = [{"key": "host", "value": echo_server}]
    col["item"] = [{"id": "f1", "name": "Fold", "auth": bearer("FOLDTOK"), "variable": [{"key": "a", "value": "1"}], "item": [
        req("r1", "InheritOne", "GET", "{{host}}/echo?n=1"),
        req("r2", "InheritTwo", "GET", "{{host}}/status/404"),
        req("r3", "OwnSame", "GET", "{{host}}/echo?n=3", auth=bearer("FOLDTOK")),
        req("r4", "OwnOther", "POST", "{{host}}/echo", auth=bearer("OTHER")),
        req("r5", "NoAuth", "GET", "{{host}}/echo", auth={"type": "noauth"})]}]
    app.api("PUT", f"/api/collections/{cid}", col)
    return cid


@pytest.fixture
def ui(app, page, world, echo_server):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.echo = echo_server
    return page


def open_folder(p, name="Fold"):
    p.locator(f"[data-name='{name}']").dblclick()
    expect(T(p, "tab-folder")).to_be_visible()


# ── Folder / Collection Overview ──
def test_folder_overview_table_shows_method_name_auth_source_status_and_time(ui):
    open_folder(ui)
    rows = T(ui, "ov-row")
    expect(rows).to_have_count(5)
    by = {r.locator(".ov-name").inner_text().strip().split("\n")[-1].replace("Fold / ", ""): r for r in rows.all()}
    assert "↑ Meros" in by["InheritOne"].locator("[data-testid=ov-row-auth]").inner_text()
    assert "Bearer Token (o'zi)" in by["OwnOther"].locator("[data-testid=ov-row-auth]").inner_text()
    assert "Auth yo'q" in by["NoAuth"].locator("[data-testid=ov-row-auth]").inner_text()
    expect(by["OwnOther"].locator(".m")).to_have_text("POST")
    expect(T(ui, "ov-row-status")).to_have_count(0)                                        # hali yuborilmagan
    ui.locator("[data-name='InheritOne']").dblclick()
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("200")
    ui.locator("[data-name='Fold']").dblclick()
    expect(T(ui, "ov-row-status")).to_have_text("200")
    expect(ui.locator("[data-testid=ov-row]", has_text="InheritOne").locator(".ov-time")).not_to_have_text("—")


def test_folder_overview_filter_and_row_opens_request(ui):
    open_folder(ui)
    T(ui, "ov-filter").fill("own")
    expect(T(ui, "ov-row")).to_have_count(2)
    T(ui, "ov-filter").fill("zzz")
    expect(T(ui, "ov-empty")).to_be_visible()
    T(ui, "ov-filter").fill("OwnOther")
    T(ui, "ov-row").click()
    expect(T(ui, "request-editor")).to_be_visible()
    expect(T(ui, "method")).to_have_value("POST")


def test_folder_overview_auth_inheritance_stats_and_same_token_offer(ui):
    open_folder(ui)
    expect(T(ui, "ov-inherit")).to_have_text("2 ta so'rov meros oladi")                      # NoAuth sanalmaydi
    expect(T(ui, "ov-own-auth")).to_contain_text("2 ta so'rovning o'z auth'i bor")
    expect(T(ui, "ov-same-token")).to_contain_text("1 ta so'rovda shu papkadagi bilan bir xil token")
    T(ui, "ov-to-inherit").click()
    expect(ui.locator("[role=dialog]").first).to_be_visible()                                # mavjud ommaviy "Meros" dialogi


def test_folder_overview_counts_variables_scripts_and_last_run_dots(ui):
    open_folder(ui)
    expect(T(ui, "ov-vars")).to_contain_text("1")
    expect(T(ui, "ov-scripts")).to_contain_text("yo'q")
    expect(T(ui, "ov-lr-none")).to_be_visible()
    T(ui, "scope-run-header").click()
    expect(T(ui, "runner-tab")).to_be_visible()
    for cb in ui.locator("[data-testid=runner-item] input[type=checkbox]").all():
        cb.check()
    T(ui, "runner-run").click()
    expect(T(ui, "runner-s-done")).to_contain_text("5 / 5")
    expect(T(ui, "runner-run")).to_be_enabled()
    ui.locator("[data-name='Fold']").dblclick()
    expect(T(ui, "ov-lr-ok")).to_have_text("4")                                                # 5 tadan 4 tasi o'tdi
    expect(T(ui, "ov-dots").locator(".dot")).to_have_count(5)
    expect(T(ui, "ov-dots").locator(".dot.err")).to_have_count(1)                              # faqat /status/404 xato


# ── Env: Initial / Current ──
@pytest.fixture
def env(app):
    eid = app.api("POST", "/api/environments", {"name": "Prod muhit", "kind": "prod"})["id"]
    e = app.api("GET", f"/api/environments/{eid}")
    e["values"] = [{"key": "tok", "value": "INITIAL", "enabled": True, "type": "secret"}, {"key": "host", "value": "h.io", "enabled": True, "type": "default"}]
    app.api("PUT", f"/api/environments/{eid}", e)
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    return eid


def open_env(p):
    T(p, "sb-environments").click()
    T(p, "env-row").first.dblclick()
    expect(T(p, "env-tab")).to_be_visible()


def test_env_initial_and_current_columns_current_is_used_and_initial_is_kept(app, env, ui):
    open_env(ui)
    heads = [t.strip() for t in ui.locator("[data-testid=env-table] thead th").all_inner_texts() if t.strip()]
    assert heads == ["O'zgaruvchi", "Turi", "Boshlang'ich qiymat", "Joriy qiymat"]
    expect(T(ui, "env-active-badge")).to_be_visible()
    T(ui, "env-cur").first.fill("CURRENT")
    T(ui, "env-save").click()
    row = app.api("GET", f"/api/environments/{env}")["values"][0]
    assert row["value"] == "INITIAL" and row["current"] == "CURRENT"                         # boshlang'ich tegilmadi
    ui.locator("[data-testid=new-tab]").click()
    ui.select_option("[data-testid=method]", "GET")
    ui.fill("[data-testid=url]", ui.echo + "/echo?t={{tok}}")
    T(ui, "send").click()
    expect(T(ui, "resp-body")).to_contain_text("CURRENT")                                     # so'rov joriy qiymatni ishlatadi
    expect(T(ui, "resp-body")).not_to_contain_text("INITIAL")


def test_env_secret_is_masked_and_can_be_revealed(app, env, ui):
    open_env(ui)
    first = T(ui, "env-val").first
    assert first.get_attribute("type") == "password"
    assert T(ui, "env-cur").first.get_attribute("type") == "password"
    T(ui, "env-reveal").first.click()
    assert first.get_attribute("type") == "text" and first.input_value() == "INITIAL"
    T(ui, "env-reveal").first.click()
    assert first.get_attribute("type") == "password"
    assert T(ui, "env-val").nth(1).get_attribute("type") == "text"                            # oddiy o'zgaruvchi maskalanmaydi


def test_env_current_to_initial_reset_duplicate_export_and_used_by(app, env, ui, tmp_path):
    open_env(ui)
    T(ui, "env-cur").first.fill("C1")
    T(ui, "env-cur").nth(1).fill("c.io")
    T(ui, "env-cur-to-init").click()
    assert T(ui, "env-val").first.input_value() == "C1" and T(ui, "env-cur").first.input_value() == ""
    T(ui, "env-cur").first.fill("C2")
    expect(T(ui, "env-cur-reset")).to_be_enabled()
    T(ui, "env-cur-reset").click()
    expect(T(ui, "env-cur").first).to_have_value("")
    expect(T(ui, "env-cur-reset")).to_be_disabled()
    expect(T(ui, "env-used-by")).to_have_text("Bu muhitni 5 ta so'rov ishlatadi")                  # 5 ta so'rov {{host}} ishlatadi
    with ui.expect_download() as d:
        T(ui, "env-export").click()
    import json
    exp = json.load(open(d.value.path()))
    assert exp["name"] == "Prod muhit" and "current" not in exp["values"][0] and exp["values"][0]["value"] == "C1"       # eksportda faqat boshlang'ich
    T(ui, "env-duplicate").click()
    expect(T(ui, "env-name")).to_have_value("Prod muhit Copy")


def test_script_set_variable_changes_current_only(app, env, ui):
    e = app.api("GET", f"/api/environments/{env}")
    assert e["values"][0]["value"] == "INITIAL"
    r = app.flask.test_client().post("/run_one", json={"url": ui.echo + "/echo", "method": "GET", "scripts": {"prerequest": [
        {"source": "pm.environment.set('tok', 'FROM_SCRIPT')", "kind": "prerequest", "scope": "request", "name": "x", "id": "x"}], "test": []}},
        headers={"X-Session-Token": "e2e-token"})
    assert r.status_code == 200
    v = app.api("GET", f"/api/environments/{env}")["values"][0]
    assert v["value"] == "INITIAL" and v["current"] == "FROM_SCRIPT"


# ── Tarix ──
def seed_history(app, echo):
    db = app.flask.extensions["db"]
    now = time.time()
    base = {"headers": [], "params": [], "time": 0.2, "size": 120, "resp_headers": {"Date": "x", "X-A": "1"}}
    for i in range(3):                                                                         # ketma-ket bir xil — ×3
        db.add_history("request", {**base, "method": "GET", "url": echo + "/echo?same=1", "status": 200, "body": '{"id": %d, "n": "x"}' % i}, ts=now - 100 + i)
    db.add_history("request", {**base, "method": "POST", "url": echo + "/echo", "status": 500, "body": "{}"}, ts=now - 50)
    db.add_history("request", {**base, "method": "GET", "url": echo + "/status/404", "status": 404, "body": "{}"}, ts=now - 40)
    db.add_history("request", {**base, "size": 100, "method": "GET", "url": echo + "/old", "status": 200, "body": '{"v": 1, "items": [1, 2]}'}, ts=now - 86400 * 1.2)
    db.add_history("request", {**base, "size": 200, "method": "GET", "url": echo + "/old", "status": 200, "body": '{"v": 2, "items": [1, 3, 4]}'}, ts=now - 86400 * 1.2 + 5)


@pytest.fixture
def hist(app, ui, echo_server):
    seed_history(app, echo_server)
    T(ui, "sb-history").click()
    T(ui, "history-btn").click()
    expect(T(ui, "history-drawer")).to_be_visible()
    return ui


def test_history_groups_by_day_splits_host_and_path_and_merges_repeats(hist, echo_server):
    expect(T(hist, "hd-row").first).to_be_visible()
    days = [d.strip() for d in T(hist, "hd-day").all_text_contents()]
    assert days[0] == "Bugun" and "Kecha" in days
    expect(T(hist, "hd-repeat")).to_have_text(["×3", "×2"])                                    # ketma-ket bir xil so'rovlar — bitta qator (/echo?same=1 ×3, /old ×2)
    row = T(hist, "hd-row").filter(has_text="/echo?same=1")
    expect(row.locator("[data-testid=hd-path]")).to_have_text("/echo?same=1")
    expect(row.locator("[data-testid=hd-host]")).to_contain_text(echo_server.split("//")[1])
    expect(row.locator("[data-testid=hd-status]")).to_have_text("200")


def test_history_status_filters_and_search(hist):
    expect(T(hist, "hd-row").first).to_be_visible()
    all_rows = T(hist, "hd-row").count()
    hist.click("[data-testid=history-drawer] [data-filter='5xx']")
    expect(T(hist, "hd-row")).to_have_count(1)
    hist.click("[data-testid=history-drawer] [data-filter='4xx']")
    expect(T(hist, "hd-row")).to_have_count(1)
    hist.click("[data-testid=history-drawer] [data-filter='2xx']")
    assert T(hist, "hd-row").count() == all_rows - 2
    hist.click("[data-testid=history-drawer] [data-filter=all]")
    T(hist, "hd-search").fill("old")
    expect(T(hist, "hd-row")).to_have_count(1)                                                  # ikki bir xil /old — bitta ×2 qator
    T(hist, "hd-search").fill("POST")
    expect(T(hist, "hd-row")).to_have_count(1)


def test_history_pick_two_shows_response_diff_with_ignore_option(hist):
    T(hist, "hd-search").fill("/old")
    expect(T(hist, "hd-repeat")).to_have_text("×2")
    T(hist, "hd-expand").click()
    subs = T(hist, "hd-pick-sub")
    expect(subs).to_have_count(2)
    subs.nth(0).check()                                                                         # avval yangisini (ro'yxatda tepada), keyin eskisini tanlaymiz
    subs.nth(1).check()
    expect(T(hist, "hd-diff")).to_be_visible()
    expect(T(hist, "hd-card-A")).to_be_visible()
    expect(T(hist, "hd-card-B")).to_be_visible()
    adds = int(re.sub(r"\D", "", T(hist, "hd-add").inner_text()))
    dels = int(re.sub(r"\D", "", T(hist, "hd-del").inner_text()))
    assert adds > 0 and dels > 0
    expect(hist.locator(".hx-dl.add")).to_have_count(adds)
    expect(hist.locator(".hx-dl.del")).to_have_count(dels)
    expect(T(hist, "hd-hdiff")).to_contain_text("Headers: 0 farq")                              # Date chiqarib tashlangan
    a, b = T(hist, "hd-card-A").inner_text(), T(hist, "hd-card-B").inner_text()
    assert "100 B" in a and "200 B" in b                                                        # A — eskirog'i (100 B), B — yangirog'i (200 B)


def test_history_diff_ignores_id_and_time_fields_when_enabled(app, hist, echo_server):
    db = app.flask.extensions["db"]
    base = {"method": "GET", "url": echo_server + "/idonly", "headers": [], "params": [], "status": 200, "resp_headers": {"Date": "1"}}
    db.add_history("request", {**base, "body": '{"id": 1, "ts": 100, "name": "a"}'}, ts=time.time() - 5)
    db.add_history("request", {**base, "body": '{"id": 2, "ts": 200, "name": "a"}', "resp_headers": {"Date": "2"}}, ts=time.time() - 4)
    hist.keyboard.press("Escape")
    T(hist, "history-btn").click()
    T(hist, "hd-search").fill("idonly")
    T(hist, "hd-expand").click()
    T(hist, "hd-pick-sub").nth(0).check()
    T(hist, "hd-pick-sub").nth(1).check()
    expect(T(hist, "hd-ignore")).to_be_checked()
    expect(T(hist, "hd-add")).to_have_text("+0 qator")                                          # faqat id/ts farq qiladi — e'tiborsiz
    expect(T(hist, "hd-del")).to_have_text("−0 qator")
    expect(T(hist, "hd-hdiff")).to_contain_text("Headers: 0 farq")
    T(hist, "hd-ignore").uncheck()
    expect(T(hist, "hd-add")).not_to_have_text("+0 qator")                                      # o'chirilsa — haqiqiy farq ko'rinadi
    expect(T(hist, "hd-hdiff")).to_contain_text("Headers: 1 farq")


def test_history_open_in_tab_and_save_to_collection_and_clear(hist, echo_server):
    T(hist, "hd-row").filter(has_text="/status/404").click()
    expect(T(hist, "hd-det-path")).to_have_text("/status/404")
    T(hist, "hd-open").click()
    expect(T(hist, "history-drawer")).to_have_count(0)
    expect(T(hist, "url")).to_have_text(echo_server + "/status/404")
    T(hist, "history-btn").click()
    T(hist, "hd-row").first.click()
    T(hist, "hd-save").click()
    expect(T(hist, "saveas-dialog")).to_be_visible()
    hist.click("[data-testid=saveas-dialog] button:not(.primary)")


# ── Joylashuv va zich rejim ──
def test_layout_toggle_side_by_side_persists_and_is_in_settings(ui):
    ui.locator("[data-name='InheritOne']").dblclick()
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_be_visible()
    req_box = ui.locator(".req-pane").bounding_box()
    resp_box = T(ui, "response").bounding_box()
    assert resp_box["y"] > req_box["y"] + req_box["height"] - 5                                # sukut: ustma-ust
    T(ui, "layout-toggle").click()
    req_box = ui.locator(".req-pane").bounding_box()
    resp_box = T(ui, "response").bounding_box()
    assert resp_box["x"] >= req_box["x"] + req_box["width"] - 5 and abs(resp_box["y"] - req_box["y"]) < 80      # yonma-yon
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    assert ui.evaluate("document.documentElement.classList.contains('view-side')")             # tanlov saqlandi
    T(ui, "settings-btn").click()
    expect(T(ui, "view-side")).to_be_checked()
    T(ui, "view-stack").check()
    assert not ui.evaluate("document.documentElement.classList.contains('view-side')")


def test_dense_mode_shrinks_rows_and_persists(ui):
    ui.locator("[data-name='InheritOne']").dblclick()
    ui.click("[data-section=headers]")
    h = lambda: ui.locator("[data-testid=headers-table] tbody tr").first.bounding_box()["height"]  # noqa: E731
    normal = h()
    T(ui, "settings-btn").click()
    T(ui, "view-dense").check()
    ui.locator("[data-testid=tab-bar] [data-testid=tab]").first.click() if False else None
    ui.locator("[data-name='InheritOne']").dblclick()
    ui.click("[data-section=headers]")
    assert h() < normal
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    assert ui.evaluate("document.documentElement.classList.contains('dense')")


# ── Body segmentlari ──
def test_body_segments_and_default_raw_json_for_post_put(ui):
    T(ui, "new-tab").click()
    ui.click("[data-section=body]")
    seg = lambda m: ui.locator(f"[data-testid=body-mode] [data-mode={m}]")  # noqa: E731
    assert [b.strip() for b in ui.locator("[data-testid=body-mode] button").all_inner_texts()] == ["none", "form-data", "urlencoded", "raw", "binary", "GraphQL"]
    expect(T(ui, "body-mode")).to_have_attribute("data-value", "none")                          # GET — none
    ui.select_option("[data-testid=method]", "POST")
    expect(T(ui, "body-mode")).to_have_attribute("data-value", "json")                          # POST — raw JSON sukut bo'yicha
    expect(seg("raw")).to_have_attribute("aria-checked", "true")
    expect(T(ui, "body-format")).to_have_value("json")
    ui.select_option("[data-testid=body-format]", "raw")
    expect(T(ui, "body-mode")).to_have_attribute("data-value", "raw")
    seg("multipart").click()
    expect(seg("multipart")).to_have_attribute("aria-checked", "true")
    expect(T(ui, "formdata-table")).to_be_visible()
    seg("none").click()
    ui.select_option("[data-testid=method]", "PUT")
    expect(T(ui, "body-mode")).to_have_attribute("data-value", "json")                          # PUT ham
    seg("form").click()
    ui.select_option("[data-testid=method]", "POST")
    expect(T(ui, "body-mode")).to_have_attribute("data-value", "form")                          # tanlangan tur ustidan yozilmaydi
    ui.select_option("[data-testid=method]", "GET")
    expect(T(ui, "body-mode")).to_have_attribute("data-value", "form")


def test_body_segments_keyboard_arrows(ui):
    T(ui, "new-tab").click()
    ui.click("[data-section=body]")
    ui.locator("[data-testid=body-mode] [data-mode=none]").focus()
    ui.keyboard.press("ArrowRight")
    expect(T(ui, "body-mode")).to_have_attribute("data-value", "multipart")
    ui.keyboard.press("ArrowLeft")
    expect(T(ui, "body-mode")).to_have_attribute("data-value", "none")


# ── Batch formasi ──
def test_batch_form_is_compact_actions_on_one_line_at_the_left_and_labels_not_clipped(ui):
    ui.locator("[data-name='InheritOne']").dblclick()
    ui.click("[data-section=batch]")
    cells = ui.locator("[data-testid=batch-grid] .bf").all()
    assert len(cells) == 6
    for c in cells:
        assert c.bounding_box()["width"] <= 250                                                 # maydonlar mazmuniga mos, 1/3 kenglikka cho'zilmaydi
    run, stop = T(ui, "batch-run").bounding_box(), T(ui, "batch-stop").bounding_box()
    form = ui.locator("[data-testid=batch-settings]").bounding_box()
    assert abs(run["y"] - stop["y"]) < 4 and run["x"] <= form["x"] + 8                          # amallar bitta qatorda, chapda
    for lab in ui.locator("[data-testid=batch-grid] .bl").all():
        assert lab.evaluate("e => e.scrollWidth <= e.clientWidth + 1"), lab.inner_text()      # yorliq kesilmagan
