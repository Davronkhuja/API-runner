"""Import dialogi (ko'p format, oldindan ko'rish, konflikt holati) va eksport (collection, muhit, globals, workspace zip)."""
import json
import pathlib

import pytest
from playwright.sync_api import expect

FX = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def open_import(p):
    T(p, "import-btn").click()
    expect(T(p, "import-dialog")).to_be_visible()


def add_file(p, *path):
    T(p, "import-dlg-file").set_input_files(str(FX.joinpath(*path)))


def tree_names(p):
    return p.locator("[data-testid=tree-row]").evaluate_all("els => els.map(e => e.dataset.name)")


def test_openapi_yaml_file_preview_and_import(ui):
    open_import(ui)
    add_file(ui, "openapi", "petstore3.yaml")
    expect(T(ui, "import-preview")).to_contain_text("OpenAPI")
    expect(T(ui, "import-preview")).to_contain_text("2 papka, 8 so'rov")
    expect(T(ui, "import-warnings")).to_have_count(0)
    T(ui, "import-confirm").click()
    expect(T(ui, "import-dialog")).to_have_count(0)
    names = tree_names(ui)
    assert "Swagger Petstore" in names and "pet" in names and "store" in names and "Health check" in names


def test_conflict_choices_merge_replace_copy_and_skip(ui, app):
    open_import(ui)
    add_file(ui, "postman", "newman_reporter_sample.json")
    T(ui, "import-confirm").click()
    expect(T(ui, "import-dialog")).to_have_count(0)
    base = [c for c in app.api("GET", "/api/workspace")["collections"] if c["name"] != "Mening collection"]
    assert len(base) == 1
    # qayta — konflikt
    open_import(ui)
    add_file(ui, "postman", "newman_reporter_sample.json")
    expect(T(ui, "import-conflict")).to_be_visible()
    sel = T(ui, "import-action")
    assert sel.input_value() == "copy"
    labels = sel.locator("option").all_inner_texts()
    assert labels[0] == "Yangi nusxa" and labels[1].startswith("Birlashtirish (+0 so'rov)") and "Savatga" in labels[2] and labels[3] == "O'tkazib yuborish"
    sel.select_option("skip")
    expect(T(ui, "import-confirm")).to_be_disabled()                                         # hech narsa tanlanmagan
    sel.select_option("merge")
    T(ui, "import-confirm").click()
    assert len([c for c in app.api("GET", "/api/workspace")["collections"] if c["name"] != "Mening collection"]) == 1       # birlashtirish yangi collection yaratmadi
    open_import(ui)
    add_file(ui, "postman", "newman_reporter_sample.json")
    T(ui, "import-action").select_option("copy")
    T(ui, "import-confirm").click()
    expect(ui.locator("[data-testid=tree-row][data-kind=collection]")).to_have_count(3)
    open_import(ui)
    add_file(ui, "postman", "newman_reporter_sample.json")
    T(ui, "import-action").select_option("replace")
    T(ui, "import-confirm").click()
    expect(T(ui, "import-dialog")).to_have_count(0)
    rows = app.api("GET", "/api/trash")
    assert len(rows) == 1 and rows[0]["kind"] == "collection"                                  # almashtirilgani Savatda


def test_insomnia_shows_each_item_and_allows_unchecking_environment(ui, app):
    open_import(ui)
    add_file(ui, "insomnia", "insomnia_v4.json")
    expect(T(ui, "import-item")).to_have_count(2)
    expect(T(ui, "import-item").nth(0)).to_contain_text("Shop API")
    expect(T(ui, "import-item").nth(1)).to_contain_text("Muhit")
    T(ui, "import-item-on").nth(1).uncheck()
    expect(T(ui, "import-confirm")).to_contain_text("Import (1)")
    T(ui, "import-confirm").click()
    expect(T(ui, "import-dialog")).to_have_count(0)
    ws = app.api("GET", "/api/workspace")
    assert "Shop API" in [c["name"] for c in ws["collections"]] and ws["environments"] == []


def test_multiple_curl_commands_become_one_collection_but_single_stays_a_tab(ui, app):
    open_import(ui)
    T(ui, "import-tab-text").click() if T(ui, "import-tab-text").count() else ui.click("[data-tab=text]")
    T(ui, "import-text").fill((FX / "curl" / "multi.sh").read_text())
    T(ui, "import-add-text").click()
    expect(T(ui, "import-preview")).to_contain_text("cURL")
    expect(T(ui, "import-preview")).to_contain_text("5 so'rov")
    T(ui, "import-confirm").click()
    expect(T(ui, "import-dialog")).to_have_count(0)
    ws = app.api("GET", "/api/workspace")
    c = next(c for c in ws["collections"] if c["name"] == "cURL import")
    assert c["requests"] == 5


def test_har_warning_and_zip_file_are_shown(ui, app, tmp_path):
    open_import(ui)
    add_file(ui, "har", "sample.har")
    expect(T(ui, "import-warnings")).to_contain_text("Cookie")
    T(ui, "import-confirm").click()
    expect(T(ui, "import-dialog")).to_have_count(0)
    # workspace zaxirasi: eksport → qayta import (hammasi konflikt)
    ui.click("[data-testid=settings-btn]")
    with ui.expect_download() as d:
        T(ui, "io-workspace-zip").click()
    assert d.value.suggested_filename.startswith("api-runner-workspace-") and d.value.suggested_filename.endswith(".zip")
    z = tmp_path / "ws.zip"
    d.value.save_as(str(z))
    open_import(ui)
    T(ui, "import-dlg-file").set_input_files(str(z))
    expect(T(ui, "import-preview")).to_contain_text("API Runner workspace")
    expect(T(ui, "import-conflict").first).to_be_visible()


def test_invalid_and_unknown_files_show_clear_errors(ui, tmp_path):
    f = tmp_path / "x.json"
    f.write_text(json.dumps({"hello": "world"}))
    open_import(ui)
    T(ui, "import-dlg-file").set_input_files(str(f))
    expect(T(ui, "import-error")).to_contain_text("Format tanilmadi")


def test_collection_export_dialog_downloads_all_formats(ui, app):
    cid = app.api("POST", "/api/collections", {"name": "Exp col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "r", "name": "R", "request": {"method": "GET", "header": [], "url": {"raw": "https://api.test/items/:id"}}, "response": []}]
    col["variable"] = [{"key": "pub", "value": "visible", "type": "default"}, {"key": "sec", "value": "TOPSECRET", "type": "secret"}]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-testid=tree-row][data-name='Exp col']").click(button="right")
    ui.click("[data-act=export]")
    expect(T(ui, "export-dialog")).to_be_visible()
    expect(T(ui, "export-name")).to_have_text("Exp col")
    for fmt, suffix in (("postman", ".postman_collection.json"), ("openapi", ".openapi.json"), ("openapi-yaml", ".openapi.yaml")):
        ui.locator(f"[data-testid=export-fmt-{fmt}]").check()
        with ui.expect_download() as d:
            T(ui, "export-go").click()
        assert d.value.suggested_filename == "Exp_col" + suffix, d.value.suggested_filename
        body = pathlib.Path(d.value.path()).read_text()
        assert "TOPSECRET" not in body or fmt == "never"
        T(ui, "scope-export").count()
        ui.locator("[data-testid=tree-row][data-name='Exp col']").click(button="right")
        ui.click("[data-act=export]")
    ui.keyboard.press("Escape")


def test_environment_and_globals_export_buttons(ui, app):
    eid = app.api("POST", "/api/environments", {"name": "My Env"})["id"]
    e = app.api("GET", f"/api/environments/{eid}")
    e["values"] = [{"key": "a", "value": "init", "current": "cur", "enabled": True, "type": "default"}, {"key": "s", "value": "sec", "enabled": True, "type": "secret"}]
    app.api("PUT", f"/api/environments/{eid}", e)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.click("[data-testid=sb-environments]")
    T(ui, "env-row").filter(has_text="My Env").click()
    with ui.expect_download() as d:
        T(ui, "env-export-postman").click()
    assert d.value.suggested_filename == "My_Env.postman_environment.json"
    out = json.loads(pathlib.Path(d.value.path()).read_text())
    assert [v["value"] for v in out["values"]] == ["init", ""] and "cur" not in json.dumps(out) and "sec" not in [v["value"] for v in out["values"]]
