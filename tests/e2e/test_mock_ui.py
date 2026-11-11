"""Mock server UI: ishga tushirish, yo'nalishlar, jurnal, to'xtatish, band port."""
import pytest
import requests
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    cid = app.api("POST", "/api/collections", {"name": "Mockable"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    ex = lambda n, c, b: {"id": "e" + n, "name": n, "code": c, "status": "x", "header": [{"key": "Content-Type", "value": "application/json"}], "body": b, "_postman_previewlanguage": "json"}  # noqa: E731
    col["item"] = [{"id": "r1", "name": "Get user", "request": {"method": "GET", "header": [], "url": {"raw": "{{base}}/users/:id"}}, "response": [ex("found", 200, '{"id": "{{id}}"}')]},
                   {"id": "r2", "name": "No example", "request": {"method": "GET", "header": [], "url": {"raw": "{{base}}/x"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.cid = cid
    return page


def open_mock(p):
    p.locator("[data-testid=tree-row][data-name='Mockable']").click(button="right")
    p.click("[data-act=mock]")
    expect(T(p, "mock-dialog")).to_be_visible()


def test_start_route_table_log_and_stop(ui):
    open_mock(ui)
    T(ui, "mock-start").click()
    expect(T(ui, "mock-status")).to_have_text("Ishlayapti")
    url = T(ui, "mock-url").inner_text()
    expect(T(ui, "mock-routes")).to_contain_text("/users/:id")
    expect(T(ui, "mock-log-empty")).to_be_visible()
    assert requests.get(url + "/users/5").json() == {"id": "5"}
    requests.get(url + "/nothing")
    expect(T(ui, "mock-entry")).to_have_count(2, timeout=6000)
    expect(T(ui, "mock-entry").first).to_contain_text("moslik yo'q")
    ui.click("[data-testid=mock-dialog] button:has-text('Yopish')")                          # dialog yopilsa ham server ishlayveradi
    expect(T(ui, "mock-dialog")).to_have_count(0)
    assert requests.get(url + "/users/6").status_code == 200
    open_mock(ui)
    expect(T(ui, "mock-status")).to_be_visible()
    expect(T(ui, "mock-entry")).to_have_count(3, timeout=6000)
    T(ui, "mock-stop").click()
    expect(T(ui, "mock-start")).to_be_visible()
    with pytest.raises(requests.ConnectionError):
        requests.get(url + "/users/1", timeout=1)


def test_busy_port_shows_error_and_overview_button(ui, app):
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    port = s.getsockname()[1]
    ui.locator("[data-testid=tree-row][data-name='Mockable']").dblclick()
    T(ui, "scope-mock").click()
    T(ui, "mock-port").fill(str(port))
    T(ui, "mock-start").click()
    expect(T(ui, "mock-error")).to_contain_text("band")
    s.close()
    T(ui, "mock-start").click()
    expect(T(ui, "mock-status")).to_be_visible()
    T(ui, "mock-stop").click()


def test_generate_docs_button_downloads_html_for_collection_and_folder(ui, app):
    col = app.api("GET", f"/api/collections/{ui.cid}")
    col["item"].append({"id": "fo", "name": "Sub", "item": [{"id": "r9", "name": "Deep", "request": {"method": "GET", "header": [], "url": {"raw": "{{base}}/deep"}}, "response": []}]})
    app.api("PUT", f"/api/collections/{ui.cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-testid=tree-row][data-name='Mockable']").dblclick()
    with ui.expect_download() as d:
        T(ui, "scope-docs-gen").click()
    assert d.value.suggested_filename == "Mockable.docs.html"
    html = open(d.value.path(), encoding="utf-8").read()
    assert "Get user" in html and "Deep" in html
    ui.locator("[data-testid=tree-row][data-name='Sub']").dblclick()
    with ui.expect_download() as d2:
        T(ui, "scope-docs-gen").click()
    html2 = open(d2.value.path(), encoding="utf-8").read()
    assert "Deep" in html2 and "Get user" not in html2
