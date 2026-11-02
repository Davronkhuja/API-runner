"""Bosqich 2 / 1: collection-papka sozlamalari (meros auth), scope'li o'zgaruvchilar, path variables, chiplar."""
import json
import re

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


def bearer(tok):
    return {"type": "bearer", "bearer": [{"key": "token", "value": tok, "type": "string"}]}


def req_item(iid, name, url, auth=None):
    r = {"method": "GET", "header": [], "url": {"raw": url}}
    if auth:
        r["auth"] = auth
    return {"id": iid, "name": name, "request": r, "response": []}


@pytest.fixture
def world(app, echo_server):
    """Collection(auth=A, vars host/who) → Folder(auth=inherit, var who) → 3 so'rov."""
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["auth"] = bearer("COLTOKEN")
    col["variable"] = [{"key": "host", "value": echo_server}, {"key": "who", "value": "collection"}]
    col["item"] = [{"id": "f1", "name": "Fold", "variable": [{"key": "who", "value": "folder"}], "auth": bearer("FOLDTOKEN"), "item": [
        req_item("r1", "InFolder", "{{host}}/echo?who={{who}}"),
        req_item("r2", "Own", "{{host}}/echo", auth=bearer("OWNTOKEN")),
        req_item("r3", "NoAuth", "{{host}}/echo", auth={"type": "noauth"})]},
        req_item("r4", "AtRoot", "{{host}}/echo?who={{who}}")]
    app.api("PUT", f"/api/collections/{cid}", col)
    return cid


@pytest.fixture
def ui(app, page, world):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def open_req(p, name):
    p.locator(f"[data-name='{name}']").dblclick()
    expect(T(p, "request-editor")).to_be_visible()


def send_and_json(p):
    T(p, "send").click()
    expect(T(p, "resp-status")).to_have_text("200")
    return json.loads(T(p, "resp-body").inner_text())


def test_request_inherits_nearest_parent_auth(ui):
    open_req(ui, "InFolder")
    j = send_and_json(ui)
    assert j["headers"]["Authorization"] == "Bearer FOLDTOKEN"       # papka collection'dan ustun
    open_req(ui, "AtRoot")
    assert send_and_json(ui)["headers"]["Authorization"] == "Bearer COLTOKEN"


def test_own_auth_and_noauth_override_inheritance(ui):
    open_req(ui, "Own")
    assert send_and_json(ui)["headers"]["Authorization"] == "Bearer OWNTOKEN"
    open_req(ui, "NoAuth")
    assert "Authorization" not in send_and_json(ui)["headers"]


def test_scope_precedence_folder_over_collection_and_env_over_both(ui, app):
    open_req(ui, "InFolder")
    assert send_and_json(ui)["args"]["who"] == ["folder"]
    open_req(ui, "AtRoot")
    assert send_and_json(ui)["args"]["who"] == ["collection"]
    # Globals < Collection: globals'dagi 'who' collection'ni bosmaydi; Environment esa ustun
    app.api("PUT", "/api/globals", {"values": [{"key": "who", "value": "global", "enabled": True, "type": "default"}]})
    eid = app.api("POST", "/api/environments", {"name": "E"})["id"]
    env = app.api("GET", f"/api/environments/{eid}")
    env["values"] = [{"key": "who", "value": "env", "enabled": True, "type": "default"}]
    app.api("PUT", f"/api/environments/{eid}", env)
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    open_req(ui, "AtRoot")
    assert send_and_json(ui)["args"]["who"] == ["env"]


def test_inherit_note_and_default_for_new_request(ui):
    T(ui, "new-tab").click()
    ui.click("[data-section=auth]")
    expect(T(ui, "auth-type")).to_have_value("inherit")
    open_req(ui, "AtRoot")
    ui.click("[data-section=auth]")
    expect(T(ui, "auth-inherit-note")).to_contain_text("bearer")


def test_var_chips_defined_dynamic_undefined_and_hover_scope(ui):
    open_req(ui, "InFolder")
    chips = T(ui, "var-chip")
    expect(chips).to_have_count(2)
    who = ui.locator("[data-testid=var-chip]", has_text="who")
    expect(who).to_have_attribute("title", re.compile(r"Folder: Fold: folder"))
    expect(who).to_have_class(re.compile("var-ok"))
    ui.fill("[data-testid=url]", "{{host}}/echo/{{missing}}/{{$guid}}")
    miss = ui.locator("[data-testid=var-chip]", has_text="missing")
    expect(miss).to_have_class(re.compile("var-undef"))
    expect(ui.locator("[data-testid=var-chip]", has_text="$guid")).to_have_class(re.compile("var-ok"))


def test_secret_variable_is_masked_in_chip_title_and_input(ui, app):
    cid = app.api("GET", "/api/workspace")["collections"][0]["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"].append({"key": "tok", "value": "SUPERSECRET", "type": "secret"})
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    open_req(ui, "AtRoot")
    ui.fill("[data-testid=url]", "{{host}}/echo?t={{tok}}")
    chip = ui.locator("[data-testid=var-chip]", has_text="tok")
    assert "SUPERSECRET" not in chip.get_attribute("title")
    ui.locator("[data-name='Col']").dblclick()
    ui.click("[data-scope-section=vars]")
    ui.locator("[data-testid=scope-vars] [data-testid=var-key]", has=ui.locator("xpath=.")).last  # jadval mavjud
    assert ui.locator("[data-testid=scope-vars] input[type=password]").count() == 1


def test_path_variables_table_and_substitution(ui, echo_server):
    T(ui, "new-tab").click()
    ui.fill("[data-testid=url]", echo_server + "/echo/:id/sub/:name?x=1")
    expect(T(ui, "path-vars").locator("code")).to_have_count(2)
    ui.locator("[data-testid=path-var-val]").nth(0).fill("42")
    ui.locator("[data-testid=path-var-val]").nth(1).fill("abc")
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("404")                # /echo/42/sub/abc yo'li yo'q, lekin yo'l almashtirilgan
    expect(T(ui, "resp-timing")).to_be_visible()
    # almashtirish engine'da: javob URL'i (karta) uchun batch orqali ko'ramiz
    ui.click("[data-section=batch]")
    T(ui, "batch-run").click()
    expect(T(ui, "result-card").first).to_contain_text("/echo/42/sub/abc")


def test_collection_settings_save_auth_vars_description_roundtrip(ui, app):
    ui.locator("[data-name='Col']").dblclick()
    expect(T(ui, "tab-collection")).to_be_visible()
    ui.select_option("[data-testid=auth-type]", "bearer")
    T(ui, "auth-token").fill("NEWCOL")
    ui.click("[data-scope-section=vars]")
    T(ui, "var-add").click()
    ui.locator("[data-testid=var-key]").last.fill("extra")
    ui.locator("[data-testid=var-val]").last.fill("1")
    ui.click("[data-scope-section=desc]")
    T(ui, "scope-desc").fill("Tavsif matni")
    T(ui, "scope-save").click()
    cid = app.api("GET", "/api/workspace")["collections"][0]["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    assert col["auth"]["bearer"][0]["value"] == "NEWCOL"
    assert any(v["key"] == "extra" for v in col["variable"])
    assert col["x-apirunner"]["description"] == "Tavsif matni"
    open_req(ui, "AtRoot")
    assert send_and_json(ui)["headers"]["Authorization"] == "Bearer NEWCOL"


def test_folder_settings_via_context_menu_save_and_inherit_option(ui, app):
    ui.locator("[data-name='Fold']").click(button="right")
    ui.click("[data-act=settings]")
    expect(T(ui, "tab-folder")).to_be_visible()
    ui.select_option("[data-testid=auth-type]", "inherit")          # papka ham meros qila oladi
    ui.click("[data-scope-section=scripts]")
    T(ui, "scope-pre").fill("console.log(1)")
    T(ui, "scope-save").click()
    cid = app.api("GET", "/api/workspace")["collections"][0]["id"]
    f = app.api("GET", f"/api/collections/{cid}")["item"][0]
    assert f.get("auth") is None and f["event"][0]["listen"] == "prerequest"
    open_req(ui, "InFolder")
    assert send_and_json(ui)["headers"]["Authorization"] == "Bearer COLTOKEN"


def test_globals_tab_edit_and_use(ui, app):
    ui.click("[data-testid=sb-environments]")
    T(ui, "globals-row").click()
    T(ui, "env-add").click()
    T(ui, "env-key").last.fill("gv")
    T(ui, "env-val").last.fill("GLOBALVAL")
    T(ui, "env-save").click()
    eventually_globals = app.api("GET", "/api/globals")["values"]
    assert any(v["key"] == "gv" and v["value"] == "GLOBALVAL" for v in eventually_globals)
