"""Papka/collection tabi (Overview | Auth | Variables | Scripts | Run), meros manbasi, ommaviy «Meros» taklifi va qulf belgisi."""
import json
import re

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import eventually

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


# ── «Meros'ga o'tkazish» taklifi (v3.0.2: faqat haqiqiy nomzod; sukut — toast) ──
def dialog_mode(app):
    app.api("PUT", "/api/workspace/meta", {"auth_offers": {"mode": "dialog", "nodes": {}}})


def reload(ui):
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")


def test_toast_offer_counts_only_requests_with_same_token_and_applies_with_backup(ui, app, world):
    cid = world
    row(ui, "Fold").locator("[data-testid=row-chevron]").click() if row(ui, "Same").count() == 0 else None
    before = len(app.api("GET", "/api/backups"))
    set_folder_auth(ui, "Fold", "NEW")
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)                                  # sukut: dialog emas, toast
    expect(T(ui, "toast-action")).to_be_visible()
    expect(T(ui, "toast")).to_contain_text("1 ta so'rovda")                             # faqat Same (NEW); Other/Optout sanalmaydi; InSub — Sub auth'i bilan to'silgan
    T(ui, "toast-action").click()
    expect(ui.locator(".toast")).to_contain_text("1 ta so'rov «Meros»ga o'tkazildi")
    assert len(app.api("GET", "/api/backups")) == before + 1 and any("pre-bulk-auth" in b["name"] for b in app.api("GET", "/api/backups"))
    assert auth_of(app, cid, "r1") is None
    assert auth_of(app, cid, "r2")["bearer"][0]["value"] == "DIFFERENT"                 # boshqacha auth — tegilmadi
    assert auth_of(app, cid, "r3") == {"type": "noauth"} and auth_of(app, cid, "r5")["bearer"][0]["value"] == "NEW"


def test_toast_disappears_after_eight_seconds_without_touching_anything(ui, app, world):
    cid = world
    set_folder_auth(ui, "Fold", "NEW")
    expect(T(ui, "toast-action")).to_be_visible()
    expect(T(ui, "toast-action")).to_have_count(0, timeout=12000)
    assert auth_of(app, cid, "r1")["bearer"][0]["value"] == "NEW"


def test_old_token_requests_are_offered_when_folder_token_changes(ui, app, world):
    cid = world
    set_folder_auth(ui, "Fold", "NEW")
    T(ui, "toast-action").click()                                                       # Same -> meros
    expect(ui.locator(".toast")).to_contain_text("o'tkazildi")
    app.api("PUT", f"/api/collections/{cid}", {**app.api("GET", f"/api/collections/{cid}")})
    set_folder_auth(ui, "Fold", "NEWER")                                                # eski NEW tokenli: InSub (Sub auth'i bilan to'silgan) — nomzod emas; boshqa yo'q
    ui.wait_for_timeout(400)
    expect(T(ui, "toast-action")).to_have_count(0)
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)


def test_dialog_mode_lists_only_candidates_and_open_tab_drafts_follow(ui, app, world):
    cid = world
    dialog_mode(app)
    reload(ui)
    row(ui, "Fold").dblclick()
    row(ui, "Fold").locator("[data-testid=row-chevron]").click() if row(ui, "Same").count() == 0 else None
    row(ui, "Same").dblclick()
    ui.click("[data-section=auth]")
    expect(T(ui, "auth-type")).to_have_value("bearer")
    ui.locator("[data-testid=tab]").filter(has_text="Fold").click()
    ui.click("[data-scope-section=auth]")
    ui.select_option("[data-testid=auth-type]", "bearer")
    T(ui, "auth-token").fill("NEW")
    T(ui, "scope-save").click()
    expect(T(ui, "bulk-auth-dialog")).to_be_visible()
    expect(T(ui, "bulk-auth-count")).to_have_text("1")
    rows = T(ui, "bulk-auth-row")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("Same")
    expect(rows.first.locator("[data-testid=bulk-auth-same]")).to_have_text("bir xil")
    expect(T(ui, "bulk-auth-backup-note")).to_contain_text("zaxira")
    T(ui, "bulk-auth-apply").click()
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    assert auth_of(app, cid, "r1") is None
    ui.locator("[data-testid=tab]").filter(has_text="Same").click()                      # ochiq tab qoralamasi ham «Meros»ga o'tdi
    expect(T(ui, "auth-type")).to_have_value("inherit")
    expect(ui.locator("[data-testid=dirty-dot]")).to_have_count(0)


def test_dialog_can_be_skipped_and_only_when_auth_really_changes(ui, app, world):
    cid = world
    dialog_mode(app)
    reload(ui)
    set_folder_auth(ui, "Fold", "NEW")
    expect(T(ui, "bulk-auth-dialog")).to_be_visible()
    ui.keyboard.press("Escape")
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    assert auth_of(app, cid, "r1")["bearer"][0]["value"] == "NEW"                      # o'zgarmadi
    ui.click("[data-scope-section=overview]")
    T(ui, "scope-desc").fill("faqat tavsif")                                           # auth o'zgarmagan — taklif yo'q
    T(ui, "scope-save").click()
    expect(ui.locator(".toast")).to_contain_text("Saqlandi")
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    expect(T(ui, "toast-action")).to_have_count(0)
    ui.click("[data-scope-section=auth]")
    ui.select_option("[data-testid=auth-type]", "inherit")                              # «Meros»ga qaytarish — taklif yo'q
    T(ui, "scope-save").click()
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)


def test_no_candidates_means_nothing_is_shown_on_repeated_saves(app, page):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "f", "name": "Fold", "item": [req("a", "A", bearer("X1")), req("b", "B", bearer("X2")), req("c", "C", {"type": "noauth"})]}]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    for tok in ("T1", "T2", "T3", "T3"):
        set_folder_auth(page, "Fold", tok)
        page.wait_for_timeout(300)
        expect(T(page, "bulk-auth-dialog")).to_have_count(0)
        expect(T(page, "toast-action")).to_have_count(0)                                # boshqacha auth'li so'rovlar umuman sanalmaydi


def test_declined_request_is_remembered_and_not_offered_again(ui, app, world):
    cid = world
    dialog_mode(app)
    reload(ui)
    set_folder_auth(ui, "Fold", "NEW")
    expect(T(ui, "bulk-auth-dialog")).to_be_visible()
    T(ui, "bulk-auth-check").first.uncheck()                                            # «Same» o'z auth'ida qoladi
    T(ui, "bulk-auth-skip").click()
    eventually(lambda: app.api("GET", "/api/workspace")["meta"]["auth_offers"]["nodes"][f"{cid}:f"]["kept"] == ["r1"])
    set_folder_auth(ui, "Fold", "NEWER")                                                # Same (NEW) eski token bilan teng — lekin rad etilgan
    ui.wait_for_timeout(400)
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    assert auth_of(app, cid, "r1")["bearer"][0]["value"] == "NEW"
    reload(ui)                                                                          # eslab qolish diskda
    set_folder_auth(ui, "Fold", "NEWEST")
    ui.wait_for_timeout(400)
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    T(ui, "settings-btn").click()
    expect(T(ui, "offer-memory-row")).to_contain_text("1 ta so'rov o'z auth'ida qoldirilgan")
    T(ui, "offer-reset").click()                                                        # qaytarib olinadi
    eventually(lambda: f"{cid}:f" not in app.api("GET", "/api/workspace")["meta"]["auth_offers"]["nodes"])


def test_dont_ask_for_this_folder_and_overview_link_remains(ui, app, world):
    cid = world
    dialog_mode(app)
    reload(ui)
    set_folder_auth(ui, "Fold", "NEW")
    T(ui, "bulk-auth-off").check()
    T(ui, "bulk-auth-skip").click()
    eventually(lambda: app.api("GET", "/api/workspace")["meta"]["auth_offers"]["nodes"][f"{cid}:f"]["off"] is True)
    set_folder_auth(ui, "Fold", "NEWER")
    ui.wait_for_timeout(400)
    expect(T(ui, "bulk-auth-dialog")).to_have_count(0)
    ui.click("[data-scope-section=overview]")
    expect(T(ui, "ov-to-inherit")).to_contain_text("ta so'rovda o'z auth'i — ko'rib chiqish")     # Overview'da kichik havola qoladi
    T(ui, "ov-to-inherit").click()
    expect(T(ui, "bulk-auth-dialog")).to_be_visible()


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
    T(ui, "toast-action").click()
    expect(ui.locator(".toast")).to_contain_text("o'tkazildi")
    eventually(lambda: not has_lock("Same"))
    assert has_lock("Fold") and has_lock("Other")                                        # papkada paydo bo'ldi; Same — meros; Other (boshqa token) tegilmadi
