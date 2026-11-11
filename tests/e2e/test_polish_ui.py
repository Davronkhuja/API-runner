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
