"""B guruhi: muhit turi (Dev/Test/Prod), Prod belgisi, yozuvchi so'rovlar tasdig'i, Runner faqat-GET va RunGuard."""
import pytest
import requests
from playwright.sync_api import expect

from tests.e2e.conftest import eventually

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








# ── Runner ──
def checked_methods(p):
    return sorted({r.locator(".m").inner_text().strip() for r in p.locator("[data-testid=runner-item]").all() if r.locator("input[type=checkbox]").is_checked()})








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


# ── Runner: xavfsizlik so'rovning o'ziga qaraydi (v3.0.1) ──
def set_safety(app, **kw):
    app.api("PUT", "/api/workspace/meta", {"safety": {"test_hosts": [], "prod_hosts": [], "skip_hosts": [], "single_confirm": False, "dev_runner_writes": False, **kw}})


@pytest.mark.parametrize("kind", [None, "dev", "test", "prod"])
def test_runner_selects_only_safe_methods_by_default_for_any_env(app, world, page, kind):
    if kind:
        make_env(app, "E", kind=kind)
    start(app, page)
    open_runner(page)
    expect(T(page, "runner-selcount")).to_have_text("2 / 4 tanlangan")
    assert checked_methods(page) == ["GET"]


def test_dev_exception_only_when_allowed_in_settings(app, world, page):
    make_env(app, "Dev", kind="dev")
    set_safety(app, dev_runner_writes=True)
    start(app, page)
    open_runner(page)
    expect(T(page, "runner-selcount")).to_have_text("4 / 4 tanlangan")
    make_env(app, "Prod", kind="prod")                                                  # Prod'da ruxsat ishlamaydi
    page.reload()
    page.wait_for_selector("[data-testid=app]")
    open_runner(page)
    expect(T(page, "runner-selcount")).to_have_text("2 / 4 tanlangan")


def test_no_env_and_absolute_prod_urls_select_only_gets_and_delete_triggers_guard(app, page):
    cid = app.api("POST", "/api/collections", {"name": "ProdCol"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [req("a", "ListA", "GET", "https://hujjat.uz/api/a"), req("b", "ListB", "GET", "https://api.online-mahalla.uz/api/b"),
                   req("c", "CreateC", "POST", "https://hujjat.uz/api/c"), req("d", "RemoveD", "DELETE", "https://api.online-mahalla.uz/api/d"), req("h", "HeadH", "GET", "http://localhost:1/h")]
    app.api("PUT", f"/api/collections/{cid}", col)
    sent = []
    start(app, page, sent)
    page.locator("[data-name='ProdCol']").click(button="right")
    page.click("[data-act=runner]")
    expect(T(page, "runner-selcount")).to_have_text("3 / 5 tanlangan")
    assert checked_methods(page) == ["GET"]
    T(page, "runner-run").click()                                                       # faqat GET — dialog yo'q (muhit ham Prod emas)
    expect(T(page, "runguard")).to_have_count(0)
    T(page, "runner-stop").click() if T(page, "runner-stop").count() else None
    page.locator("[data-testid=runner-item]", has_text="RemoveD").locator("input[type=checkbox]").check()
    T(page, "runner-run").click()
    expect(T(page, "runguard")).to_be_visible()
    expect(T(page, "rg-count-DELETE")).to_contain_text("1")
    hosts = T(page, "rg-host").all_inner_texts()
    assert any("api.online-mahalla.uz" in h and "prod" in h for h in hosts) and any("localhost" in h and "test/dev" in h for h in hosts), hosts
    expect(T(page, "rg-warn")).to_contain_text("api.online-mahalla.uz")
    T(page, "rg-cancel").click()
    assert not [u for u in sent if "online-mahalla" in u]


def test_guard_all_requires_confirm_word_and_get_mode_skips_writes(app, world, page):
    start(app, page)
    open_runner(page)
    page.locator("[data-testid=runner-item]", has_text="Post1").locator("input[type=checkbox]").check()
    T(page, "runner-run").click()
    expect(T(page, "runguard")).to_be_visible()
    T(page, "rg-all").check()
    expect(T(page, "rg-word")).to_have_text("tasdiqlayman")
    expect(T(page, "rg-run-all")).to_be_disabled()
    T(page, "rg-type").fill("tasdiqlayman")
    expect(T(page, "rg-run-all")).to_be_enabled()
    T(page, "rg-get").check()
    T(page, "rg-run").click()
    expect(T(page, "runner-row")).to_have_count(2)
    expect(page.locator("[data-testid=runner-row] .m-POST")).to_have_count(0)


def test_env_kind_is_saved_and_validated(app, world, page):
    eid = make_env(app, "E1", active=False)
    start(app, page)
    T(page, "sb-environments").click()
    page.locator("[data-testid=env-row], .tree-row", has_text="E1").first.dblclick()
    expect(T(page, "env-tab")).to_be_visible()
    page.click("[data-kind=prod]")
    T(page, "env-save").click()
    eventually(lambda: app.api("GET", f"/api/environments/{eid}")["kind"] == "prod")
    saved = app.api("GET", f"/api/environments/{eid}")
    r = requests.put(app.url + f"/api/environments/{eid}", json={**saved, "kind": "staging"}, headers={"X-Session-Token": E2E_TOKEN})
    assert r.status_code == 400


# ── yagona so'rov tasdig'i (v3.0.2: sukut O'CHIQ; yoqilgan bo'lsa faqat DELETE, faqat Prod muhit yoki prod host) ──
def prod_col(app, name="PC"):
    cid = app.api("POST", "/api/collections", {"name": name})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [req("p", "PostP", "POST", "https://api.company.uz/items"), req("u", "PutP", "PUT", "https://api.company.uz/items/1"),
                   req("d", "DelP", "DELETE", "https://api.company.uz/items/1"), req("d2", "DelQ", "DELETE", "https://other.company.uz/items/2")]
    app.api("PUT", f"/api/collections/{cid}", col)
    return cid


def test_plain_post_put_and_default_delete_go_without_confirmation(app, page):
    prod_col(app)
    make_env(app, "Prod", kind="prod")
    for single in (False, True):
        set_safety(app, single_confirm=single, prod_hosts=["api.company.uz"])
        sent = []
        start(app, page, sent)
        for n in ("PostP", "PutP"):                                                     # POST/PUT kundalik ish: Prod + prod host + yoqilgan sozlama bo'lsa ham so'ralmaydi
            open_req(page, n)
            T(page, "send").click()
            page.wait_for_timeout(250)
            expect(T(page, "confirm-dialog")).to_have_count(0)
        eventually(lambda: len(sent) == 2)
    set_safety(app, single_confirm=False, prod_hosts=["api.company.uz"])                # sukut o'chiq: DELETE ham so'ralmaydi
    sent = []
    start(app, page, sent)
    open_req(page, "DelP")
    T(page, "send").click()
    page.wait_for_timeout(250)
    expect(T(page, "confirm-dialog")).to_have_count(0)
    eventually(lambda: len(sent) == 1)


def test_enabled_delete_confirm_only_for_prod_env_or_prod_host(app, page):
    prod_col(app)
    set_safety(app, single_confirm=True, prod_hosts=["api.company.uz"])
    sent = []
    start(app, page, sent)
    open_req(page, "DelQ")                                                              # muhit yo'q, host prod ro'yxatida emas
    T(page, "send").click()
    page.wait_for_timeout(250)
    expect(T(page, "confirm-dialog")).to_have_count(0)
    open_req(page, "DelP")                                                              # prod host
    T(page, "send").click()
    expect(T(page, "confirm-dialog")).to_contain_text("api.company.uz")
    page.click("[data-testid=confirm-dialog] button:not(.primary)")
    n = len(sent)
    page.wait_for_timeout(300)
    assert len(sent) == n                                                               # bekor qilinsa yuborilmadi
    make_env(app, "Prod", kind="prod")                                                  # Prod muhit: DelQ ham so'raydi
    page.reload()
    page.wait_for_selector("[data-testid=app]")
    open_req(page, "DelQ")
    T(page, "send").click()
    expect(T(page, "confirm-dialog")).to_contain_text("Prod")
    T(page, "confirm-ok").click()
    eventually(lambda: len(sent) > n)


def test_dont_ask_again_for_host_persists_and_can_be_undone_in_settings(app, page):
    prod_col(app)
    set_safety(app, single_confirm=True, prod_hosts=["api.company.uz"])
    sent = []
    start(app, page, sent)
    open_req(page, "DelP")
    T(page, "send").click()
    T(page, "confirm-check-host").check()
    T(page, "confirm-ok").click()
    eventually(lambda: app.api("GET", "/api/workspace")["meta"]["safety"]["skip_hosts"] == ["api.company.uz"])
    T(page, "send").click()                                                             # ikkinchi marta — tasdiqsiz
    page.wait_for_timeout(250)
    expect(T(page, "confirm-dialog")).to_have_count(0)
    T(page, "settings-btn").click()
    expect(T(page, "safety-skip-host")).to_contain_text("api.company.uz")
    T(page, "safety-skip-undo").click()
    eventually(lambda: app.api("GET", "/api/workspace")["meta"]["safety"]["skip_hosts"] == [])
    open_req(page, "DelP")
    T(page, "send").click()
    expect(T(page, "confirm-dialog")).to_be_visible()                                   # qaytarib olindi — yana so'raydi


def test_dont_ask_again_this_session_is_not_persisted(app, page):
    prod_col(app)
    set_safety(app, single_confirm=True, prod_hosts=["api.company.uz"])
    start(app, page, [])
    open_req(page, "DelP")
    T(page, "send").click()
    T(page, "confirm-check-session").check()
    T(page, "confirm-ok").click()
    T(page, "send").click()
    page.wait_for_timeout(250)
    expect(T(page, "confirm-dialog")).to_have_count(0)
    assert app.api("GET", "/api/workspace")["meta"]["safety"]["skip_hosts"] == []
    page.reload()                                                                       # yangi sessiya — yana so'raydi
    page.wait_for_selector("[data-testid=app]")
    open_req(page, "DelP")
    T(page, "send").click()
    expect(T(page, "confirm-dialog")).to_be_visible()


def test_safety_settings_ui_saves_hosts_and_single_confirm(app, world, page):
    start(app, page)
    T(page, "settings-btn").click()
    T(page, "safety-hosts").fill("*.corp.test\napi.stage.company.uz")
    T(page, "safety-hosts").blur()
    eventually(lambda: app.api("GET", "/api/workspace")["meta"]["safety"]["test_hosts"] == ["*.corp.test", "api.stage.company.uz"])
    expect(T(page, "safety-single-confirm")).not_to_be_checked()                        # sukut o'chiq
    T(page, "safety-single-confirm").check()
    T(page, "safety-prod-hosts").fill("api.company.uz")
    T(page, "safety-prod-hosts").blur()
    eventually(lambda: (lambda sf: sf["single_confirm"] is True and sf["prod_hosts"] == ["api.company.uz"])(app.api("GET", "/api/workspace")["meta"]["safety"]))


def test_old_host_confirm_flag_is_removed_by_migration(isolated, make_client):
    c = make_client()
    ws = c.app.extensions["workspace"]
    ws.update_meta(safety={"test_hosts": ["x.uz"], "host_confirm": True, "dev_runner_writes": False})          # v3.0.1 holati
    from apirunner.app import create_app
    app2 = create_app(workspace_dir=str(isolated / "workspace"), saved_file=str(isolated / "saved_requests.json"), upload_dir=str(isolated / "uploads"), session_token="t", backup_dir=str(isolated / "backups"))
    sf = app2.extensions["workspace"].meta()["safety"]
    assert "host_confirm" not in sf and sf["single_confirm"] is False and sf["test_hosts"] == ["x.uz"]
