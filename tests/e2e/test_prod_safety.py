"""B guruhi: muhit turi (Dev/Test/Prod), Prod belgisi, yozuvchi so'rovlar tasdig'i, Runner faqat-GET va RunGuard."""
import pytest
import requests
from playwright.sync_api import expect

from conftest import E2E_TOKEN

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


def req(iid, name, method, url):
    return {"id": iid, "name": name, "request": {"method": method, "header": [], "url": {"raw": url}}, "response": []}


@pytest.fixture
def world(app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [req("g1", "Get1", "GET", echo_server + "/echo?a=1"), req("g2", "Get2", "GET", echo_server + "/echo?a=2"),
                   req("p1", "Post1", "POST", echo_server + "/echo"), req("d1", "Del1", "DELETE", echo_server + "/echo")]
    app.api("PUT", f"/api/collections/{cid}", col)
    return cid


def make_env(app, name, kind=None, confirm=None, active=True):
    body = {"name": name}
    if kind is not None:
        body["kind"] = kind
    if confirm is not None:
        body["confirm_writes"] = confirm
    eid = app.api("POST", "/api/environments", body)["id"]
    if active:
        app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    return eid


def start(app, page, counter=None):
    if counter is not None:
        page.on("request", lambda r: counter.append(r.url) if r.url.endswith("/run_one") else None)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")


def open_req(p, name):
    p.locator(f"[data-name='{name}']").dblclick()
    expect(T(p, "request-editor")).to_be_visible()


def open_runner(p):
    p.locator("[data-name='Col']").click(button="right")
    p.click("[data-act=runner]")
    expect(T(p, "runner-tab")).to_be_visible()


# ── muhit turi ──
def test_env_kind_and_confirm_setting_are_saved_and_validated(app, world, page):
    eid = make_env(app, "E1", active=False)
    start(app, page)
    T(page, "sb-environments").click()
    page.locator("[data-testid=env-row], .tree-row", has_text="E1").first.dblclick()
    expect(T(page, "env-tab")).to_be_visible()
    expect(T(page, "env-confirm-writes")).not_to_be_checked()
    page.click("[data-kind=prod]")
    expect(T(page, "env-confirm-writes")).to_be_checked()                       # Prod uchun sukut bo'yicha yoqiq
    T(page, "env-save").click()
    saved = app.api("GET", f"/api/environments/{eid}")
    assert saved["kind"] == "prod" and saved["confirm_writes"] is True
    r = requests.put(app.url + f"/api/environments/{eid}", json={**saved, "kind": "staging"}, headers={"X-Session-Token": E2E_TOKEN})
    assert r.status_code == 400


def test_prod_badge_only_for_prod_env(app, world, page):
    make_env(app, "Prod env", kind="prod")
    start(app, page)
    expect(T(page, "prod-badge")).to_be_visible()
    expect(T(page, "prod-badge")).to_contain_text("PROD")
    page.select_option("[data-testid=env-select]", label="Prod env")
    app.api("POST", "/api/environments", {"name": "Dev env", "kind": "dev"})
    page.reload()
    page.wait_for_selector("[data-testid=app]")
    page.select_option("[data-testid=env-select]", label="Dev env")
    expect(T(page, "prod-badge")).to_have_count(0)


# ── yozuvchi so'rovlar tasdig'i ──
def test_post_on_prod_needs_confirmation_and_cancel_sends_nothing(app, world, page):
    make_env(app, "Prod", kind="prod")
    sent = []
    start(app, page, sent)
    open_req(page, "Post1")
    T(page, "send").click()
    expect(T(page, "confirm-dialog")).to_contain_text("POST")
    expect(T(page, "confirm-dialog")).to_contain_text("Prod")
    page.click("[data-testid=confirm-dialog] button:not(.primary)")             # Bekor qilish
    page.wait_for_timeout(400)
    assert sent == []                                                            # tasdiqsiz POST yuborilmadi
    expect(T(page, "resp-status")).to_have_count(0)
    T(page, "send").click()
    T(page, "confirm-ok").click()
    expect(T(page, "resp-status")).to_have_text("200")
    assert len(sent) == 1


def test_delete_on_prod_confirms_but_get_does_not(app, world, page):
    make_env(app, "Prod", kind="prod")
    sent = []
    start(app, page, sent)
    open_req(page, "Get1")
    T(page, "send").click()
    expect(T(page, "resp-status")).to_have_text("200")
    expect(T(page, "confirm-dialog")).to_have_count(0)
    open_req(page, "Del1")
    T(page, "send").click()
    expect(T(page, "confirm-dialog")).to_contain_text("DELETE")
    assert len(sent) == 1


def test_confirmation_follows_the_env_setting_not_only_the_kind(app, world, page):
    make_env(app, "Prod no confirm", kind="prod", confirm=False)
    start(app, page)
    open_req(page, "Post1")
    T(page, "send").click()
    expect(T(page, "resp-status")).to_have_text("200")
    expect(T(page, "confirm-dialog")).to_have_count(0)


def test_dev_env_with_confirm_enabled_asks_and_no_env_never_asks(app, world, page):
    make_env(app, "Dev strict", kind="dev", confirm=True)
    start(app, page)
    open_req(page, "Post1")
    T(page, "send").click()
    expect(T(page, "confirm-dialog")).to_be_visible()
    page.click("[data-testid=confirm-dialog] button:not(.primary)")
    page.select_option("[data-testid=env-select]", value="")
    T(page, "send").click()
    expect(T(page, "resp-status")).to_have_text("200")


# ── Runner ──
def test_runner_opens_with_only_get_checked(app, world, page):
    make_env(app, "Dev", kind="dev")
    start(app, page)
    open_runner(page)
    expect(T(page, "runner-selcount")).to_have_text("2 / 4 tanlangan")
    for row in page.locator("[data-testid=runner-item]").all():
        on = row.locator("input[type=checkbox]").is_checked()
        assert on == ("GET" in row.inner_text())


def test_runner_on_non_prod_runs_without_guard(app, world, page):
    make_env(app, "Dev", kind="dev")
    start(app, page)
    open_runner(page)
    T(page, "runner-run").click()
    expect(T(page, "runner-row")).to_have_count(2)
    expect(T(page, "runguard")).to_have_count(0)


def test_runguard_get_only_runs_just_gets(app, world, page):
    make_env(app, "Prod", kind="prod")
    start(app, page)
    open_runner(page)
    page.locator("[data-testid=runner-item]", has_text="Post1").locator("input[type=checkbox]").check()   # POST ham belgilangan
    T(page, "runner-run").click()
    g = T(page, "runguard")
    expect(g).to_be_visible()
    expect(T(page, "rg-count-GET")).to_contain_text("2")
    expect(T(page, "rg-count-POST")).to_contain_text("1")
    expect(T(page, "rg-get")).to_be_checked()                                     # tavsiya etilgan variant tanlangan
    T(page, "rg-run").click()
    expect(T(page, "runner-row")).to_have_count(2)
    expect(page.locator("[data-testid=runner-row] .m-POST")).to_have_count(0)


def test_runguard_all_is_blocked_until_prod_is_typed(app, world, page):
    make_env(app, "Prod", kind="prod")
    start(app, page)
    open_runner(page)
    page.locator("[data-testid=runner-item]", has_text="Post1").locator("input[type=checkbox]").check()
    T(page, "runner-run").click()
    T(page, "rg-all").check()
    btn = T(page, "rg-run-all")
    expect(btn).to_be_disabled()
    T(page, "rg-type").fill("pro")
    expect(btn).to_be_disabled()
    T(page, "rg-type").fill("PROD1")
    expect(btn).to_be_disabled()
    expect(T(page, "runner-row")).to_have_count(0)                                 # hali hech narsa yuborilmadi
    T(page, "rg-type").fill("prod")
    expect(btn).to_be_enabled()
    btn.click()
    expect(T(page, "runner-row")).to_have_count(3)
    expect(page.locator("[data-testid=runner-row] .m-POST")).to_have_count(1)


def test_runguard_cancel_runs_nothing(app, world, page):
    make_env(app, "Prod", kind="prod")
    sent = []
    start(app, page, sent)
    open_runner(page)
    T(page, "runner-run").click()
    T(page, "rg-cancel").click()
    expect(T(page, "runguard")).to_have_count(0)
    page.wait_for_timeout(300)
    assert sent == []
