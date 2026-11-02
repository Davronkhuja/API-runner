"""Ma'lumot xavfsizligi — UI tomoni: zaxiralar, ogohlantirish, Default xabari, localStorage tegilmasligi."""
import json
import re

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import App

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
SEED = [("a", "Alfa", None), ("b", "Beta", None)]

LS = {
    "apiRunnerEnvs": json.dumps([{"id": "e1", "name": "Prod", "vars": {"host": "api.io"}},
                                 {"id": "ed", "name": "Default", "vars": {"dkey": "dval"}}]),
    "apiRunnerEnvVars": json.dumps({"legacyvar": "1"}),
    "apiRunnerHistory": json.dumps([{"method": "GET", "url": "http://h1", "timestamp": 1700000000000}]),
    "apiRunnerUrlHistory": json.dumps(["http://a", "http://b"]),
}


def init_ls(page, ls):
    page.add_init_script("(d => { if (!sessionStorage.getItem('__seeded')) { for (const k in d) localStorage.setItem(k, d[k]); sessionStorage.setItem('__seeded', '1') } })(%s)" % json.dumps(ls))


def ls_dump(page):
    return page.evaluate("() => Object.fromEntries(Object.keys(localStorage).filter(k => k.startsWith('apiRunner')).map(k => [k, localStorage.getItem(k)]))")


def test_settings_backups_create_list_and_restore(app, page):
    app.seed(SEED)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=tree-row][data-name=Alfa]")
    T(page, "settings-btn").click()
    expect(T(page, "settings-tab")).to_be_visible()
    n0 = T(page, "backup-row").count()
    T(page, "backup-create").click()
    expect(T(page, "backup-row")).to_have_count(n0 + 1)
    name = T(page, "backup-row").first.get_attribute("data-name")
    assert re.match(r"^\d{8}-\d{6}(-\d+)?_v[\w.\-]+_manual$", name)
    # zaxiradan keyin o'zgartirish
    app.api("POST", "/saved/request", {"name": "FAQAT-KEYIN"})
    page.reload()
    page.wait_for_selector("[data-testid=tree-row][data-name=FAQAT-KEYIN]")
    T(page, "settings-btn").click()
    T(page, "backup-row").filter(has_text=name).locator("[data-testid=backup-restore]").click()
    T(page, "confirm-ok").click()
    page.wait_for_selector("[data-testid=tree-row][data-name=Alfa]")                       # sahifa qayta yuklanadi
    expect(page.locator("[data-testid=tree-row][data-name=FAQAT-KEYIN]")).to_have_count(0)
    names = [r["name"] for r in app.api("GET", "/api/backups")]
    assert any(n.endswith("_pre-restore") for n in names)                                  # joriy holat ham zaxiralangan


def test_migration_rollback_warning_banner(tmp_path, page, monkeypatch):
    import apirunner.storage.migrations as m
    (tmp_path / "saved_requests.json").write_text(json.dumps({"folders": [], "requests": [{"id": "r", "name": "X"}]}))
    monkeypatch.setattr(m, "migrate_saved_requests", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sinov xatosi")))
    a = App(tmp_path)
    try:
        page.goto(a.url)
        banner = T(page, "migration-warning")
        expect(banner).to_be_visible()
        expect(banner).to_contain_text("Migratsiya bekor qilindi")
    finally:
        a.srv.shutdown()


def test_default_env_notice_once_and_localstorage_untouched(app, page):
    init_ls(page, LS)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    expect(T(page, "toast")).to_contain_text("Eski Default o'zgaruvchilar Globals'ga ko'chirildi")
    g = {v["key"] for v in app.api("GET", "/api/globals")["values"]}
    assert {"dkey", "legacyvar"} <= g
    assert [e["name"] for e in app.api("GET", "/api/workspace")["environments"]] == ["Prod"]
    assert all(ls_dump(page)[k] == v for k, v in LS.items())     # localStorage O'CHIRILMAGAN
    page.reload()
    page.wait_for_selector("[data-testid=app]")
    page.wait_for_load_state("networkidle")                                                  # startup so'rovlari tugadi
    expect(T(page, "toast")).to_have_count(0)                                              # xabar bir marta
    assert all(ls_dump(page)[k] == v for k, v in LS.items())


def test_import_button_twice_no_duplicates_and_keeps_localstorage(app, page):
    init_ls(page, LS)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    h1 = len(app.api("GET", "/api/history"))
    envs1 = len(app.api("GET", "/api/workspace")["environments"])
    for _ in range(2):
        with page.expect_response(lambda r: "/api/import/localstorage" in r.url):
            T(page, "ls-import").click()
    assert len(app.api("GET", "/api/history")) == h1 == 3
    assert len(app.api("GET", "/api/workspace")["environments"]) == envs1 == 1
    assert all(ls_dump(page)[k] == v for k, v in LS.items())


def test_legacy_ui_import_button_keeps_localstorage_and_is_idempotent(app, page):
    init_ls(page, LS)
    page.goto(app.url + "/legacy")
    for _ in range(2):
        with page.expect_response(lambda r: "/api/import/localstorage" in r.url):
            page.click("#lsImportBtn")
    assert len(app.api("GET", "/api/history")) == 3
    assert all(ls_dump(page)[k] == v for k, v in LS.items())


def test_environment_save_conflict_between_two_tabs_shows_error(app, page, browser):
    eid = app.api("POST", "/api/environments", {"name": "E"})["id"]
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.click("[data-testid=sb-environments]")
    T(page, "env-row").click()
    other = app.api("GET", f"/api/environments/{eid}")        # boshqa tab/jarayon avval saqlaydi
    other["name"] = "BOSHQA"
    app.api("PUT", f"/api/environments/{eid}", other)
    T(page, "env-name").fill("MENIKI")
    T(page, "env-save").click()
    expect(T(page, "toast")).to_contain_text("boshqa tab")
    assert app.api("GET", f"/api/environments/{eid}")["name"] == "BOSHQA"    # ustidan yozilmadi
