"""Qo'lda tekshiruv xatolari (A guruhi): server versiyasi, saqlanmagan javob, ghost 📎/Bulk Edit, disabled holat, ⌘K."""
import re

import pytest
from playwright.sync_api import expect

import apirunner

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "a", "name": "Alpha", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/echo?q=1"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def open_alpha(p):
    p.locator("[data-name='Alpha']").dblclick()
    expect(T(p, "request-editor")).to_be_visible()


# ── A1 ──
def test_status_bar_warns_when_server_is_older_than_ui(app, page):
    page.route("**/api/version", lambda r: r.fulfill(json={"version": "0.0.1"}))
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    warn = T(page, "stale-server")
    expect(warn).to_be_visible()
    expect(warn).to_contain_text("pm2 restart api-runner")
    expect(warn).to_contain_text("0.0.1")


def test_no_warning_when_versions_match_and_endpoint_returns_version(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    expect(T(page, "version")).to_have_text("v" + apirunner.__version__)
    expect(T(page, "stale-server")).to_have_count(0)
    assert app.api("GET", "/api/version")["version"] == apirunner.__version__


# ── A2 ──
def test_response_after_reload_never_shows_an_empty_body(ui):
    open_alpha(ui)
    T(ui, "send").click()
    expect(T(ui, "resp-body")).to_contain_text("q")
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    expect(T(ui, "resp-status")).to_be_visible()                                  # holat/o'lcham saqlangan
    expect(T(ui, "resp-not-saved")).to_be_visible()
    expect(T(ui, "resp-body")).to_have_count(0)                                    # bo'sh <pre> qolmaydi
    T(ui, "resp-resend").click()
    expect(T(ui, "resp-body")).to_contain_text("q")
    expect(T(ui, "resp-not-saved")).to_have_count(0)


# ── A3 ──
def test_ghost_row_has_no_attach_icon_and_bulk_edit_is_one_line(ui):
    T(ui, "new-tab").click()
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "multipart")
    expect(ui.locator("[data-testid=formdata-table] tr[data-ghost] input[type=file]")).to_have_count(0)
    box = T(ui, "kv-bulk").first.bounding_box()
    assert box["height"] <= 26 and box["width"] >= 60
    th = ui.locator(".kv-head thead th").first.bounding_box()
    assert abs((box["y"] + box["height"] / 2) - (th["y"] + th["height"] / 2)) < 4          # sarlavha bilan bir qatorda


# ── A4 ──
@pytest.mark.parametrize("dark", [False, True])
def test_save_button_looks_disabled_when_clean_in_both_themes(ui, dark):
    if dark:
        T(ui, "theme").click()
    open_alpha(ui)
    save = T(ui, "save")
    expect(save).to_be_disabled()
    css = ui.evaluate("(e => { const s = getComputedStyle(e); return {o: s.opacity, c: s.cursor} })(document.querySelector('[data-testid=save]'))")
    assert float(css["o"]) <= 0.6 and css["c"] == "not-allowed"
    ui.locator("[data-testid=url]").click()
    ui.keyboard.type("x")
    expect(save).to_be_enabled()
    assert float(ui.evaluate("getComputedStyle(document.querySelector('[data-testid=save]')).opacity")) == 1.0


# ── A5 ──
def test_cmdk_has_import_and_runner_commands(ui):
    T(ui, "cmdk-open").click()
    rows = T(ui, "cmdk-row")
    T(ui, "cmdk-input").fill("import")
    expect(rows.first).to_contain_text("Import")
    T(ui, "cmdk-input").fill("runner")
    expect(rows.first).to_contain_text("Runner")
