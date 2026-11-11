"""Workspace almashtirgich: yaratish, almashtirish (izolyatsiya), nomlash, o'chirish (Savat) va tiklash."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    app.api("POST", "/api/collections", {"name": "Asosiy collection"})
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def open_menu(p):
    T(p, "ws-switch").click()
    expect(T(p, "ws-menu")).to_be_visible()


def tree(p):
    return p.locator("[data-testid=tree-row][data-kind=collection]").evaluate_all("els => els.map(e => e.dataset.name)")


def test_create_switch_isolation_rename_delete_and_restore(ui, app):
    expect(T(ui, "ws-switch")).to_contain_text("Shaxsiy workspace")
    assert "Asosiy collection" in tree(ui)
    open_menu(ui)
    T(ui, "ws-new").click()
    T(ui, "ws-name").fill("Mijoz A")
    T(ui, "ws-ok").click()
    ui.wait_for_selector("[data-testid=app]")                                              # sahifa yangi workspace bilan qayta yuklandi
    expect(T(ui, "ws-switch")).to_contain_text("Mijoz A")
    assert "Asosiy collection" not in tree(ui)                                              # boshqa workspace'ning ma'lumoti ko'rinmaydi
    n = len(tree(ui))
    T(ui, "new-collection").click()
    expect(ui.locator("[data-testid=tree-row][data-kind=collection]")).to_have_count(n + 1)
    open_menu(ui)
    expect(T(ui, "ws-item")).to_have_count(2)
    ui.locator("[data-testid=ws-item][data-name='Shaxsiy workspace'] [data-testid=ws-pick]").click()
    ui.wait_for_selector("[data-testid=app]")
    expect(T(ui, "ws-switch")).to_contain_text("Shaxsiy workspace")
    assert "Asosiy collection" in tree(ui) and "Yangi collection" not in tree(ui)           # izolyatsiya
    open_menu(ui)
    ui.locator("[data-testid=ws-item][data-name='Mijoz A'] [data-testid=ws-rename]").click()
    T(ui, "ws-name").fill("Shaxsiy workspace")
    T(ui, "ws-ok").click()
    expect(T(ui, "ws-error")).to_contain_text("bor")                                      # nom takrorlanmaydi
    T(ui, "ws-name").fill("Mijoz B")
    T(ui, "ws-ok").click()
    open_menu(ui)
    expect(T(ui, "ws-item").filter(has_text="Mijoz B")).to_have_count(1)
    ui.locator("[data-testid=ws-item][data-name='Mijoz B'] [data-testid=ws-delete]").click()
    expect(T(ui, "confirm-dialog")).to_contain_text("Savatga")
    T(ui, "confirm-ok").click()
    open_menu(ui)
    expect(T(ui, "ws-item")).to_have_count(1)
    expect(ui.locator("[data-testid=ws-item] [data-testid=ws-delete]")).to_have_count(0)    # sukut va faol o'chirilmaydi
    ui.keyboard.press("Escape")
    T(ui, "trash-open").click()
    expect(T(ui, "trash-row")).to_contain_text("Mijoz B")
    T(ui, "trash-restore").click()
    expect(T(ui, "trash-empty")).to_be_visible()
    ui.click("[data-testid=trash-dialog] button.primary")
    open_menu(ui)
    expect(T(ui, "ws-item").filter(has_text="Mijoz B")).to_have_count(1)


def test_switch_asks_confirmation_when_connections_are_open(ui, app, ws_server):
    wid = app.api("POST", "/api/workspaces", {"name": "Boshqa"})["id"]
    T(ui, "new-tab").click()
    ui.select_option("[data-testid=method]", "WS")
    T(ui, "url").click()
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type(ws_server.url + "/echo")
    ui.keyboard.press("Escape")
    T(ui, "proto-connect").click()
    expect(T(ui, "proto-status")).to_have_text("Ulangan")
    open_menu(ui)
    ui.locator("[data-testid=ws-item][data-name='Boshqa'] [data-testid=ws-pick]").click()
    expect(T(ui, "confirm-dialog")).to_contain_text("ulanishlari")
    ui.keyboard.press("Escape")
    assert app.api("GET", "/api/workspaces")["active"] == "default"
    open_menu(ui)
    ui.locator("[data-testid=ws-item][data-name='Boshqa'] [data-testid=ws-pick]").click()
    T(ui, "confirm-ok").click()
    ui.wait_for_selector("[data-testid=app]")
    expect(T(ui, "ws-switch")).to_contain_text("Boshqa")
    assert wid
