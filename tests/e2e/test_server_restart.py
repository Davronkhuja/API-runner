"""Server yangilanishi: "Server eski" → Qayta ishga tushirish (PM2'siz, mock bilan), faol run tasdig'i, yangi build banneri, Bosh sahifa nomlari."""
import json

import pytest
from playwright.sync_api import expect

import apirunner

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
V = apirunner.__version__


def version_mock(page, **over):
    state = {"calls": 0, "info": {"version": V, "ui_version": V, "started": 1, "managed": True, "active": 0, **over}}

    def h(route):
        state["calls"] += 1
        route.fulfill(json=state["info"])
    page.route("**/api/version", h)
    return state


def boot(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")


def test_stale_managed_server_shows_restart_button_overlay_then_reloads(app, page):
    st = version_mock(page, version="0.0.1")
    posts = []

    def restart(route):
        posts.append(json.loads(route.request.post_data or "{}"))
        st["info"] = {**st["info"], "version": V, "started": 2}          # server qayta ko'tarildi
        route.fulfill(json={"ok": True})
    page.route("**/api/admin/restart", restart)
    boot(app, page)
    expect(T(page, "stale-server")).to_contain_text("0.0.1")
    page.evaluate("window.__same_page = true")
    T(page, "restart-server").click()
    expect(T(page, "restarting")).to_be_visible()
    expect(T(page, "restarting")).to_contain_text("Server yangilanmoqda")
    page.wait_for_function("() => window.__same_page !== true", timeout=15000)      # sahifa avtomatik qayta yuklandi
    assert posts == [{}]


def test_not_managed_shows_instruction_instead_of_button(app, page):
    version_mock(page, version="0.0.1", managed=False)
    boot(app, page)
    expect(T(page, "restart-server")).to_have_count(0)
    expect(T(page, "restart-hint")).to_contain_text("./run.command")


def test_restart_with_active_run_asks_confirmation_and_cancel_keeps_server(app, page):
    st = version_mock(page, version="0.0.1", active=1)
    bodies = []

    def restart(route):
        body = json.loads(route.request.post_data or "{}")
        bodies.append(body)
        if body.get("force"):
            st["info"] = {**st["info"], "version": V, "started": 2, "active": 0}
            return route.fulfill(json={"ok": True})
        route.fulfill(status=409, json={"error": "Faol run bor", "needs_confirm": True, "active_runs": 1})
    page.route("**/api/admin/restart", restart)
    boot(app, page)
    T(page, "restart-server").click()
    expect(T(page, "confirm-dialog")).to_contain_text("1 ta faol run")
    page.keyboard.press("Escape")                                              # bekor qilish
    expect(T(page, "confirm-dialog")).to_have_count(0)
    expect(T(page, "restarting")).to_have_count(0)
    assert bodies == [{}]                                                      # force yuborilmadi
    page.evaluate("window.__same_page = true")
    T(page, "restart-server").click()
    T(page, "confirm-ok").click()
    expect(T(page, "restarting")).to_be_visible()
    page.wait_for_function("() => window.__same_page !== true", timeout=15000)
    assert bodies[-1] == {"force": True}


def test_restart_failure_timeout_message_is_not_needed_when_server_rejects(app, page):
    version_mock(page, version="0.0.1")
    page.route("**/api/admin/restart", lambda r: r.fulfill(status=500, json={"error": "ichki xato"}))
    boot(app, page)
    T(page, "restart-server").click()
    expect(T(page, "restarting")).to_have_count(0)
    expect(page.locator(".toast, [role=status]").filter(has_text="ichki xato").first).to_be_visible()


def test_new_build_banner_appears_within_a_minute_and_warns_about_unsaved_tabs(app, page):
    page.clock.install()
    st = version_mock(page)
    boot(app, page)
    expect(T(page, "new-build")).to_have_count(0)
    T(page, "new-tab").click()
    T(page, "url").fill("http://x.test/a")                                      # saqlanmagan (dirty) tab
    st["info"] = {**st["info"], "ui_version": "99.0.0"}
    page.clock.fast_forward(61000)
    expect(T(page, "new-build")).to_contain_text("99.0.0")
    expect(T(page, "stale-server")).to_have_count(0)
    T(page, "reload-new-build").click()
    expect(T(page, "confirm-dialog")).to_contain_text("saqlanmagan")
    page.keyboard.press("Escape")
    expect(T(page, "confirm-dialog")).to_have_count(0)
    expect(T(page, "new-build")).to_be_visible()                                # sahifa yuklanmadi
    page.evaluate("window.__same_page = true")
    T(page, "reload-new-build").click()
    T(page, "confirm-ok").click()
    page.wait_for_function("() => window.__same_page !== true", timeout=15000)


def test_welcome_recent_shows_request_name_with_small_host(app, page):
    app.api("POST", "/api/history", {"kind": "request", "payload": {"method": "GET", "url": "https://api.example.test/v1/contracts?x=1", "name": "Shartnomalar ro'yxati", "headers": [], "params": []}})
    app.api("POST", "/api/history", {"kind": "request", "payload": {"method": "GET", "url": "https://api.example.test/v1/users/42", "headers": [], "params": []}})   # eski yozuv: nomsiz
    boot(app, page)
    names = T(page, "wl-recent-name").all_inner_texts()
    assert names == ["42", "Shartnomalar ro'yxati"] or sorted(names) == ["42", "Shartnomalar ro'yxati"]
    assert not any("http" in n for n in names)
    expect(T(page, "wl-recent-host").first).to_have_text("api.example.test")
    expect(T(page, "wl-recent-row").first).not_to_contain_text("https://")
