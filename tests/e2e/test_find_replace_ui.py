"""Find & Replace dialogi: qidirish, oldindan ko'rish, tanlab almashtirish, zaxira, xatolar."""
import os

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def world(app):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    r = lambda i, n, url, hv: {"id": i, "name": n, "request": {"method": "GET", "header": [{"key": "X-Host", "value": hv}], "url": {"raw": url}}, "response": []}  # noqa: E731
    col["item"] = [r("a", "Alpha", "https://old.test/a", "old.test"), r("b", "Beta", "https://old.test/b", "keep")]
    app.api("PUT", f"/api/collections/{cid}", col)
    eid = app.api("POST", "/api/environments", {"name": "Dev"})["id"]
    e = app.api("GET", f"/api/environments/{eid}")
    e["values"] = [{"key": "k", "value": "old.test-secret", "enabled": True, "type": "secret"}]
    app.api("PUT", f"/api/environments/{eid}", e)
    return cid


@pytest.fixture
def ui(app, page, world):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    T(page, "sb-more").click()
    T(page, "find-open").click()
    expect(T(page, "fr-dialog")).to_be_visible()
    return page


def urls(app, cid):
    return [i["request"]["url"]["raw"] for i in app.api("GET", f"/api/collections/{cid}")["item"]]


def test_search_shows_grouped_preview_and_masks_secret(ui):
    T(ui, "fr-query").fill("old.test")
    T(ui, "fr-replacement").fill("new.test")
    expect(T(ui, "fr-group")).to_have_count(3)                                # Alpha, Beta, Dev muhiti
    expect(T(ui, "fr-summary")).to_contain_text("ta maydon tanlangan")
    snip = T(ui, "fr-snippet").first
    expect(snip.locator("del")).to_have_text("old.test")
    expect(snip.locator("ins")).to_have_text("new.test")
    expect(T(ui, "fr-dialog")).to_contain_text("maxfiy qiymat")
    expect(T(ui, "fr-dialog")).not_to_contain_text("old.test-secret")


def test_apply_only_selected_rows_with_confirmation_and_backup(ui, app, world):
    T(ui, "fr-query").fill("old.test")
    T(ui, "fr-replacement").fill("new.test")
    T(ui, "fr-target-environments").uncheck()
    expect(T(ui, "fr-group")).to_have_count(2)
    ui.locator("[data-testid=fr-row]", has_text="Header · X-Host").first.locator("input").uncheck()    # Alpha header qoldiriladi
    T(ui, "fr-apply").click()
    expect(T(ui, "confirm-dialog")).to_contain_text("avtomatik zaxira")
    ui.keyboard.press("Escape")
    assert urls(app, world)[0] == "https://old.test/a"                         # bekor qilindi — hech narsa o'zgarmadi
    T(ui, "fr-apply").click()
    T(ui, "confirm-ok").click()
    expect(ui.locator("text=Zaxira:").first).to_be_visible()
    assert urls(app, world) == ["https://new.test/a", "https://new.test/b"]
    col = app.api("GET", f"/api/collections/{world}")
    assert [i["request"]["header"][0]["value"] for i in col["item"]] == ["old.test", "keep"]
    assert any("pre-find-replace" in b for b in os.listdir(app.tmp / "backups"))
    expect(T(ui, "fr-group")).to_have_count(1)                                 # qolgan (header) hali topiladi


def test_scope_regex_error_and_empty_state(ui, world):
    T(ui, "fr-query").fill("(")
    T(ui, "fr-regex").click()
    expect(T(ui, "fr-error")).to_contain_text("Regex")
    T(ui, "fr-regex").click()
    T(ui, "fr-query").fill("zzz-nothing")
    expect(T(ui, "fr-none")).to_be_visible()
    T(ui, "fr-query").fill("old.test")
    T(ui, "fr-scope").select_option(world)
    expect(T(ui, "fr-group")).to_have_count(2)                                 # muhit chiqarib tashlandi


def test_palette_opens_find_replace(app, page, world):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.keyboard.press("Control+k")
    page.keyboard.type("Find")
    page.keyboard.press("Enter")
    expect(T(page, "fr-dialog")).to_be_visible()
