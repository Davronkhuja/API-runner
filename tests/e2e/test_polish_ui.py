"""Bosqich 8 sayqali: sidebar «⋯» menyusi, klaviatura yorliqlari (?), birinchi ishga tushirish tanishtiruvi."""
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


def boot(app, page, query=""):
    page.goto(app.url + query)
    page.wait_for_selector("[data-testid=app]")


def test_sidebar_header_keeps_two_main_buttons_and_more_menu(app, page):
    boot(app, page)
    expect(T(page, "sb-new-request")).to_be_visible()
    expect(T(page, "new-collection")).to_be_visible()
    expect(T(page, "trash-open")).to_have_count(0)
    T(page, "sb-more").click()
    expect(T(page, "sb-more-menu")).to_be_visible()
    for t in ("trash-open", "find-open", "shortcuts-open"):
        expect(T(page, t)).to_be_visible()
    box, sb = T(page, "sb-more").bounding_box(), T(page, "sidebar").bounding_box()
    assert box["x"] + box["width"] <= sb["x"] + sb["width"] + 1          # sidebar ichida
    page.keyboard.press("Escape")
    expect(T(page, "sb-more-menu")).to_have_count(0)
    T(page, "sb-more").click()
    page.mouse.click(900, 500)                                            # tashqariga bosish yopadi
    expect(T(page, "sb-more-menu")).to_have_count(0)


def test_question_mark_opens_shortcuts_but_not_while_typing(app, page):
    boot(app, page)
    page.keyboard.press("?")
    expect(T(page, "shortcuts-dialog")).to_be_visible()
    expect(T(page, "shortcuts-dialog")).to_contain_text("⌘ K")
    page.keyboard.press("Escape")
    expect(T(page, "shortcuts-dialog")).to_have_count(0)
    T(page, "sb-new-request").click()
    T(page, "url").click()
    page.keyboard.type("a?b")                                             # URL maydonida «?» yozilishi kerak
    expect(T(page, "shortcuts-dialog")).to_have_count(0)
    T(page, "sb-more").click()
    T(page, "shortcuts-open").click()
    expect(T(page, "shortcuts-dialog")).to_be_visible()


def test_onboarding_steps_skip_and_remembered(app, page):
    boot(app, page, "?onboarding=1")
    expect(T(page, "onboarding")).to_be_visible()
    first = T(page, "onb-text").inner_text()
    T(page, "onb-next").click()
    assert T(page, "onb-text").inner_text() != first
    T(page, "onb-back").click()
    T(page, "onb-next").click()
    T(page, "onb-next").click()
    expect(T(page, "onb-done")).to_be_visible()
    T(page, "onb-done").click()
    expect(T(page, "onboarding")).to_have_count(0)
    assert page.evaluate("localStorage.getItem('apirunner.onboarded')") == "1"
    page.evaluate("localStorage.removeItem('apirunner.onboarded')")
    boot(app, page, "?onboarding=1")
    T(page, "onb-skip").click()
    expect(T(page, "onboarding")).to_have_count(0)


def test_no_onboarding_in_automated_browser_by_default(app, page):
    boot(app, page)
    expect(T(page, "onboarding")).to_have_count(0)


# ── yuklanish / xato / bo'sh holatlari ──
def fail_once(page, pattern):
    state = {"n": 0}

    def handler(route):
        state["n"] += 1
        if state["n"] == 1:
            route.fulfill(status=500, content_type="application/json", body='{"error": "Server xatosi"}')
        else:
            route.continue_()
    page.route(pattern, handler)


def test_trash_shows_loading_then_error_with_retry_then_empty(app, page):
    boot(app, page)
    state = {"n": 0}

    def handler(route):
        state["n"] += 1
        if state["n"] == 1:
            page.wait_for_timeout(400)                                        # yuklanish holati ko'rinsin
            route.fulfill(status=500, content_type="application/json", body='{"error": "Server xatosi"}')
        else:
            route.continue_()
    page.route("**/api/trash", handler)
    T(page, "sb-more").click()
    T(page, "trash-open").click()
    expect(T(page, "trash-loading")).to_be_visible()
    expect(T(page, "trash-error")).to_contain_text("Server xatosi")
    expect(T(page, "trash-empty")).to_have_count(0)                           # xato «Savat bo'sh» deb ko'rsatilmaydi
    T(page, "trash-error").locator("[data-testid=state-retry]").click()
    expect(T(page, "trash-empty")).to_be_visible()


def test_monitor_and_cookies_show_error_and_recover(app, page):
    boot(app, page)
    fail_once(page, "**/api/monitors")
    T(page, "monitor-open").click()
    expect(T(page, "mon-load-error")).to_be_visible()
    T(page, "mon-load-error").locator("[data-testid=state-retry]").click()
    expect(T(page, "mon-empty")).to_be_visible()
    page.keyboard.press("Escape")
    fail_once(page, "**/api/cookies")
    T(page, "cookies-btn").click()
    expect(T(page, "cookies-error")).to_be_visible()
    T(page, "cookies-error").locator("[data-testid=state-retry]").click()
    expect(T(page, "cookies-empty")).to_be_visible()


def test_settings_load_error_is_shown_not_swallowed(app, page):
    boot(app, page)
    fail_once(page, "**/api/backups")
    T(page, "settings-btn").click()
    expect(T(page, "settings-load-error")).to_be_visible()
    T(page, "settings-load-error").locator("[data-testid=state-retry]").click()
    expect(T(page, "settings-load-error")).to_have_count(0)


def test_escape_closes_dialog_even_when_focused_button_was_removed(app, page):
    boot(app, page)
    app.api("POST", "/api/collections", {"name": "C"})
    page.reload()
    page.wait_for_selector("[data-testid=app]")
    T(page, "monitor-open").click()
    T(page, "mon-new").click()                                            # fokusdagi tugma («Yangi monitor») DOM'dan o'chadi
    expect(T(page, "monitor-form")).to_be_visible()
    page.keyboard.press("Escape")
    expect(T(page, "monitor-dialog")).to_have_count(0)


def test_escape_closes_only_the_topmost_of_stacked_dialogs(app, page):
    boot(app, page)
    app.api("POST", "/api/collections", {"name": "C"})
    page.reload()
    page.wait_for_selector("[data-testid=app]")
    T(page, "monitor-open").click()
    T(page, "mon-new").click()
    T(page, "mon-save").click()
    expect(T(page, "mon-item")).to_have_count(1)
    T(page, "mon-del").click()                                            # ustiga tasdiq dialogi
    expect(T(page, "confirm-dialog")).to_be_visible()
    page.evaluate("document.activeElement && document.activeElement.blur()")     # fokus body'ga tushdi
    page.keyboard.press("Escape")
    expect(T(page, "confirm-dialog")).to_have_count(0)
    expect(T(page, "monitor-dialog")).to_be_visible()


def test_onboarding_only_for_empty_workspace_or_forced(app, page):
    boot(app, page, "?onboarding=auto")                                  # bo'sh workspace (faqat bo'sh sukut collection)
    expect(T(page, "onboarding")).to_be_visible()
    T(page, "onb-skip").click()
    page.evaluate("localStorage.removeItem('apirunner.onboarded')")
    cid = app.api("GET", "/api/workspace")["collections"][0]["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "r1", "name": "R", "request": {"method": "GET", "header": [], "url": {"raw": "http://localhost/x"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    boot(app, page, "?onboarding=auto")                                  # endi so'rov bor — chiqmaydi
    expect(T(page, "tree-row").first).to_be_visible()
    expect(T(page, "onboarding")).to_have_count(0)
    boot(app, page, "?onboarding=1")                                     # majburan
    expect(T(page, "onboarding")).to_be_visible()
