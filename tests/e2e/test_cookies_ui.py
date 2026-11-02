"""Bosqich 2 / Cookie'lar va sozlamalar UI."""
import json
import re

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import eventually

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def run(p, url, status="200"):
    """Yuboradi; /run_one javobini qaytaradi (eski natija bilan adashmaslik uchun)."""
    p.fill("[data-testid=url]", url)
    with p.expect_response(lambda r: r.url.endswith("/run_one")) as info:
        T(p, "send").click()
    d = info.value.json()
    assert str(d["status"]) == status, d
    return d


def new_tab(p):
    T(p, "new-tab").click()


def test_response_cookies_tab_and_jar_roundtrip(ui, echo_server):
    new_tab(ui)
    run(ui, echo_server + "/cookie/set?name=sid&value=abc&httponly=1")
    expect(T(ui, "rp-cookies-tab")).to_contain_text("Cookies (1)")
    T(ui, "rp-cookies-tab").click()
    row = T(ui, "rp-cookie-row")
    expect(row).to_contain_text("sid")
    expect(row).to_contain_text("abc")
    expect(row).to_contain_text("HttpOnly")
    d = run(ui, echo_server + "/cookie/echo")
    assert d["response"] == {"sid": "abc"}                                       # jar avtomatik yubordi
    T(ui, "rp-cookies-tab").click()
    expect(T(ui, "rp-cookies")).to_contain_text("cookie o'rnatmadi")


def test_cookie_manager_lists_edits_deletes(ui, echo_server):
    new_tab(ui)
    run(ui, echo_server + "/cookie/set?name=sid&value=abc")
    T(ui, "cookies-btn").click()
    expect(T(ui, "cookies-tab")).to_be_visible()
    expect(T(ui, "cookie-domain")).to_have_attribute("data-domain", "127.0.0.1")
    expect(T(ui, "cookie-row")).to_have_count(1)
    T(ui, "cookie-value").fill("changed")
    T(ui, "cookie-value").press("Tab")                                          # change -> serverga saqlanadi
    ui.locator("[data-testid=tab]").first.click()
    assert run(ui, echo_server + "/cookie/echo")["response"] == {"sid": "changed"}
    T(ui, "cookies-btn").click()
    T(ui, "cookie-del").click()
    expect(T(ui, "cookies-empty")).to_be_visible()
    ui.locator("[data-testid=tab]").first.click()
    assert run(ui, echo_server + "/cookie/echo")["response"] == {}


def test_cookie_manager_add_domain_delete_and_clear_all(ui, echo_server):
    T(ui, "cookies-btn").click()
    expect(T(ui, "cookies-empty")).to_be_visible()
    for dom, name in (("a.test", "x"), ("a.test", "y"), ("b.test", "z")):
        T(ui, "cookie-add-domain").fill(dom)
        T(ui, "cookie-add-name").fill(name)
        T(ui, "cookie-add-value").fill("1")
        T(ui, "cookie-add").click()
        expect(T(ui, "cookie-row").filter(has=ui.locator("b", has_text=re.compile(f"^{name}$")))).to_have_count(1)
    expect(T(ui, "cookie-domain")).to_have_count(2)
    T(ui, "cookie-domain").first.locator("[data-testid=cookie-domain-del]").click()
    T(ui, "confirm-ok").click()
    expect(T(ui, "cookie-domain")).to_have_count(1)
    T(ui, "cookies-clear").click()
    T(ui, "confirm-ok").click()
    expect(T(ui, "cookies-empty")).to_be_visible()


def test_cookie_manager_validation_toast(ui):
    T(ui, "cookies-btn").click()
    T(ui, "cookie-add").click()
    expect(ui.locator(".toast")).to_contain_text("domain")


def test_request_setting_use_cookies_off(ui, echo_server):
    new_tab(ui)
    run(ui, echo_server + "/cookie/set?name=k&value=v")
    ui.click("[data-section=settings]")
    ui.select_option("[data-testid=set-use_cookies]", "false")
    assert run(ui, echo_server + "/cookie/echo")["response"] == {}               # jar o'chiq: yuborilmaydi
    ui.select_option("[data-testid=set-use_cookies]", "")
    assert run(ui, echo_server + "/cookie/echo")["response"] == {"k": "v"}


def test_follow_redirects_and_max_redirects_in_request_settings(ui, echo_server):
    new_tab(ui)
    ui.click("[data-section=settings]")
    expect(T(ui, "set-follow_redirects")).to_contain_text("Sukut (yoqilgan)")
    run(ui, echo_server + "/redirect")                                          # sukut: ergashadi -> 200
    ui.select_option("[data-testid=set-follow_redirects]", "false")
    d = run(ui, echo_server + "/redirect", status="302")
    assert d["resp_headers"]["location"].endswith("/echo")
    ui.select_option("[data-testid=set-follow_redirects]", "")
    T(ui, "set-max_redirects").fill("2")
    d = run(ui, echo_server + "/redir/6", status="ERR")
    assert "redirect" in d["response"].lower()


def test_global_settings_apply_and_request_overrides(ui, echo_server, app):
    T(ui, "settings-btn").click()
    expect(T(ui, "gset-form")).to_be_visible()
    ui.select_option("[data-testid=gset-follow_redirects]", "false")
    T(ui, "gset-save").click()
    expect(T(ui, "gset-save")).to_be_disabled()
    assert app.api("GET", "/api/workspace")["meta"]["settings"] == {"follow_redirects": False}
    new_tab(ui)
    run(ui, echo_server + "/redirect", status="302")                            # global ta'sir qiladi
    ui.click("[data-section=settings]")
    expect(T(ui, "set-follow_redirects")).to_contain_text("Sukut (o'chirilgan)")
    ui.select_option("[data-testid=set-follow_redirects]", "true")              # so'rov globalni bosadi
    run(ui, echo_server + "/redirect", status="200")


def test_request_settings_persist_with_save_and_reload(ui, echo_server, app):
    cid = app.api("POST", "/api/collections", {"name": "S"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "s1", "name": "SReq", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/redirect"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='SReq']").dblclick()
    ui.click("[data-section=settings]")
    ui.select_option("[data-testid=set-follow_redirects]", "false")
    T(ui, "set-proxy").fill("")
    T(ui, "set-max_redirects").fill("4")
    T(ui, "save").click()
    eventually(lambda: app.api("GET", f"/api/collections/{cid}")["item"][0].get("x-apirunner", {}).get("settings") == {"follow_redirects": False, "max_redirects": 4})
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='SReq']").dblclick()
    ui.click("[data-section=settings]")
    expect(T(ui, "set-follow_redirects")).to_have_value("false")
    expect(T(ui, "set-max_redirects")).to_have_value("4")
    run(ui, echo_server + "/redirect", status="302")


def test_settings_apply_in_batch(ui, echo_server):
    new_tab(ui)
    ui.fill("[data-testid=url]", echo_server + "/redirect")
    ui.click("[data-section=settings]")
    ui.select_option("[data-testid=set-follow_redirects]", "false")
    ui.click("[data-section=batch]")
    T(ui, "batch-run").click()
    expect(T(ui, "result-card").first).to_contain_text("302")
