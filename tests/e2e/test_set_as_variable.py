"""Belgilangan matndan o'zgaruvchi yaratish ("Set as variable")."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "r1", "name": "Req", "request": {"method": "GET", "header": [], "url": {"raw": "https://api.test/v1/items"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    eid = app.api("POST", "/api/environments", {"name": "Dev"})["id"]
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.locator("[data-name='Req']").dblclick()
    expect(T(page, "request-editor")).to_be_visible()
    return page


def env_values(app):
    ws = app.api("GET", "/api/workspace")
    return {v["key"]: v for e in ws["environments"] for v in e["values"]}


def test_url_selection_becomes_environment_variable_and_is_replaced(ui, app):
    u = T(ui, "url")
    u.click()
    ui.keyboard.press("Home")
    for _ in range(len("https://api.test")):
        ui.keyboard.press("Shift+ArrowRight")
    btn = T(ui, "set-var-btn")
    expect(btn).to_be_visible()
    btn.click()
    expect(T(ui, "setvar-dialog")).to_be_visible()
    expect(T(ui, "setvar-name")).to_have_value("api_test")
    expect(T(ui, "setvar-value")).to_have_value("https://api.test")
    expect(T(ui, "setvar-scope")).to_contain_text("Environment: Dev")
    T(ui, "setvar-ok").click()
    expect(T(ui, "setvar-dialog")).to_have_count(0)
    expect(u).to_have_text("{{api_test}}/v1/items")
    assert env_values(app)["api_test"]["value"] == "https://api.test"


def test_params_value_to_globals_with_key_as_name_hint_and_validation(ui, app):
    ui.click("[data-section=params]")
    ui.locator("[data-cell='0:0']").fill("page_size")
    cell = ui.locator("[data-cell='0:1']")
    cell.fill("250")
    cell.click()
    ui.keyboard.press("ControlOrMeta+a")
    T(ui, "set-var-btn").click()
    expect(T(ui, "setvar-name")).to_have_value("page_size")
    T(ui, "setvar-name").fill("1bad name")
    expect(T(ui, "setvar-error")).to_be_visible()
    expect(T(ui, "setvar-ok")).to_be_disabled()
    T(ui, "setvar-name").fill("page_size")
    T(ui, "setvar-scope").select_option("globals")
    T(ui, "setvar-ok").click()
    expect(cell).to_have_value("{{page_size}}")
    g = {v["key"]: v for v in app.api("GET", "/api/workspace")["globals"]["values"]}
    assert g["page_size"]["value"] == "250"


def test_collection_scope_and_existing_name_warning(ui, app):
    ui.click("[data-section=headers]")
    ui.locator("[data-cell='0:0']").fill("X-Key")
    cell = ui.locator("[data-cell='0:1']")
    cell.fill("k-1")
    cell.click()
    ui.keyboard.press("ControlOrMeta+a")
    T(ui, "set-var-btn").click()
    T(ui, "setvar-scope").select_option("collection")
    T(ui, "setvar-ok").click()
    expect(cell).to_have_value("{{x_key}}")
    cid = app.api("GET", "/api/workspace")["collections"][0]["id"]
    assert any(v["key"] == "x_key" and v["value"] == "k-1" for v in app.api("GET", f"/api/collections/{cid}")["variable"])
    cell.fill("k-2")
    cell.click()
    ui.keyboard.press("ControlOrMeta+a")
    T(ui, "set-var-btn").click()
    T(ui, "setvar-name").fill("x_key")
    T(ui, "setvar-scope").select_option("collection")
    expect(T(ui, "setvar-note")).to_contain_text("qiymati yangilanadi")


def test_no_button_for_empty_selection_or_existing_braces(ui):
    u = T(ui, "url")
    u.click()
    ui.keyboard.press("End")
    expect(T(ui, "set-var-btn")).to_have_count(0)
    ui.keyboard.type("/{{x}}")
    for _ in range(5):
        ui.keyboard.press("Shift+ArrowLeft")
    ui.wait_for_timeout(200)
    expect(T(ui, "set-var-btn")).to_have_count(0)
