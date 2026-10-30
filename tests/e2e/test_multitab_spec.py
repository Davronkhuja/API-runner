"""Bosqich 2 — Multi-tab (MAJBURIY). Spetsifikatsiyaning har bir bandi uchun alohida e2e test."""
import pytest
from playwright.sync_api import expect

TREE = [("f1", "Papka", [("a", "Alfa", None), ("b", "Beta", None)]), ("c", "Gamma", None), ("d", "Delta", None)]
TABS = "[data-testid=tab]"


def row(p, name):
    return p.locator(f"[data-testid=tree-row][data-name='{name}']")


def titles(p):
    return p.locator(f"{TABS} .title").all_inner_texts()


@pytest.fixture
def ui(app, page):
    app.seed(TREE)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=tree-row][data-name=Gamma]")
    return page


def open_perm(p, name):
    row(p, name).dblclick()


def edit_url(p, text="http://edited"):
    p.fill("[data-testid=url]", text)


def test_open_many_tabs_simultaneously(ui):
    for n in ("Alfa", "Beta", "Gamma", "Delta"):
        open_perm(ui, n)
    assert titles(ui) == ["Alfa", "Beta", "Gamma", "Delta"]
    for _ in range(6):
        ui.click("[data-testid=new-tab]")
    expect(ui.locator(TABS)).to_have_count(10)


def test_single_click_opens_preview_tab_italic_replaced_by_next_click(ui):
    row(ui, "Gamma").click()
    expect(ui.locator(f"{TABS}.preview")).to_have_count(1)
    assert ui.locator(f"{TABS}.preview .title").evaluate("e => getComputedStyle(e).fontStyle") == "italic"
    row(ui, "Delta").click()
    assert titles(ui) == ["Delta"]


def test_double_click_makes_tab_permanent(ui):
    row(ui, "Gamma").click()
    row(ui, "Gamma").dblclick()
    expect(ui.locator(f"{TABS}.preview")).to_have_count(0)
    row(ui, "Delta").click()
    assert titles(ui) == ["Gamma", "Delta"]


def test_editing_preview_tab_makes_it_permanent(ui):
    row(ui, "Gamma").click()
    edit_url(ui)
    expect(ui.locator(f"{TABS}.preview")).to_have_count(0)
    row(ui, "Delta").click()
    assert titles(ui) == ["Gamma", "Delta"]


def test_each_tab_keeps_independent_state_url_params_body_auth_scripts_response_scroll(ui, echo_server):
    open_perm(ui, "Gamma")
    ui.fill("[data-testid=url]", echo_server + "/echo?x=1")
    ui.click("[data-section=auth]")
    ui.select_option("[data-testid=auth-type]", "bearer")
    ui.fill("[data-testid=auth-token]", "TOK-G")
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "raw")
    ui.fill("[data-testid=body-raw]", "gamma-body")
    ui.click("[data-testid=send]")
    expect(ui.locator("[data-testid=resp-status]")).to_have_text("200")
    open_perm(ui, "Delta")
    expect(ui.locator("[data-testid=url]")).to_have_value("http://x/Delta")
    expect(ui.locator("[data-testid=response]")).to_contain_text("Javob shu yerda")
    ui.locator(f"{TABS}", has_text="Gamma").click()
    expect(ui.locator("[data-testid=url]")).to_have_value(echo_server + "/echo?x=1")
    expect(ui.locator("[data-testid=resp-status]")).to_have_text("200")
    ui.click("[data-section=auth]")
    expect(ui.locator("[data-testid=auth-token]")).to_have_value("TOK-G")
    ui.click("[data-section=body]")
    expect(ui.locator("[data-testid=body-raw]")).to_have_value("gamma-body")
    ui.click("[data-section=params]")
    expect(ui.locator("[data-testid=params-table] input[type=text]").first).to_have_value("x")


def test_switching_tabs_loses_nothing(ui):
    open_perm(ui, "Gamma")
    edit_url(ui, "http://keep-me")
    open_perm(ui, "Delta")
    ui.locator(TABS, has_text="Gamma").click()
    expect(ui.locator("[data-testid=url]")).to_have_value("http://keep-me")
    expect(ui.locator(f"{TABS}", has_text="Gamma").locator("[data-testid=dirty-dot]")).to_be_visible()


def test_response_scroll_is_kept_per_tab(ui, echo_server):
    open_perm(ui, "Gamma")
    ui.fill("[data-testid=url]", echo_server + "/big")
    ui.click("[data-testid=send]")
    expect(ui.locator("[data-testid=resp-status]")).to_have_text("200")
    ui.locator("[data-testid=response]").evaluate("e => { e.scrollTop = 300 }")
    ui.wait_for_timeout(100)
    open_perm(ui, "Delta")
    ui.locator(TABS, has_text="Gamma").click()
    ui.wait_for_timeout(200)
    assert ui.locator("[data-testid=response]").evaluate("e => e.scrollTop") > 100


def test_dirty_indicator_dot_on_edit_and_cleared_on_save(ui):
    open_perm(ui, "Gamma")
    expect(ui.locator("[data-testid=dirty-dot]")).to_have_count(0)
    edit_url(ui)
    expect(ui.locator("[data-testid=dirty-dot]")).to_have_count(1)
    ui.click("[data-testid=save]")
    expect(ui.locator("[data-testid=dirty-dot]")).to_have_count(0)


def test_closing_dirty_tab_shows_save_dontsave_cancel_dialog(ui):
    open_perm(ui, "Gamma")
    edit_url(ui)
    ui.click("[data-testid=tab-close]")
    dlg = ui.locator("[data-testid=close-dialog]")
    expect(dlg).to_be_visible()
    for t in ("dlg-save", "dlg-discard", "dlg-cancel"):
        expect(dlg.locator(f"[data-testid={t}]")).to_be_visible()


def test_dialog_save_saves_and_closes(ui, app):
    open_perm(ui, "Gamma")
    edit_url(ui, "http://saved-url")
    ui.click("[data-testid=tab-close]")
    ui.click("[data-testid=dlg-save]")
    expect(ui.locator(TABS)).to_have_count(0)
    col = app.api("GET", "/api/collections/" + app.api("GET", "/api/workspace")["collections"][0]["id"])
    gamma = next(i for i in col["item"] if i["id"] == "c")
    assert gamma["request"]["url"]["raw"] == "http://saved-url"


def test_dialog_dont_save_discards_and_closes(ui, app):
    open_perm(ui, "Gamma")
    edit_url(ui, "http://discard-me")
    ui.click("[data-testid=tab-close]")
    ui.click("[data-testid=dlg-discard]")
    expect(ui.locator(TABS)).to_have_count(0)
    open_perm(ui, "Gamma")
    expect(ui.locator("[data-testid=url]")).to_have_value("http://x/Gamma")


def test_dialog_cancel_keeps_tab_open(ui):
    open_perm(ui, "Gamma")
    edit_url(ui)
    ui.click("[data-testid=tab-close]")
    ui.click("[data-testid=dlg-cancel]")
    expect(ui.locator(TABS)).to_have_count(1)
    expect(ui.locator("[data-testid=url]")).to_have_value("http://edited")


def _ctx(p, tab_title, act):
    p.locator(TABS, has_text=tab_title).first.click(button="right")
    p.click(f"[data-testid=tab-menu] [data-act={act}]")


def _three(p):
    for n in ("Alfa", "Gamma", "Delta"):
        open_perm(p, n)


def test_context_menu_duplicate(ui):
    open_perm(ui, "Gamma")
    _ctx(ui, "Gamma", "dup")
    assert titles(ui) == ["Gamma", "Gamma Copy"]


def test_context_menu_close(ui):
    _three(ui)
    _ctx(ui, "Gamma", "close")
    assert titles(ui) == ["Alfa", "Delta"]


def test_context_menu_close_others(ui):
    _three(ui)
    _ctx(ui, "Gamma", "others")
    assert titles(ui) == ["Gamma"]


def test_context_menu_close_to_the_right(ui):
    _three(ui)
    _ctx(ui, "Gamma", "right")
    assert titles(ui) == ["Alfa", "Gamma"]


def test_context_menu_close_all(ui):
    _three(ui)
    _ctx(ui, "Gamma", "all")
    expect(ui.locator(TABS)).to_have_count(0)
    expect(ui.locator("[data-testid=no-tabs]")).to_be_visible()


def test_context_menu_reveal_in_collection(ui):
    open_perm(ui, "Beta")
    ui.click("[data-testid=tree-row][data-name=Papka]")      # papkani yopamiz
    expect(row(ui, "Beta")).to_have_count(0)
    _ctx(ui, "Beta", "reveal")
    expect(row(ui, "Beta")).to_be_visible()
    expect(row(ui, "Beta")).to_have_class(__import__("re").compile(r"\bsel\b"))


def test_drag_and_drop_reorder_tabs(ui):
    _three(ui)
    ui.locator(TABS, has_text="Delta").drag_to(ui.locator(TABS, has_text="Alfa"), target_position={"x": 3, "y": 10})
    assert titles(ui) == ["Delta", "Alfa", "Gamma"]


def test_many_tabs_horizontal_scroll(ui):
    for _ in range(25):
        ui.click("[data-testid=new-tab]")
    sc = ui.locator(".tabs-scroll")
    assert sc.evaluate("e => e.scrollWidth > e.clientWidth")


def test_all_tabs_dropdown_lists_and_activates(ui):
    for _ in range(25):
        ui.click("[data-testid=new-tab]")
    open_perm(ui, "Gamma")
    ui.locator(TABS).first.click()
    ui.click("[data-testid=all-tabs]")
    lst = ui.locator("[data-testid=all-tabs-list] button")
    expect(lst).to_have_count(26)
    lst.filter(has_text="Gamma").click()
    expect(ui.locator(f"{TABS}.active .title")).to_have_text("Gamma")
    assert ui.locator(f"{TABS}.active").evaluate("e => { const r = e.getBoundingClientRect(), s = e.parentElement.getBoundingClientRect(); return r.left >= s.left - 1 && r.right <= s.right + 1 }")


def test_open_tabs_and_active_tab_restored_after_page_reload(ui):
    _three(ui)
    ui.locator(TABS, has_text="Gamma").click()
    edit_url(ui, "http://drafted")
    ui.wait_for_timeout(700)                           # debounce
    ui.reload()
    ui.wait_for_selector(TABS)
    assert titles(ui) == ["Alfa", "Gamma", "Delta"]
    expect(ui.locator(f"{TABS}.active .title")).to_have_text("Gamma")
    expect(ui.locator("[data-testid=url]")).to_have_value("http://drafted")


def test_open_tabs_and_active_tab_restored_after_server_restart(ui, app):
    _three(ui)
    ui.locator(TABS, has_text="Delta").click()
    ui.wait_for_timeout(700)
    app.restart()
    ui.goto(app.url)
    ui.wait_for_selector(TABS)
    assert titles(ui) == ["Alfa", "Gamma", "Delta"]
    expect(ui.locator(f"{TABS}.active .title")).to_have_text("Delta")


def test_shortcut_cmd_t_new_tab(ui):
    ui.keyboard.press("Control+t")
    expect(ui.locator(TABS)).to_have_count(1)
    ui.keyboard.press("Meta+t")
    expect(ui.locator(TABS)).to_have_count(2)


def test_shortcut_cmd_w_close_tab(ui):
    _three(ui)
    ui.keyboard.press("Control+w")
    assert titles(ui) == ["Alfa", "Gamma"]


def test_shortcut_ctrl_tab_next_and_ctrl_shift_tab_previous(ui):
    _three(ui)
    ui.keyboard.press("Control+Tab")
    expect(ui.locator(f"{TABS}.active .title")).to_have_text("Alfa")        # Delta dan keyin aylanadi
    ui.keyboard.press("Control+Shift+Tab")
    expect(ui.locator(f"{TABS}.active .title")).to_have_text("Delta")


def test_shortcut_cmd_shift_t_reopen_closed_tab(ui):
    _three(ui)
    ui.keyboard.press("Control+w")
    assert titles(ui) == ["Alfa", "Gamma"]
    ui.keyboard.press("Control+Shift+t")
    assert titles(ui) == ["Alfa", "Gamma", "Delta"]


def test_opening_same_request_twice_switches_to_existing_tab(ui):
    _three(ui)
    row(ui, "Alfa").click()
    assert titles(ui) == ["Alfa", "Gamma", "Delta"]
    expect(ui.locator(f"{TABS}.active .title")).to_have_text("Alfa")


def test_environment_opens_as_tab(ui):
    ui.click("[data-testid=sb-environments]")
    ui.click("[data-testid=new-env]")
    expect(ui.locator("[data-testid=env-tab]")).to_be_visible()
    assert "Yangi muhit" in titles(ui)


def test_collection_opens_as_tab(ui):
    ui.locator("[data-testid=tree-row][data-kind=collection]").dblclick()
    expect(ui.locator("[data-testid=tab-collection]")).to_be_visible()
    assert titles(ui) == ["Col"]


def test_runner_opens_as_tab(ui):
    ui.locator("[data-testid=tree-row][data-kind=collection]").click(button="right")
    ui.click("[data-testid=tree-menu] [data-act=runner]")
    expect(ui.locator("[data-testid=runner-tab]")).to_be_visible()
