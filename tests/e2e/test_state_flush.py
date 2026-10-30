"""Tab holati debounce bilan yoziladi — lekin foydalanuvchi o'zgarishdan DARHOL sahifani yangilasa/yopsa ham hech narsa yo'qolmasligi shart.
Bu yerda hech qanday qat'iy sleep yo'q."""
import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import eventually

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
TAB = "[data-testid=tab]"


@pytest.fixture
def ui(app, page):
    app.seed([("a", "Alfa", None), ("b", "Beta", None)])
    page.goto(app.url)
    page.wait_for_selector("[data-testid=tree-row][data-name=Alfa]")
    return page


def open_perm(p, name):
    p.locator(f"[data-testid=tree-row][data-name={name}]").dblclick()


def reload(p):
    p.reload()
    p.wait_for_selector("[data-testid=app]")


def test_edit_then_immediate_reload_keeps_last_change_repeatedly(ui):
    open_perm(ui, "Alfa")
    for i in range(8):                                         # poyga holatini ushlash uchun takror
        T(ui, "url").fill(f"http://last-{i}")
        reload(ui)
        expect(T(ui, "url")).to_have_value(f"http://last-{i}")
        expect(ui.locator(TAB).locator("[data-testid=dirty-dot]")).to_have_count(1)


def test_typing_keystrokes_then_immediate_reload(ui):
    open_perm(ui, "Alfa")
    T(ui, "url").fill("")
    T(ui, "url").press_sequentially("http://typed-live/path", delay=5)
    reload(ui)
    expect(T(ui, "url")).to_have_value("http://typed-live/path")


def test_params_headers_body_edits_survive_immediate_reload(ui):
    T(ui, "new-tab").click()
    T(ui, "url").fill("http://h/p")
    ui.click("[data-section=params]")
    ui.locator("[data-testid=params-table] input[type=text]").nth(0).fill("q")
    ui.locator("[data-testid=params-table] input[type=text]").nth(1).fill("1")
    ui.click("[data-section=headers]")
    ui.locator("[data-testid=headers-table] input[type=text]").nth(0).fill("X-A")
    ui.locator("[data-testid=headers-table] input[type=text]").nth(1).fill("v")
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "raw")
    T(ui, "body-raw").fill("son-matn")
    reload(ui)
    expect(T(ui, "url")).to_have_value("http://h/p?q=1")
    ui.click("[data-section=headers]")
    expect(ui.locator("[data-testid=headers-table] input[type=text]").nth(1)).to_have_value("v")
    ui.click("[data-section=body]")
    expect(T(ui, "body-raw")).to_have_value("son-matn")


def test_new_unsaved_tab_survives_immediate_reload(ui):
    T(ui, "new-tab").click()
    T(ui, "url").fill("http://never-saved")
    reload(ui)
    expect(T(ui, "url")).to_have_value("http://never-saved")


def test_tab_switch_and_close_then_immediate_reload(ui):
    open_perm(ui, "Alfa")
    open_perm(ui, "Beta")
    ui.locator(TAB, has_text="Alfa").click()
    reload(ui)
    expect(ui.locator(f"{TAB}.active .title")).to_have_text("Alfa")
    ui.locator(TAB, has_text="Beta").locator("[data-testid=tab-close]").click()
    reload(ui)
    assert ui.locator(f"{TAB} .title").all_inner_texts() == ["Alfa"]


def test_hidden_visibility_flushes_pending_edit_to_server(ui, app):
    open_perm(ui, "Alfa")
    T(ui, "url").fill("http://on-hide")
    ui.evaluate("""() => { Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => 'hidden' });
                           document.dispatchEvent(new Event('visibilitychange')) }""")
    eventually(lambda: app.api("GET", "/api/ui-state")["tabs"]["tabs"][0]["draft"]["url"] == "http://on-hide")


def test_pagehide_flushes_pending_edit_to_server(ui, app):
    open_perm(ui, "Alfa")
    T(ui, "url").fill("http://on-pagehide")
    ui.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
    eventually(lambda: app.api("GET", "/api/ui-state")["tabs"]["tabs"][0]["draft"]["url"] == "http://on-pagehide")


def test_run_flushes_pending_edit_before_sending(ui, app, echo_server):
    open_perm(ui, "Alfa")
    T(ui, "url").fill(echo_server + "/echo?ran=1")
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("200")
    st = app.api("GET", "/api/ui-state")["tabs"]["tabs"][0]["draft"]["url"]
    assert st == echo_server + "/echo?ran=1"


def test_save_flushes_and_clears_dirty_on_server(ui, app):
    open_perm(ui, "Alfa")
    T(ui, "url").fill("http://saved-now")
    T(ui, "save").click()
    expect(ui.locator("[data-testid=dirty-dot]")).to_have_count(0)
    tab = app.api("GET", "/api/ui-state")["tabs"]["tabs"][0]
    assert tab["dirty"] is False and tab["draft"]["url"] == "http://saved-now"


def test_expanded_tree_state_survives_immediate_reload_without_losing_tabs(app, page):
    app.seed([("f1", "F1", [("a", "A", None)]), ("b", "B", None)])
    page.goto(app.url)
    page.wait_for_selector("[data-testid=tree-row][data-name=B]")
    open_perm(page, "B")
    page.locator("[data-testid=tree-row][data-name=F1]").click()          # papkani yopamiz
    reload(page)
    expect(page.locator("[data-testid=tree-row][data-name=A]")).to_have_count(0)
    assert page.locator(f"{TAB} .title").all_inner_texts() == ["B"]        # tablar ham, daraxt holati ham saqlangan (birlashtirilgan PUT)
