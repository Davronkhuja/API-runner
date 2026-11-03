"""Papka/collection tabi (Overview | Auth | Variables | Scripts | Run), meros manbasi, ommaviy «Meros» taklifi va qulf belgisi."""
import json
import re

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


def bearer(tok):
    return {"type": "bearer", "bearer": [{"key": "token", "value": tok, "type": "string"}]}


def req(i, name, auth=None):
    r = {"method": "GET", "header": [], "url": {"raw": "{{base}}/echo"}}
    if auth:
        r["auth"] = auth
    return {"id": i, "name": name, "request": r, "response": []}


@pytest.fixture
def world(app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base", "value": echo_server}]
    col["auth"] = bearer("COLTOKEN")
    col["item"] = [
        {"id": "f", "name": "Fold", "item": [req("r1", "Same", bearer("NEW")), req("r2", "Other", bearer("DIFFERENT")), req("r3", "Optout", {"type": "noauth"}), req("r4", "Plain"),
                                             {"id": "s", "name": "Sub", "auth": bearer("SUBTOKEN"), "item": [req("r5", "InSub", bearer("NEW"))]}]},
        {"id": "g", "name": "Other folder", "auth": {"type": "basic", "basic": [{"key": "username", "value": "u"}, {"key": "password", "value": "p"}]}, "item": [req("r6", "Child")]},
        req("r7", "Root"),
    ]
    app.api("PUT", f"/api/collections/{cid}", col)
    return cid


@pytest.fixture
def ui(app, page, world):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def row(p, name):
    return p.locator(f"[data-name='{name}']")


def auth_of(app, cid, rid):
    def walk(items):
        for it in items:
            if it["id"] == rid:
                return it["request"].get("auth")
            if "item" in it:
                r = walk(it["item"])
                if r != "missing":
                    return r
        return "missing"
    return walk(app.api("GET", f"/api/collections/{cid}")["item"])


def set_folder_auth(p, folder, token):
    row(p, folder).click(button="right")
    p.click("[data-act=settings]")
    expect(T(p, "tab-folder")).to_be_visible()
    p.click("[data-scope-section=auth]")
    p.select_option("[data-testid=auth-type]", "bearer")
    T(p, "auth-token").fill(token)
    T(p, "scope-save").click()


# ── Postman kabi tab ──
def test_click_on_folder_and_collection_opens_overview_tab_chevron_only_toggles(ui):
    row(ui, "Fold").click()
    expect(T(ui, "tab-folder")).to_be_visible()
    expect(T(ui, "node-title")).to_have_text("Fold")
    assert ui.locator("[data-testid=scope-sections] button").all_inner_texts()[0:5] == ["Overview", "Auth", "Variables", "Scripts", "Run"]
    expect(ui.locator("[data-testid=tab].preview")).to_have_count(1)                    # kursiv preview tab
    expect(row(ui, "Same")).to_have_count(0)                                           # bosish papkani yopdi ham
    row(ui, "Fold").locator("[data-testid=row-chevron]").click()
    expect(row(ui, "Same")).to_have_count(1)
    expect(ui.locator("[data-testid=tab]")).to_have_count(1)                           # chevron yangi tab ochmadi
    row(ui, "Col").click()
    expect(T(ui, "tab-collection")).to_be_visible()
    expect(ui.locator("[data-testid=tab]")).to_have_count(1)                           # preview tab almashdi
    row(ui, "Col").dblclick()
    expect(ui.locator("[data-testid=tab].preview")).to_have_count(0)                   # ikki marta bosish — doimiy tab


def test_context_menu_remains_with_open_settings_and_runner(ui):
    row(ui, "Fold").click(button="right")
    acts = ui.locator("[data-testid=tree-menu] [data-act]")
    expect(acts).to_have_count(7)
    assert acts.evaluate_all("els => els.map(e => e.dataset.act)") == ["runner", "settings", "newfolder", "rename", "dup", "move", "delete"]
    ui.click("[data-act=settings]")
    expect(T(ui, "tab-folder")).to_be_visible()
    row(ui, "Col").click(button="right")
    expect(ui.locator("[data-testid=tree-menu] [data-act=open]")).to_be_visible()
    ui.click("[data-act=open]")
    expect(T(ui, "tab-collection")).to_be_visible()


def test_overview_summary_auth_description_and_run_tab(ui, app, world):
    row(ui, "Fold").dblclick()
    expect(T(ui, "ov-requests")).to_have_text("5")
    expect(T(ui, "ov-folders")).to_have_text("1")
    expect(T(ui, "ov-auth")).to_contain_text("Meros: Bearer Token («Col»)")
    expect(T(ui, "ov-own-auth")).to_contain_text("3 ta so'rovning o'z auth'i bor")      # Same, Other, InSub (noauth sanalmaydi)
    T(ui, "scope-desc").fill("Papka tavsifi")
    T(ui, "scope-save").click()
    cid = world
    assert json.dumps(app.api("GET", f"/api/collections/{cid}")["item"][0]["x-apirunner"]).count("Papka tavsifi") == 1
    ui.click("[data-scope-section=run]")
    T(ui, "scope-run-open").click()
    expect(T(ui, "runner-tab")).to_be_visible()
    expect(T(ui, "runner-item")).to_have_count(5)                                      # faqat shu papka so'rovlari
    expect(T(ui, "runner-collection")).to_have_text("Fold")


def test_collection_overview_shows_own_auth_and_variable_count(ui):
    row(ui, "Col").dblclick()
    expect(T(ui, "ov-auth")).to_contain_text("Bearer Token")
    expect(T(ui, "ov-vars")).to_contain_text("1")
    expect(T(ui, "ov-requests")).to_have_text("7")


# ── Meros manbasi ──
def test_request_auth_tab_shows_inheritance_source_with_link_to_it(ui):
    row(ui, "Fold").click()                                                            # papka ochiq bo'lsin (Same ko'rinsin)
    row(ui, "Fold").locator("[data-testid=row-chevron]").click()
    row(ui, "Plain").dblclick()
    ui.click("[data-section=auth]")
    expect(T(ui, "auth-type")).to_have_value("inherit")
    expect(T(ui, "auth-inherit-src")).to_contain_text("«Col» collection'dan")          # Fold'da auth yo'q → collection'dan
    expect(T(ui, "auth-inherit-type")).to_have_text("Bearer Token")
    expect(T(ui, "auth-inherit-note")).to_contain_text("bearer")
    T(ui, "auth-inherit-link").click()
    expect(T(ui, "tab-collection")).to_be_visible()
    expect(T(ui, "auth-panel")).to_be_visible()                                         # Auth bo'limi ochilgan
    # papkadan merosi bor so'rov
    row(ui, "Child").dblclick() if row(ui, "Child").count() else None


def test_inheritance_source_names_the_nearest_folder_and_link_opens_its_auth_tab(ui, app, world):
    row(ui, "Child").dblclick()
    ui.click("[data-section=auth]")
    expect(T(ui, "auth-inherit-src")).to_contain_text("«Other folder» papkasidan")
    expect(T(ui, "auth-inherit-type")).to_have_text("Basic Auth")
    expect(T(ui, "auth-inherit-link")).to_have_text("Papkaga o'tish")
    T(ui, "auth-inherit-link").click()
    expect(T(ui, "tab-folder")).to_be_visible()
    expect(T(ui, "node-title")).to_have_text("Other folder")
    expect(T(ui, "auth-type")).to_have_value("basic")


def test_inherit_note_when_nothing_above_has_auth(app, page):
    cid = app.api("POST", "/api/collections", {"name": "Bare"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [req("x", "Lone")]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    row(page, "Lone").dblclick()
    page.click("[data-section=auth]")
    expect(T(page, "auth-inherit-note")).to_contain_text("auth yo'q")
    expect(T(page, "auth-inherit-link")).to_have_count(0)


# ── ommaviy «Meros» taklifi ──
def test_bulk_offer_detects_same_token_requests_and_applies_selected_with_backup(ui, app, world):
    cid = world
    row(ui, "Fold").locator("[data-testid=row-chevron]").click() if row(ui, "Same").count() == 0 else None
    before = len(app.api("GET", "/api/backups"))
    set_folder_auth(ui, "Fold", "NEW")
    dlg = T(ui, "bulk-auth-dialog")
    expect(dlg).to_be_visible()
    expect(T(ui, "bulk-auth-count")).to_have_text("3")                                  # Same, Other, Optout (Sub ichidagi InSub o'z papka auth'i bilan to'silgan)
    rows = T(ui, "bulk-auth-row")
    expect(rows).to_have_count(3)
    expect(rows.filter(has_text="Same").locator("[data-testid=bulk-auth-same]")).to_have_text("bir xil")
    expect(rows.filter(has_text="Same").locator("input")).to_be_checked()               # bir xil token avtomatik tanlangan
    expect(rows.filter(has_text="Other").locator("input")).not_to_be_checked()
    expect(rows.filter(has_text="Optout").locator("input")).not_to_be_checked()
    expect(T(ui, "bulk-auth-backup-note")).to_contain_text("zaxira")
    T(ui, "bulk-auth-apply").click()
    expect(ui.locator(".toast")).to_contain_text("1 ta so'rov «Meros»ga o'tkazildi")
    expect(dlg).to_have_count(0)
    assert len(app.api("GET", "/api/backups")) == before + 1 and any("pre-bulk-auth" in b["name"] for b in app.api("GET", "/api/backups"))
    assert auth_of(app, cid, "r1") is None                                              # Same — meros
    assert auth_of(app, cid, "r2")["bearer"][0]["value"] == "DIFFERENT"                 # Other tegilmadi
    assert auth_of(app, cid, "r3") == {"type": "noauth"} and auth_of(app, cid, "r5")["bearer"][0]["value"] == "NEW"


def test_bulk_offer_select_all_and_open_tab_drafts_follow(ui, app, world):
    cid = world
    row(ui, "Fold").dblclick()
    row(ui, "Fold").locator("[data-testid=row-chevron]").click() if row(ui, "Other").count() == 0 else None
    row(ui, "Other").dblclick()
    ui.click("[data-section=auth]")
    expect(T(ui, "auth-type")).to_have_value("bearer")
    ui.locator("[data-testid=tab]").filter(has_text="Fold").click()
    ui.click("[data-scope-section=auth]")
    ui.select_option("[data-testid=auth-type]", "bearer")
    T(ui, "auth-token").fill("NEW")
    T(ui, "scope-save").click()
    T(ui, "bulk-auth-all").click()
    expect(T(ui, "bulk-auth-apply")).to_contain_text("(3)")
    T(ui, "bulk-auth-apply").click()
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    assert [auth_of(app, cid, i) for i in ("r1", "r2", "r3")] == [None, None, None]
    ui.locator("[data-testid=tab]").filter(has_text="Other").click()                     # ochiq tab qoralamasi ham «Meros»ga o'tdi
    expect(T(ui, "auth-type")).to_have_value("inherit")
    expect(ui.locator("[data-testid=dirty-dot]")).to_have_count(0)
    expect(T(ui, "auth-inherit-src")).to_contain_text("«Fold» papkasidan")


def test_bulk_offer_can_be_skipped_and_only_when_it_matters(ui, app, world):
    cid = world
    set_folder_auth(ui, "Fold", "NEW")
    expect(T(ui, "bulk-auth-dialog")).to_be_visible()
    ui.keyboard.press("Escape")
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    assert auth_of(app, cid, "r1")["bearer"][0]["value"] == "NEW"                      # o'zgarmadi
    T(ui, "scope-desc") if False else None
    ui.click("[data-scope-section=overview]")
    T(ui, "scope-desc").fill("faqat tavsif")                                           # auth o'zgarmagan — taklif yo'q
    T(ui, "scope-save").click()
    expect(ui.locator(".toast")).to_contain_text("Saqlandi")
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    ui.click("[data-scope-section=auth]")
    ui.select_option("[data-testid=auth-type]", "inherit")                              # «Meros»ga qaytarish — taklif yo'q
    T(ui, "scope-save").click()
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)


def test_no_offer_when_nothing_would_be_overridden(ui):
    row(ui, "Other folder").click(button="right")
    ui.click("[data-act=settings]")
    ui.click("[data-scope-section=auth]")
    ui.select_option("[data-testid=auth-type]", "bearer")
    T(ui, "auth-token").fill("X")
    T(ui, "scope-save").click()
    expect(ui.locator(".toast")).to_contain_text("Saqlandi")
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)                                  # Child'ning o'z auth'i yo'q


# ── qulf belgisi ──
def test_lock_icon_marks_nodes_with_own_auth_only(ui, app, world):
    row(ui, "Fold").click()
    row(ui, "Fold").locator("[data-testid=row-chevron]").click()
    has_lock = lambda name: row(ui, name).locator("[data-testid=auth-lock]").count() == 1  # noqa: E731
    assert has_lock("Col") and has_lock("Same") and has_lock("Other") and has_lock("Other folder") and has_lock("Sub")
    assert not has_lock("Fold") and not has_lock("Optout") and not has_lock("Plain") and not has_lock("Root")      # meros / "Auth yo'q" — qulfsiz
    expect(row(ui, "Same").locator("[data-testid=auth-lock]")).to_have_attribute("title", "Auth: Bearer Token (o'z auth'i)")
    expect(row(ui, "Other folder").locator("[data-testid=auth-lock]")).to_have_attribute("aria-label", re.compile("Basic Auth"))
    set_folder_auth(ui, "Fold", "NEW")
    T(ui, "bulk-auth-all").click()
    T(ui, "bulk-auth-apply").click()
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    assert has_lock("Fold") and not has_lock("Same") and not has_lock("Other")           # papkada paydo bo'ldi, so'rovlardan ketdi
