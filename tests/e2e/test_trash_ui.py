"""Savat UI: o'chirish → Savat → tiklash / butunlay o'chirish."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def world(app):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    r = lambda i, n: {"id": i, "name": n, "request": {"method": "GET", "header": [], "url": {"raw": "http://x.test/" + n}}, "response": []}  # noqa: E731
    col["item"] = [{"id": "f", "name": "Fold", "item": [r("a", "Alpha"), r("b", "Beta")]}, r("c", "Gamma")]
    app.api("PUT", f"/api/collections/{cid}", col)
    app.api("POST", "/api/environments", {"name": "Temp env"})
    return cid


@pytest.fixture
def ui(app, page, world):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def delete_row(p, name):
    p.locator(f"[data-name='{name}']").first.click(button="right")
    p.click("[data-act=delete]")
    expect(T(p, "confirm-dialog")).to_contain_text("Savatga")
    T(p, "confirm-ok").click()
    expect(p.locator(f"[data-testid=tree-row][data-name='{name}']")).to_have_count(0)


def test_deleted_request_is_in_trash_and_restores_into_its_folder(ui):
    delete_row(ui, "Alpha")
    T(ui, "sb-more").click()
    T(ui, "trash-open").click()
    expect(T(ui, "trash-row")).to_have_count(1)
    expect(T(ui, "trash-name")).to_have_text("Alpha")
    expect(T(ui, "trash-row")).to_contain_text("Col / Fold")
    expect(T(ui, "trash-days")).to_have_text("30 kun qoldi")
    T(ui, "trash-restore").click()
    expect(T(ui, "trash-empty")).to_be_visible()
    ui.keyboard.press("Escape")
    expect(ui.locator("[data-testid=tree-row][data-name='Alpha']")).to_have_count(1)
    names = ui.locator("[data-testid=tree-row]").evaluate_all("els => els.map(e => e.dataset.name)")
    assert names.index("Alpha") < names.index("Beta")                          # o'z o'rniga qaytdi


def test_forever_and_empty_trash_ask_confirmation(ui):
    delete_row(ui, "Gamma")
    delete_row(ui, "Fold")
    T(ui, "sb-more").click()
    T(ui, "trash-open").click()
    expect(T(ui, "trash-row")).to_have_count(2)
    T(ui, "trash-forever").first.click()
    expect(T(ui, "confirm-dialog")).to_contain_text("Qaytarib bo'lmaydi")
    ui.keyboard.press("Escape")
    expect(T(ui, "trash-row")).to_have_count(2)                                # bekor qilindi
    T(ui, "trash-forever").first.click()
    T(ui, "confirm-ok").click()
    expect(T(ui, "trash-row")).to_have_count(1)
    T(ui, "trash-empty-btn").click()
    T(ui, "confirm-ok").click()
    expect(T(ui, "trash-empty")).to_be_visible()


def test_deleted_environment_goes_to_trash_and_comes_back(ui):
    ui.click("[data-testid=sb-environments]")
    expect(T(ui, "env-row").filter(has_text="Temp env")).to_be_visible()
    T(ui, "env-row").filter(has_text="Temp env").locator("[data-testid=env-delete], button[aria-label*='chirish']").first.click()
    T(ui, "confirm-ok").click()
    expect(T(ui, "env-row").filter(has_text="Temp env")).to_have_count(0)
    ui.click("[data-testid=sb-collections]")
    T(ui, "sb-more").click()
    T(ui, "trash-open").click()
    expect(T(ui, "trash-row")).to_contain_text("Temp env")
    T(ui, "trash-restore").click()
    expect(T(ui, "trash-empty")).to_be_visible()
    ui.click("[data-testid=trash-dialog] button.primary")
    ui.click("[data-testid=sb-environments]")
    expect(T(ui, "env-row").filter(has_text="Temp env")).to_be_visible()


def test_collection_delete_from_context_menu_shows_request_count_and_goes_to_trash(ui, world):
    ui.locator("[data-name='Alpha']").dblclick()                              # ichidagi tab ham yopilishi kerak
    expect(T(ui, "request-editor")).to_be_visible()
    ui.locator("[data-testid=tree-row][data-name='Col']").click(button="right")
    ui.click("[data-act=delete-collection]")
    expect(T(ui, "confirm-dialog")).to_contain_text("3 ta so'rov")
    expect(T(ui, "confirm-dialog")).to_contain_text("Savatga")
    ui.keyboard.press("Escape")
    expect(T(ui, "confirm-dialog")).to_have_count(0)                                       # overlay to'liq yopilgach qayta bosamiz
    expect(ui.locator("[data-testid=tree-row][data-name='Col']")).to_have_count(1)         # bekor qilindi
    ui.locator("[data-testid=tree-row][data-name='Col']").click(button="right")
    ui.click("[data-act=delete-collection]")
    T(ui, "confirm-ok").click()
    expect(ui.locator("[data-testid=tree-row][data-name='Col']")).to_have_count(0)
    expect(T(ui, "request-editor")).to_have_count(0)
    T(ui, "sb-more").click()
    T(ui, "trash-open").click()
    expect(T(ui, "trash-row")).to_contain_text("Col")
    expect(T(ui, "trash-row")).to_contain_text("3 ta so'rov")
    T(ui, "trash-restore").click()
    expect(T(ui, "trash-empty")).to_be_visible()
    ui.click("[data-testid=trash-dialog] button.primary")
    expect(ui.locator("[data-testid=tree-row][data-name='Col']")).to_have_count(1)
