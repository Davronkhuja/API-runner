"""Example'lar daraxtda: so'rov ostida, ochish/tahrirlash/saqlash, dublikat/o'chirish, javobdan saqlash."""
import json

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import eventually

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def world(app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    ex = lambda n, code, body, i=None: {**({"id": i} if i else {}), "name": n, "code": code, "status": "OK" if code == 200 else "Not Found", "header": [{"key": "Content-Type", "value": "application/json"}], "body": body, "_postman_previewlanguage": "json"}  # noqa: E731
    col["item"] = [{"id": "r1", "name": "Users", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/echo"}}, "response": [ex("Success", 200, '{"ok": true}', "exA"), ex("Missing", 404, '{"error": "no"}')]},
                   {"id": "r2", "name": "Plain", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/echo"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    return cid


@pytest.fixture
def ui(app, page, world):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def examples_on_server(app, cid, item="r1"):
    return next(i for i in app.api("GET", f"/api/collections/{cid}")["item"] if i["id"] == item)["response"]


def expand(p):
    p.locator("[data-name='Users'] [data-testid=ex-chevron]").click()


def test_examples_appear_under_request_only_when_expanded_and_requests_without_examples_have_no_chevron(ui):
    expect(T(ui, "example-row")).to_have_count(0)
    expect(ui.locator("[data-name='Plain'] [data-testid=ex-chevron]")).to_have_count(0)
    expand(ui)
    expect(T(ui, "example-row")).to_have_count(2)
    expect(ui.locator("[data-testid=example-row]").first).to_contain_text("Success")
    ui.locator("[data-name='Users'] [data-testid=ex-chevron]").click()
    expect(T(ui, "example-row")).to_have_count(0)


def test_open_edit_and_save_example_assigns_ids_and_persists(ui, app, world):
    expand(ui)
    ui.locator("[data-testid=example-row][data-name='Missing']").dblclick()
    expect(T(ui, "example-tab")).to_be_visible()
    expect(T(ui, "example-name")).to_have_value("Missing")
    expect(T(ui, "example-code")).to_have_value("404")
    expect(T(ui, "example-save")).to_be_disabled()
    T(ui, "example-code").fill("410")
    expect(T(ui, "example-status")).to_have_value("")
    T(ui, "example-status").fill("Gone")
    T(ui, "example-body").click()
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type('{"error": "gone"}')
    ui.locator("[data-cell='0:1']").fill("text/plain")
    expect(T(ui, "example-save")).to_be_enabled()
    T(ui, "example-save").click()
    eventually(lambda: next(e for e in examples_on_server(app, world) if e["name"] == "Missing")["code"] == 410)       # saqlash asinxron: serverga yetguncha kutamiz
    exs = examples_on_server(app, world)
    assert all(e.get("id") for e in exs)                                   # eski id'siz example'larga id berildi
    miss = next(e for e in exs if e["name"] == "Missing")
    assert miss["code"] == 410 and miss["status"] == "Gone" and "gone" in miss["body"] and miss["header"] == [{"key": "Content-Type", "value": "text/plain"}]
    assert next(e for e in exs if e["name"] == "Success")["body"] == '{"ok": true}'   # boshqasi tegilmagan


def test_unsaved_edit_survives_tab_switch_and_close_dialog_saves(ui, app, world):
    expand(ui)
    ui.locator("[data-testid=example-row][data-name='Success']").dblclick()
    T(ui, "example-name").fill("Renamed")
    ui.locator("[data-name='Plain']").dblclick()                           # boshqa tabga o'tish
    expect(T(ui, "request-editor")).to_be_visible()
    ui.locator("[data-testid=tab]", has_text="Success").click()           # qaytganda tahrir saqlanib qolgan
    expect(T(ui, "example-name")).to_have_value("Renamed")
    ui.locator("[data-testid=tab]", has_text="Success").locator("[data-testid=tab-close]").click()
    T(ui, "dlg-save").click()
    eventually(lambda: any(e["name"] == "Renamed" for e in examples_on_server(app, world)))


def test_duplicate_and_delete_via_context_menu(ui, app, world):
    expand(ui)
    row = ui.locator("[data-testid=example-row][data-name='Success']")
    row.click(button="right")
    ui.click("[data-act=ex-dup]")
    expect(T(ui, "example-row")).to_have_count(3)
    assert [e["name"] for e in examples_on_server(app, world)] == ["Success", "Success Copy", "Missing"]
    ui.locator("[data-testid=example-row][data-name='Success Copy']").click(button="right")
    ui.click("[data-act=ex-delete]")
    T(ui, "confirm-ok").click()
    expect(T(ui, "example-row")).to_have_count(2)
    assert [e["name"] for e in examples_on_server(app, world)] == ["Success", "Missing"]


def test_save_as_example_from_response_shows_up_in_tree(ui, app, world, echo_server):
    ui.locator("[data-name='Plain']").dblclick()
    with ui.expect_response(lambda r: r.url.endswith("/run_one")):
        T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("200")
    T(ui, "save-example").click()
    eventually(lambda: len(examples_on_server(app, world, "r2")) == 1)
    ex = examples_on_server(app, world, "r2")
    assert len(ex) == 1 and ex[0]["id"] and ex[0]["code"] == 200
    ui.locator("[data-name='Plain'] [data-testid=ex-chevron]").click()
    expect(T(ui, "example-row")).to_have_count(1)
    json.loads(ex[0]["body"])
