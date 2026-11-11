"""Monitor UI: yaratish, cron tekshiruvi, "Hozir" yurgizish (xato/OK), o'chirish/yoqish, tahrirlash."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Monitorable"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "r1", "name": "Ping", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/echo"}}}]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.cid, page.echo, page.app = cid, echo_server, app
    return page


def open_monitor(p):
    T(p, "monitor-open").click()
    expect(T(p, "monitor-dialog")).to_be_visible()


def test_create_validate_run_toggle_edit_delete(ui):
    open_monitor(ui)
    expect(T(ui, "mon-empty")).to_be_visible()
    T(ui, "mon-new").click()
    T(ui, "mon-name").fill("Sog'liq")
    T(ui, "mon-cron").fill("61 * * * *")
    expect(T(ui, "mon-cron-hint")).to_contain_text("0–59")
    expect(T(ui, "mon-save")).to_be_disabled()
    T(ui, "mon-preset").nth(1).click()
    expect(T(ui, "mon-cron")).to_have_value("*/5 * * * *")
    expect(T(ui, "mon-cron-hint")).to_contain_text("Keyingi")
    T(ui, "mon-save").click()
    expect(T(ui, "mon-item")).to_have_count(1)
    expect(T(ui, "mon-item")).to_contain_text("Monitorable")
    T(ui, "mon-run").click()
    expect(T(ui, "mon-last")).to_have_text("OK", timeout=10000)
    runs = ui.app.api("GET", "/api/runs")
    rows = runs["items"] if isinstance(runs, dict) else runs
    assert any(r.get("kind") == "monitor" for r in rows)
    T(ui, "mon-toggle").click()
    expect(T(ui, "mon-item")).to_contain_text("o'chiq")
    T(ui, "mon-edit").click()
    T(ui, "mon-name").fill("Yangi nom")
    T(ui, "mon-save").click()
    expect(T(ui, "mon-item")).to_contain_text("Yangi nom")
    T(ui, "mon-del").click()
    T(ui, "confirm-ok").click()
    expect(T(ui, "mon-empty")).to_be_visible()


def test_failing_monitor_shows_error_status(ui):
    col = ui.app.api("GET", f"/api/collections/{ui.cid}")
    col["item"][0]["request"]["url"]["raw"] = "http://127.0.0.1:1/x"
    ui.app.api("PUT", f"/api/collections/{ui.cid}", col)
    open_monitor(ui)
    T(ui, "mon-new").click()
    T(ui, "mon-name").fill("Buzilgan")
    T(ui, "mon-save").click()
    T(ui, "mon-run").click()
    expect(T(ui, "mon-last")).to_have_text("Xato", timeout=10000)
    expect(T(ui, "mon-item")).to_contain_text("1 xato")
