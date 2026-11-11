"""Proxy capture UI: ishga tushirish, ushlash, collection'ga saqlash, to'xtatish."""
import pytest
import requests
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page, echo_server):
    app.api("POST", "/api/collections", {"name": "Capture target"})
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.echo, page.app = echo_server, app
    return page


def test_capture_and_save_to_collection(ui):
    T(ui, "proxy-open").click()
    expect(T(ui, "proxy-dialog")).to_be_visible()
    T(ui, "proxy-start").click()
    expect(T(ui, "proxy-status")).to_have_text("Ishlayapti")
    expect(T(ui, "proxy-log-empty")).to_be_visible()
    proxy = T(ui, "proxy-url").inner_text()
    requests.get(ui.echo + "/echo?z=1", proxies={"http": proxy})
    requests.post(ui.echo + "/echo", json={"a": 1}, proxies={"http": proxy})
    expect(T(ui, "proxy-entry")).to_have_count(2, timeout=6000)
    expect(T(ui, "proxy-save")).to_contain_text("Hammasini saqlash (2)")
    T(ui, "proxy-pick").first.check()
    expect(T(ui, "proxy-save")).to_contain_text("Tanlanganlarni saqlash (1)")
    T(ui, "proxy-save").click()
    expect(ui.locator("[data-testid=toast]").first).to_contain_text("1 ta so'rov")
    cols = ui.app.api("GET", "/api/workspace")["collections"]
    cid = next(c["id"] for c in cols if c["name"] == "Capture target")
    col = ui.app.api("GET", f"/api/collections/{cid}")
    assert col["item"][-1]["name"] == "Ushlangan so'rovlar" and len(col["item"][-1]["item"]) == 1
    T(ui, "proxy-stop").click()
    expect(T(ui, "proxy-start")).to_be_visible()
    with pytest.raises(requests.ConnectionError):
        requests.get(ui.echo + "/echo", proxies={"http": proxy}, timeout=1)


def test_busy_port_shows_error(ui):
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    T(ui, "proxy-open").click()
    T(ui, "proxy-port").fill(str(s.getsockname()[1]))
    T(ui, "proxy-start").click()
    expect(T(ui, "proxy-error")).to_contain_text("band")
    s.close()
