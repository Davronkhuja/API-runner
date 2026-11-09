"""Docs paneli: so'rov o'ng tomonida Markdown tavsif (xavfsiz render), collection/papka Overview'da."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
MD = "# Qo'llanma\n\nBu **muhim** so'rov: `GET /users`.\n\n- bir\n- ikki\n\n[hujjat](https://example.com/docs)\n\n<script>window.__pwned = 1</script>\n\n[xss](javascript:window.__pwned=2)"


@pytest.fixture
def world(app):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "r1", "name": "Users", "request": {"method": "GET", "header": [], "url": {"raw": "http://x.test/users"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    return cid


@pytest.fixture
def ui(app, page, world):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.locator("[data-name='Users']").dblclick()
    expect(T(page, "request-editor")).to_be_visible()
    return page


def request_of(app, cid):
    return app.api("GET", f"/api/collections/{cid}")["item"][0]["request"]


def test_request_docs_edit_render_safely_and_persist(ui, app, world):
    expect(T(ui, "docs-side")).to_have_count(0)
    T(ui, "docs-btn").click()
    expect(T(ui, "req-docs-empty")).to_be_visible()
    T(ui, "req-docs-edit").click()
    T(ui, "req-docs-text").fill(MD)
    expect(T(ui, "save")).to_be_enabled()
    T(ui, "req-docs-view").click()
    html = T(ui, "req-docs-html")
    expect(html.locator("h1")).to_have_text("Qo'llanma")
    expect(html.locator("strong")).to_have_text("muhim")
    expect(html.locator("li")).to_have_count(2)
    expect(html.locator("a[href='https://example.com/docs']")).to_have_attribute("rel", "noopener noreferrer")
    expect(html.locator("script")).to_have_count(0)
    expect(html.locator("a[href^='javascript']")).to_have_count(0)
    assert ui.evaluate("window.__pwned") is None
    T(ui, "save").click()
    expect(T(ui, "save")).to_be_disabled()
    assert request_of(app, world)["description"] == MD
    expect(T(ui, "docs-btn").locator(".dot-on")).to_be_visible()


def test_docs_panel_state_and_content_survive_reload(ui, app, world):
    T(ui, "docs-btn").click()
    T(ui, "req-docs-edit").click()
    T(ui, "req-docs-text").fill("# Saqlangan")
    T(ui, "save").click()
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    expect(T(ui, "req-docs-html").locator("h1")).to_have_text("Saqlangan")


def test_postman_object_description_is_read(app, page, world):
    col = app.api("GET", f"/api/collections/{world}")
    col["item"][0]["request"]["description"] = {"content": "## Postman tavsif", "type": "text/markdown"}
    app.api("PUT", f"/api/collections/{world}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.locator("[data-name='Users']").dblclick()
    T(page, "docs-btn").click()
    expect(T(page, "req-docs-html").locator("h2")).to_have_text("Postman tavsif")


def test_collection_overview_description_is_markdown(ui, app, world):
    ui.locator("[data-name='Col']").dblclick()
    expect(T(ui, "node-overview")).to_be_visible()
    T(ui, "scope-desc").fill("## Hamma uchun\n\n*muhim*")
    T(ui, "scope-save").click() if T(ui, "scope-save").count() else ui.keyboard.press("ControlOrMeta+s")
    ui.wait_for_timeout(400)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='Col']").dblclick()
    expect(T(ui, "scope-docs-html").locator("h2")).to_have_text("Hamma uchun")
