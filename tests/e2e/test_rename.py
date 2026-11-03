"""Nomni o'zgartirish: bitta haqiqat manbai (server + daraxt + ochiq tab qoralamasi + sarlavha), Save nomni bosib ketmasin."""
import re

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    mk = lambda i, n, u="{{base}}/echo": {"id": i, "name": n, "request": {"method": "GET", "header": [], "url": {"raw": u}}, "response": []}  # noqa: E731
    col["variable"] = [{"key": "base", "value": echo_server}]
    col["item"] = [{"id": "f", "name": "Fold", "item": [mk("a", "Alpha"), mk("b", "Beta")]}, {"id": "g", "name": "Gold", "item": [mk("c", "Alpha")]}, mk("d", "Delta")]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.cid = cid
    return page


def row(p, name, nth=0):
    return p.locator(f"[data-name='{name}']").nth(nth)


def item_name(app, cid, iid):
    def walk(items):
        for it in items:
            if it["id"] == iid:
                return it["name"]
            if "item" in it:
                r = walk(it["item"])
                if r:
                    return r
    return walk(app.api("GET", f"/api/collections/{cid}")["item"])


def toast(p):
    return p.locator(".toast")


def collection_name(app, cid):
    return app.api("GET", f"/api/collections/{cid}")["info"]["name"]


# ── asosiy xato: rename → Save nomni bosib ketmasin ──
def test_rename_in_sidebar_then_save_dirty_tab_keeps_new_name_and_other_edits(ui, app):
    cid = ui.cid
    row(ui, "Delta").dblclick()
    ui.fill("[data-testid=url]", "{{base}}/echo?edited=1")                      # saqlanmagan o'zgarish (tab dirty)
    row(ui, "Delta").press("F2")
    T(ui, "rename-input").fill("Renamed")
    T(ui, "rename-input").press("Enter")
    expect(row(ui, "Renamed")).to_have_count(1)
    expect(T(ui, "dirty-dot")).to_have_count(1)                                 # rename tab holatini "toza" qilib yubormadi
    expect(T(ui, "url")).to_have_text("{{base}}/echo?edited=1")                 # boshqa saqlanmagan o'zgarish yo'qolmadi
    T(ui, "save").click()
    expect(T(ui, "dirty-dot")).to_have_count(0)
    assert item_name(app, cid, "d") == "Renamed"
    saved = next(i for i in app.api("GET", f"/api/collections/{cid}")["item"] if i["id"] == "d")
    assert saved["request"]["url"]["raw"].endswith("echo?edited=1")
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    assert ui.locator("[data-testid=tab] .title").all_inner_texts() == ["Renamed"]
    expect(row(ui, "Renamed")).to_have_count(1)
    expect(T(ui, "crumbs")).to_contain_text("Renamed")


def test_rename_updates_server_tree_tab_title_breadcrumb_and_draft_at_once(ui, app):
    cid = ui.cid
    row(ui, "Delta").dblclick()
    row(ui, "Delta").click(button="right")
    ui.click("[data-act=rename]")
    T(ui, "rename-input").fill("Epsilon")
    T(ui, "rename-input").press("Enter")
    expect(ui.locator("[data-testid=tab] .title")).to_have_text("Epsilon")
    expect(T(ui, "crumb-rename")).to_have_text("Epsilon")
    assert item_name(app, cid, "d") == "Epsilon"
    ui.fill("[data-testid=url]", "{{base}}/echo?x=1")
    T(ui, "save").click()
    expect(T(ui, "dirty-dot")).to_have_count(0)
    assert item_name(app, cid, "d") == "Epsilon"
    ui.locator("[data-testid=tab]").first.click(button="right")                          # tab nusxasi ham yangi nom bilan
    ui.click("[data-act=dup]")
    expect(ui.locator("[data-testid=tab] .title").nth(1)).to_have_text("Epsilon Copy")


def test_rename_focus_selection_enter_blur_and_escape(ui, app):
    cid = ui.cid
    row(ui, "Delta").press("F2")
    expect(T(ui, "rename-input")).to_be_focused()                                       # fokus ishonchli
    assert ui.evaluate("(() => { const i = document.activeElement; return i.value.slice(i.selectionStart, i.selectionEnd) })()") == "Delta"      # matn belgilangan
    ui.keyboard.type("Esc-test")
    ui.keyboard.press("Escape")
    expect(T(ui, "rename-input")).to_have_count(0)
    assert item_name(app, cid, "d") == "Delta"                                           # Esc — bekor (blur saqlab yubormadi)
    row(ui, "Delta").press("F2")
    ui.keyboard.type("ViaBlur")
    ui.locator("[data-testid=tree]").click(position={"x": 5, "y": 400})                  # blur — saqlash
    expect(row(ui, "ViaBlur")).to_have_count(1)
    assert item_name(app, cid, "d") == "ViaBlur"


def test_empty_and_duplicate_names_show_clear_messages(ui, app):
    cid = ui.cid
    row(ui, "Alpha", 0).press("F2")
    T(ui, "rename-input").fill("   ")
    T(ui, "rename-input").press("Enter")
    expect(toast(ui)).to_contain_text("Nom bo'sh bo'lishi mumkin emas")
    expect(T(ui, "rename-input")).to_be_visible()                                       # tahrirda qoladi
    T(ui, "rename-input").fill("Beta")                                                  # bir papkada takror
    T(ui, "rename-input").press("Enter")
    expect(toast(ui)).to_contain_text("«Beta» nomli element bu papkada allaqachon bor")
    expect(T(ui, "rename-input")).to_be_visible()
    T(ui, "rename-input").fill("Delta")                                                 # boshqa papka/ildiz — ruxsat
    T(ui, "rename-input").press("Enter")
    expect(T(ui, "rename-input")).to_have_count(0)
    assert item_name(app, cid, "a") == "Delta"
    row(ui, "Delta", 1).press("F2")                                                     # blur + yaroqsiz = bekor
    T(ui, "rename-input").fill("Beta")
    T(ui, "rename-input").blur()
    expect(T(ui, "rename-input")).to_have_count(0)
    assert item_name(app, cid, "a") == "Delta"
    row(ui, "Col").press("F2")
    T(ui, "rename-input").fill("")
    T(ui, "rename-input").press("Enter")
    expect(toast(ui)).to_contain_text("bo'sh")


# ── breadcrumb ──
def test_breadcrumb_name_becomes_inline_input_enter_blur_escape(ui, app):
    cid = ui.cid
    row(ui, "Delta").dblclick()
    T(ui, "crumb-rename").click()
    expect(T(ui, "crumb-rename-input")).to_be_focused()
    assert ui.evaluate("(() => { const i = document.activeElement; return i.value.slice(i.selectionStart, i.selectionEnd) })()") == "Delta"
    ui.keyboard.type("Typed")
    ui.keyboard.press("Escape")
    expect(T(ui, "crumb-rename")).to_have_text("Delta")                                 # Esc — bekor
    assert item_name(app, cid, "d") == "Delta"
    T(ui, "crumb-rename").click()
    T(ui, "crumb-rename-input").fill("ViaEnter")
    T(ui, "crumb-rename-input").press("Enter")
    expect(T(ui, "crumb-rename")).to_have_text("ViaEnter")
    expect(row(ui, "ViaEnter")).to_have_count(1)
    assert item_name(app, cid, "d") == "ViaEnter" and ui.locator("[data-testid=tab] .title").inner_text() == "ViaEnter"
    T(ui, "crumb-rename").press("Enter")                                                # klaviatura bilan ham ochiladi
    T(ui, "crumb-rename-input").fill("ViaBlur")
    ui.locator("[data-testid=url]").click()                                              # blur — saqlash
    expect(T(ui, "crumb-rename")).to_have_text("ViaBlur")
    assert item_name(app, cid, "d") == "ViaBlur"
    T(ui, "crumb-rename").click()
    T(ui, "crumb-rename-input").fill("")
    T(ui, "crumb-rename-input").press("Enter")
    expect(toast(ui)).to_contain_text("bo'sh")
    expect(T(ui, "crumb-rename-input")).to_be_visible()


def test_breadcrumb_rename_with_unsaved_edits_then_save(ui, app):
    cid = ui.cid
    row(ui, "Delta").dblclick()
    ui.select_option("[data-testid=method]", "POST")
    ui.fill("[data-testid=url]", "{{base}}/echo?q=1")
    T(ui, "crumb-rename").click()
    T(ui, "crumb-rename-input").fill("Mixed")
    T(ui, "crumb-rename-input").press("Enter")
    T(ui, "save").click()
    expect(T(ui, "dirty-dot")).to_have_count(0)
    item = next(i for i in app.api("GET", f"/api/collections/{cid}")["item"] if i["id"] == "d")
    assert item["name"] == "Mixed" and item["request"]["method"] == "POST" and item["request"]["url"]["raw"].endswith("echo?q=1")


def test_unsaved_new_request_breadcrumb_opens_save_dialog(ui):
    T(ui, "new-tab").click()
    T(ui, "crumb-rename").click()
    expect(T(ui, "saveas-dialog")).to_be_visible()


# ── papka va collection ──
def test_folder_and_collection_rename_from_sidebar_and_from_their_tab_titles(ui, app):
    cid = ui.cid
    row(ui, "Fold").press("F2")
    T(ui, "rename-input").fill("Folder2")
    T(ui, "rename-input").press("Enter")
    expect(row(ui, "Folder2")).to_have_count(1)
    row(ui, "Folder2").dblclick()
    expect(T(ui, "node-title")).to_contain_text("Folder2")
    T(ui, "node-rename").click()
    expect(T(ui, "node-rename-input")).to_be_focused()
    T(ui, "node-rename-input").fill("Folder3")
    T(ui, "node-rename-input").press("Enter")
    expect(row(ui, "Folder3")).to_have_count(1)
    expect(ui.locator("[data-testid=tab] .title").first).to_have_text("Folder3")
    expect(T(ui, "node-crumbs")).to_contain_text("Folder3")
    # collection: F2 va kontekst menyu
    row(ui, "Col").press("F2")
    T(ui, "rename-input").fill("Col2")
    T(ui, "rename-input").press("Enter")
    expect(row(ui, "Col2")).to_have_count(1)
    assert collection_name(app, cid) == "Col2"
    row(ui, "Col2").click(button="right")
    ui.click("[data-act=rename]")
    T(ui, "rename-input").fill("Col3")
    T(ui, "rename-input").press("Enter")
    assert collection_name(app, cid) == "Col3"
    row(ui, "Col3").dblclick()
    expect(T(ui, "tab-collection")).to_be_visible()
    T(ui, "node-rename").click()
    T(ui, "node-rename-input").fill("Col4")
    T(ui, "node-rename-input").press("Enter")
    assert collection_name(app, cid) == "Col4"
    expect(ui.locator("[data-testid=tab].active .title")).to_have_text("Col4")
    row(ui, "Col4").click(button="right")                                               # runner tab sarlavhasi ham yangilanadi
    ui.click("[data-act=runner]")
    expect(ui.locator("[data-testid=tab].active .title")).to_have_text("Runner: Col4")
    row(ui, "Col4").press("F2")
    T(ui, "rename-input").fill("Col5")
    T(ui, "rename-input").press("Enter")
    expect(ui.locator("[data-testid=tab] .title").all()[-1]).to_have_text("Runner: Col5")


def test_collection_duplicate_name_is_rejected(ui, app):
    app.api("POST", "/api/collections", {"name": "Other"})
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    row(ui, "Col").press("F2")
    T(ui, "rename-input").fill("Other")
    T(ui, "rename-input").press("Enter")
    expect(toast(ui)).to_contain_text("«Other» nomli collection allaqachon bor")


# ── tab kontekst menyusi ──
def test_tab_context_menu_rename_for_request_and_collection_tabs(ui, app):
    cid = ui.cid
    row(ui, "Delta").dblclick()
    ui.locator("[data-testid=tab]").first.click(button="right")
    ui.click("[data-act=rename]")
    expect(T(ui, "crumb-rename-input")).to_be_focused()
    T(ui, "crumb-rename-input").fill("FromTab")
    T(ui, "crumb-rename-input").press("Enter")
    assert item_name(app, cid, "d") == "FromTab"
    row(ui, "Col").dblclick()
    ui.locator("[data-testid=tab]").nth(1).click(button="right")
    ui.click("[data-act=rename]")
    expect(T(ui, "node-rename-input")).to_be_focused()
    ui.keyboard.press("Escape")
    T(ui, "settings-btn").click()
    ui.locator("[data-testid=tab]").nth(2).click(button="right")
    expect(ui.locator("[data-testid=tab-menu] [data-act=rename]")).to_be_disabled()
    ui.keyboard.press("Escape")


# ── dublikat ──
def test_duplicate_opens_rename_mode_with_copy_name_selected_and_names_stay_unique(ui, app):
    cid = ui.cid
    row(ui, "Delta").click(button="right")
    ui.click("[data-act=dup]")
    expect(T(ui, "rename-input")).to_be_focused()
    expect(T(ui, "rename-input")).to_have_value("Delta Copy")
    assert ui.evaluate("(() => { const i = document.activeElement; return i.value.slice(i.selectionStart, i.selectionEnd) })()") == "Delta Copy"
    ui.keyboard.type("Clone")
    ui.keyboard.press("Enter")
    expect(row(ui, "Clone")).to_have_count(1)
    row(ui, "Delta").click(button="right")
    ui.click("[data-act=dup]")
    expect(T(ui, "rename-input")).to_be_focused()
    ui.keyboard.press("Enter")                                                          # "Delta Copy" ni qabul qilish
    expect(row(ui, "Delta Copy")).to_have_count(1)
    row(ui, "Delta").click(button="right")
    ui.click("[data-act=dup]")
    expect(T(ui, "rename-input")).to_have_value("Delta Copy 2")                         # takror bo'lmaydi
    ui.keyboard.press("Escape")
    expect(row(ui, "Delta Copy 2")).to_have_count(1)                                    # Esc nom o'zgartirmaydi, nusxa qoladi
