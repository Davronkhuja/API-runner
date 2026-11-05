"""`{{` avtoto'ldirish: URL (CodeMirror), Params/Headers (oddiy input), Body (CodeMirror), Auth; scope va qiymat ko'rsatiladi."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "coll_only", "value": "c"}]               # saqlanmagan so'rov collection scope'ini ko'rmaydi
    app.api("PUT", f"/api/collections/{cid}", col)
    eid = app.api("POST", "/api/environments", {"name": "E"})["id"]
    e = app.api("GET", f"/api/environments/{eid}")
    e["values"] = [{"key": "base_url", "value": "https://api.test", "enabled": True, "type": "default"}, {"key": "token", "value": "abc123", "enabled": True, "type": "default"}, {"key": "secret_key", "value": "s3", "enabled": True, "type": "secret"}]
    app.api("PUT", f"/api/environments/{eid}", e)
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    T(page, "new-tab").click()
    return page


def test_url_editor_suggests_with_scope_and_inserts_closed_braces(ui):
    u = T(ui, "url")
    u.click()
    ui.keyboard.type("{{ba", delay=40)
    tip = ui.locator(".cm-tooltip-autocomplete")
    expect(tip).to_be_visible()
    expect(tip).to_contain_text("base_url")
    expect(tip).to_contain_text("Environment")
    expect(tip).not_to_contain_text("token")                                 # filtr
    ui.wait_for_timeout(250)                                                  # CodeMirror interactionDelay
    ui.keyboard.press("Enter")
    expect(u).to_have_text("{{base_url}}")
    ui.keyboard.type("/x")
    expect(u).to_have_text("{{base_url}}/x")


def test_url_editor_dynamic_variables_and_no_popup_without_braces(ui):
    u = T(ui, "url")
    u.click()
    ui.keyboard.type("http://x/ba", delay=30)
    expect(ui.locator(".cm-tooltip-autocomplete")).to_have_count(0)
    ui.keyboard.type("{{$gu", delay=40)
    expect(ui.locator(".cm-tooltip-autocomplete")).to_contain_text("$guid")
    ui.wait_for_timeout(250)
    ui.keyboard.press("Enter")
    expect(u).to_contain_text("{{$guid}}")


def test_params_input_popup_keyboard_navigation_and_secret_is_masked(ui):
    ui.click("[data-section=params]")
    cell = ui.locator("[data-cell='0:1']")
    cell.click()
    ui.keyboard.type("{{", delay=40)
    pop = T(ui, "var-popup")
    expect(pop).to_be_visible()
    expect(pop).to_contain_text("token")
    expect(pop).to_contain_text("abc123")
    expect(pop).to_contain_text("••••")
    expect(pop).not_to_contain_text("s3")                                    # secret qiymati ko'rsatilmaydi
    ui.keyboard.type("tok", delay=40)
    expect(T(ui, "var-option")).to_have_count(1)
    ui.keyboard.press("Enter")
    expect(cell).to_have_value("{{token}}")
    expect(pop).to_have_count(0)
    expect(ui.locator("[data-cell='1:0']")).to_be_visible()                  # Enter satr almashtirmadi (ghost qator bor, tanlov kataklarida qoldi)
    ui.keyboard.press("Escape")


def test_headers_popup_escape_and_mouse_pick(ui):
    ui.click("[data-section=headers]")
    cell = ui.locator("[data-cell='0:1']")
    cell.click()
    ui.keyboard.type("Bearer {{", delay=40)
    expect(T(ui, "var-popup")).to_be_visible()
    ui.keyboard.press("Escape")
    expect(T(ui, "var-popup")).to_have_count(0)
    ui.keyboard.type("to", delay=40)
    T(ui, "var-option").first.click()
    expect(cell).to_have_value("Bearer {{token}}")


def test_body_editor_and_auth_field_complete_too(ui):
    ui.click("[data-section=body]")
    from tests.e2e.conftest import set_body_mode
    set_body_mode(ui, "json")
    body = T(ui, "body-raw")
    body.click()
    ui.keyboard.type('{"k": "{{tok', delay=40)
    expect(ui.locator(".cm-tooltip-autocomplete")).to_contain_text("token")
    ui.wait_for_timeout(250)
    ui.keyboard.press("Enter")
    ui.click("[data-section=auth]")
    ui.select_option("[data-testid=auth-type]", "bearer")
    T(ui, "auth-token").click()
    ui.keyboard.type("{{ba", delay=40)
    expect(T(ui, "var-popup")).to_contain_text("base_url")
    ui.keyboard.press("Tab")
    expect(T(ui, "auth-token")).to_have_value("{{base_url}}")
