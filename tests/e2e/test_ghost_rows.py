"""Jadvallarda doim bitta bo'sh "ghost" qator (Params, Headers, form-data, urlencoded, Variables, Env)."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base", "value": echo_server}]
    col["item"] = [{"id": "a", "name": "Alpha", "request": {"method": "POST", "header": [{"key": "X-A", "value": "1"}], "url": {"raw": "{{base}}/echo?p=1", "query": [{"key": "p", "value": "1"}]}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.cid = cid
    return page


def rows(p, table):
    return p.locator(f"[data-testid={table}] tbody tr")


def ghosts(p, table):
    return p.locator(f"[data-testid={table}] tbody tr[data-ghost]")


def new_tab(p):
    T(p, "new-tab").click()
    expect(T(p, "request-editor")).to_be_visible()


def cell(p, table, i, c):
    return p.locator(f"[data-testid={table}] [data-cell='{i}:{c}']")


# ── tuzilma ──
def test_new_request_tables_start_with_exactly_one_ghost_without_row_controls(ui):
    new_tab(ui)
    for section, table in (("params", "params-table"), ("headers", "headers-table")):
        ui.click(f"[data-section={section}]")
        expect(rows(ui, table)).to_have_count(1)
        g = ghosts(ui, table)
        expect(g).to_have_count(1)
        expect(g.locator("input[type=checkbox]")).to_have_count(0)
        expect(g.locator(".grip span")).to_have_count(0)
        expect(g.locator("button")).to_have_count(0)                                     # × yo'q
        expect(g.locator("input[type=text]").first).to_have_attribute("placeholder", "Kalit")
    ui.click("[data-section=body]")
    for mode, table in (("form", "form-table"), ("multipart", "formdata-table")):
        ui.select_option("[data-testid=body-mode]", mode)
        expect(ghosts(ui, table)).to_have_count(1)
    expect(ghosts(ui, "formdata-table").locator("input[type=file]")).to_have_count(0)    # ghost'da 📎 yo'q


def test_column_headers_and_bulk_edit_at_the_right_end_of_header(ui):
    new_tab(ui)
    texts = [t.strip() for t in ui.locator(".kv-head thead th").all_inner_texts()]
    assert texts[-4:-1] == ["Kalit", "Qiymat", "Tavsif"] and texts[-1] == "Bulk Edit"
    bulk = T(ui, "kv-bulk").first.bounding_box()
    desc = ui.locator(".kv-head thead th", has_text="Tavsif").bounding_box()
    assert bulk["x"] > desc["x"] + desc["width"] - 5                                      # sarlavha qatorining o'ng chetida


def test_typing_converts_ghost_to_normal_row_and_a_new_ghost_appears(ui):
    new_tab(ui)
    ui.click("[data-section=params]")
    expect(T(ui, "dirty-dot")).to_have_count(0)                                            # ghost o'zi dirty yaratmaydi
    cell(ui, "params-table", 0, 0).fill("a")
    expect(rows(ui, "params-table")).to_have_count(2)
    first = rows(ui, "params-table").nth(0)
    expect(first.locator("input[type=checkbox]")).to_be_visible()
    expect(first.locator("button[aria-label=\"Qatorni o'chirish\"]")).to_be_visible()
    expect(first.locator(".grip span")).to_be_visible()
    expect(ghosts(ui, "params-table")).to_have_count(1)
    expect(T(ui, "dirty-dot")).to_have_count(1)                                            # yozish — dirty
    cell(ui, "params-table", 1, 2).fill("faqat tavsif")                                   # tavsif yozilsa ham oddiy qator
    expect(rows(ui, "params-table")).to_have_count(3)
    expect(ghosts(ui, "params-table")).to_have_count(1)
    cell(ui, "params-table", 1, 2).fill("")                                                # bo'shatilsa — ortiqcha bo'sh qatorlar bittaga qisqaradi
    expect(rows(ui, "params-table")).to_have_count(2)
    expect(ghosts(ui, "params-table")).to_have_count(1)


def test_opening_a_saved_request_has_ghosts_and_is_not_dirty_and_ghost_is_never_saved(ui, app):
    ui.locator("[data-name='Alpha']").dblclick()
    ui.click("[data-section=params]")
    expect(rows(ui, "params-table")).to_have_count(2)                                       # p=1 + ghost
    ui.click("[data-section=headers]")
    expect(rows(ui, "headers-table")).to_have_count(2)
    expect(T(ui, "dirty-dot")).to_have_count(0)
    expect(T(ui, "url")).to_have_text("{{base}}/echo?p=1")                                 # URL'ga hech narsa qo'shilmadi
    cell(ui, "headers-table", 1, 0).fill("X-B")
    cell(ui, "headers-table", 1, 1).fill("2")
    T(ui, "save").click()
    expect(T(ui, "dirty-dot")).to_have_count(0)
    req = app.api("GET", f"/api/collections/{ui.cid}")["item"][0]["request"]
    assert [h["key"] for h in req["header"]] == ["X-A", "X-B"]                              # ghost saqlanmadi
    assert [q["key"] for q in req["url"]["query"]] == ["p"] and req["url"]["raw"].endswith("echo?p=1")
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.click("[data-section=headers]")
    expect(rows(ui, "headers-table")).to_have_count(3)
    expect(ghosts(ui, "headers-table")).to_have_count(1)


# ── URL ↔ Params ──
def test_url_sync_keeps_exactly_one_ghost(ui):
    new_tab(ui)
    ui.click("[data-section=params]")
    ui.fill("[data-testid=url]", "http://h/x?id=")                                          # bo'sh qiymatli parametr
    expect(rows(ui, "params-table")).to_have_count(2)
    expect(cell(ui, "params-table", 0, 0)).to_have_value("id")
    expect(ghosts(ui, "params-table")).to_have_count(1)
    ui.fill("[data-testid=url]", "http://h/x?a=1&b=2&c=")
    expect(rows(ui, "params-table")).to_have_count(4)
    expect(ghosts(ui, "params-table")).to_have_count(1)
    ui.fill("[data-testid=url]", "http://h/x")                                              # barcha parametr URL'dan ketdi
    expect(rows(ui, "params-table")).to_have_count(1)
    expect(ghosts(ui, "params-table")).to_have_count(1)
    ui.fill("[data-testid=url]", "http://h/x?q=1")
    cell(ui, "params-table", 1, 0).fill("w")                                                # ghost'ga yozish URL'ni "?q=1&w=" ga o'zgartiradi
    expect(T(ui, "url")).to_have_text("http://h/x?q=1&w=")
    cell(ui, "params-table", 1, 0).fill("")
    expect(T(ui, "url")).to_have_text("http://h/x?q=1")                                    # ghost URL'ga '&' qo'shmaydi


def test_removing_rows_keeps_one_ghost_and_never_leaves_empty_table(ui):
    new_tab(ui)
    ui.click("[data-section=headers]")
    for k in ("A", "B", "C"):
        cell(ui, "headers-table", rows(ui, "headers-table").count() - 1, 0).fill(k)
    expect(rows(ui, "headers-table")).to_have_count(4)
    rows(ui, "headers-table").nth(1).locator("button").click()                              # o'rtadagisini o'chirish
    expect(rows(ui, "headers-table")).to_have_count(3)
    expect(ghosts(ui, "headers-table")).to_have_count(1)
    for _ in range(2):
        rows(ui, "headers-table").nth(0).locator("button").click()
    expect(rows(ui, "headers-table")).to_have_count(1)                                       # faqat ghost
    expect(ghosts(ui, "headers-table")).to_have_count(1)


def test_bulk_edit_roundtrip_leaves_exactly_one_ghost(ui):
    new_tab(ui)
    ui.click("[data-section=headers]")
    T(ui, "kv-bulk").first.click()
    ui.fill("[data-testid=headers-table-bulk]", "X-One:1\n//X-Two:2")
    T(ui, "kv-bulk").first.click()
    expect(rows(ui, "headers-table")).to_have_count(3)
    expect(ghosts(ui, "headers-table")).to_have_count(1)
    T(ui, "kv-bulk").first.click()
    ui.fill("[data-testid=headers-table-bulk]", "")
    T(ui, "kv-bulk").first.click()
    expect(rows(ui, "headers-table")).to_have_count(1)
    expect(ghosts(ui, "headers-table")).to_have_count(1)


# ── klaviatura ──
def test_enter_and_tab_move_between_cells_and_rows(ui):
    new_tab(ui)
    ui.click("[data-section=headers]")
    cell(ui, "headers-table", 0, 0).click()
    ui.keyboard.type("K1")
    ui.keyboard.press("Enter")
    expect(cell(ui, "headers-table", 0, 1)).to_be_focused()
    ui.keyboard.type("V1")
    ui.keyboard.press("Enter")
    expect(cell(ui, "headers-table", 0, 2)).to_be_focused()
    ui.keyboard.type("izoh")
    ui.keyboard.press("Enter")                                                               # keyingi qatorning kalit katagi (yangi ghost)
    expect(cell(ui, "headers-table", 1, 0)).to_be_focused()
    ui.keyboard.type("K2")
    ui.keyboard.press("Tab")                                                                 # Tab — qiymat katagi
    expect(cell(ui, "headers-table", 1, 1)).to_be_focused()
    ui.keyboard.press("Tab")
    expect(cell(ui, "headers-table", 1, 2)).to_be_focused()
    ui.keyboard.press("Tab")                                                                 # oxirgi katakdan Tab — keyingi qator kaliti
    expect(cell(ui, "headers-table", 2, 0)).to_be_focused()
    ui.keyboard.press("Shift+Tab")                                                           # orqaga — oldingi qator tavsifi
    expect(cell(ui, "headers-table", 1, 2)).to_be_focused()
    ui.keyboard.press("Alt+Backspace")                                                       # qatorni o'chirish
    expect(rows(ui, "headers-table")).to_have_count(2)
    assert cell(ui, "headers-table", 0, 0).input_value() == "K1" and cell(ui, "headers-table", 0, 2).input_value() == "izoh"
    expect(ghosts(ui, "headers-table")).to_have_count(1)


def test_file_row_from_ghost_makes_a_new_ghost(ui, tmp_path):
    f = tmp_path / "up.txt"
    f.write_text("x")
    new_tab(ui)
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "multipart")
    cell(ui, "formdata-table", 0, 0).fill("doc")
    ui.locator("[data-testid=formdata-table] [data-testid=fd-type]").first.select_option("file")
    ui.locator("[data-testid=formdata-table] input[type=file]").first.set_input_files(str(f))
    expect(T(ui, "formdata-table")).to_contain_text("up.txt")
    expect(rows(ui, "formdata-table")).to_have_count(2)
    expect(ghosts(ui, "formdata-table")).to_have_count(1)


# ── Variables / Env ──
def test_variables_table_ghost_row_replaces_add_button_and_is_not_saved(ui, app):
    ui.locator("[data-name='Col']").dblclick()
    ui.click("[data-scope-section=vars]")
    expect(T(ui, "var-add")).to_have_count(0)
    expect(rows(ui, "scope-vars")).to_have_count(2)                                         # base + ghost
    expect(ghosts(ui, "scope-vars").locator("input[type=checkbox]")).to_have_count(0)
    expect(ghosts(ui, "scope-vars").locator("select")).to_have_count(0)
    expect(T(ui, "dirty-dot")).to_have_count(0)
    ui.locator("[data-testid=var-key]").nth(1).fill("extra")
    expect(rows(ui, "scope-vars")).to_have_count(3)
    expect(ghosts(ui, "scope-vars")).to_have_count(1)
    T(ui, "scope-save").click()
    expect(ui.locator(".toast")).to_contain_text("Saqlandi")
    col = app.api("GET", f"/api/collections/{ui.cid}")
    assert [v["key"] for v in col["variable"]] == ["base", "extra"]


def test_environment_and_globals_tables_have_ghost_rows_filtered_on_save(ui, app):
    ui.click("[data-testid=sb-environments]")
    T(ui, "new-env").click()
    expect(T(ui, "env-add")).to_have_count(0)
    expect(ui.locator("[data-testid=env-tab] tbody tr[data-ghost]")).to_have_count(1)
    expect(T(ui, "dirty-dot")).to_have_count(0)
    T(ui, "env-key").first.fill("host")
    T(ui, "env-val").first.fill("h1")
    expect(ui.locator("[data-testid=env-tab] tbody tr")).to_have_count(2)
    T(ui, "env-save").click()
    eid = app.api("GET", "/api/workspace")["environments"][0]["id"]
    vals = app.api("GET", f"/api/environments/{eid}")["values"]
    assert [(v["key"], v["value"]) for v in vals] == [("host", "h1")]                       # ghost saqlanmadi
    ui.click("[data-testid=sb-environments]")
    T(ui, "globals-row").click()
    expect(ui.locator("[data-testid=env-tab] tbody tr[data-ghost]")).to_have_count(1)
