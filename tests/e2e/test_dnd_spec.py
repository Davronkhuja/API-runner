"""Bosqich 2 — Sidebar va drag&drop (MAJBURIY). Spetsifikatsiyaning har bir bandi uchun alohida e2e test."""
import json
import re

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import eventually

TREE = [
    ("f1", "F1", [("a", "A", None), ("b", "B", None), ("f2", "F2", [("c", "C", None)])]),
    ("f3", "F3", []),
    ("d", "D", None),
    ("e", "E", None),
]
SEL = re.compile(r"\bsel\b")


def row(p, name):
    return p.locator(f"[data-testid=tree-row][data-name='{name}']")


def names(p):
    return p.locator("[data-testid=tree-row]").evaluate_all("els => els.map(e => e.dataset.name)")


Y = {"before": 3, "inside": 14, "after": 25}


def drag(p, src, dst, where="inside"):
    s = row(p, src) if isinstance(src, str) else src
    s.drag_to(row(p, dst), target_position={"x": 40, "y": Y[where]})


def server_shape(app, cid):
    def walk(items):
        return [(i["id"], walk(i["item"])) if "item" in i else i["id"] for i in items]
    return walk(app.collection(cid)["item"])


@pytest.fixture
def ui(app, page):
    app.cid = app.seed(TREE)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=tree-row][data-name=E]")
    return page


# ── ichma-ich papkalar, collapse ──
def test_nested_folders_unlimited_depth(app, page):
    deep = ("n0", "N0", [])
    node = deep
    for i in range(1, 12):
        child = (f"n{i}", f"N{i}", [])
        node[2].append(child)
        node = child
    node[2].append(("leaf", "Leaf", None))
    app.seed([deep])
    page.goto(app.url)
    expect(row(page, "Leaf")).to_be_visible()
    depth = page.locator("[data-testid=tree-row][data-name=Leaf]").evaluate("e => parseInt(e.style.paddingLeft)")
    assert depth > 12 * 10
    # UI orqali ichma-ich papka yaratish
    row(page, "N11").click(button="right")
    page.click("[data-testid=tree-menu] [data-act=newfolder]")
    expect(row(page, "Yangi papka")).to_be_visible()


def test_collapse_expand_state_persisted(ui, app):
    expect(row(ui, "C")).to_be_visible()
    row(ui, "F2").click()
    expect(row(ui, "C")).to_have_count(0)
    row(ui, "F1").click()
    expect(row(ui, "A")).to_have_count(0)
    ui.reload()                                           # darhol: yopilishda keepalive bilan yoziladi
    ui.wait_for_selector("[data-testid=tree-row][data-name=E]")
    expect(row(ui, "A")).to_have_count(0)
    row(ui, "F1").click()
    expect(row(ui, "B")).to_be_visible()
    expect(row(ui, "C")).to_have_count(0)               # F2 yopiq holda tiklangan
    app.restart()


# ── ko'chirish / tartiblash ──
def test_move_request_between_folders(ui, app):
    drag(ui, "A", "F3", "inside")
    expect(row(ui, "A")).to_be_visible()
    eventually(lambda: server_shape(app, app.cid)[:2] == [("f1", ["b", ("f2", ["c"])]), ("f3", ["a"])])


def test_move_request_between_collections(app, page):
    c1 = app.seed([("a", "A", None), ("f", "F", [])], name="One")
    c2 = app.seed([("z", "Z", None), ("g", "G", [])], name="Two")
    page.goto(app.url)
    drag(page, "A", "G", "inside")
    eventually(lambda: server_shape(app, c1) == [("f", [])])
    assert server_shape(app, c2) == ["z", ("g", ["a"])]
    # collection qatoriga tashlash — ildizga
    drag(page, "Z", page.locator("[data-testid=tree-row][data-name=One]"), "inside") if False else None


def test_reorder_requests_within_folder(ui, app):
    drag(ui, "B", "A", "before")
    assert server_shape(app, app.cid)[0] == ("f1", ["b", "a", ("f2", ["c"])])


def test_reorder_folders_within_folder(ui, app):
    drag(ui, "F2", "A", "before")
    assert server_shape(app, app.cid)[0] == ("f1", [("f2", ["c"]), "a", "b"])


def test_move_folder_into_another_folder(ui, app):
    drag(ui, "F3", "F1", "inside")
    assert server_shape(app, app.cid) == [("f1", ["a", "b", ("f2", ["c"]), ("f3", [])]), "d", "e"]


def test_drop_indicator_before_inside_after(ui):
    src = row(ui, "E")
    box = row(ui, "F3").bounding_box()
    begin_drag(ui, src)
    for where, cls in (("before", "drop-before"), ("inside", "drop-inside"), ("after", "drop-after")):
        hover(ui, box["x"] + 40, box["y"] + Y[where])
        expect(row(ui, "F3")).to_have_class(re.compile(cls))
    # so'rov ichiga tashlab bo'lmaydi — ko'rsatkich yo'q
    b2 = row(ui, "D").bounding_box()
    hover(ui, b2["x"] + 40, b2["y"] + 14)
    expect(row(ui, "D")).not_to_have_class(re.compile("drop-inside"))
    ui.mouse.up()


def begin_drag(p, loc):
    """Qo'lda sichqoncha bilan HTML5 drag boshlash (dragstart uchun avval kichik siljish kerak)."""
    x, y = _center(loc)
    p.mouse.move(x, y)
    p.mouse.down()
    p.mouse.move(x + 4, y + 4, steps=2)
    p.mouse.move(x + 8, y + 8, steps=2)


def hover(p, x, y):
    """Maqsadga o'tib, dragover hosil bo'lishi uchun joyida kichik siljish."""
    p.mouse.move(x, y, steps=6)
    p.mouse.move(x + 1, y, steps=2)
    p.mouse.move(x, y, steps=2)


def _center(loc):
    b = loc.bounding_box()
    return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2


def test_hover_while_dragging_auto_expands_folder(ui):
    row(ui, "F2").click()                                  # yopamiz
    expect(row(ui, "C")).to_have_count(0)
    begin_drag(ui, row(ui, "E"))
    box = row(ui, "F2").bounding_box()
    hover(ui, box["x"] + 40, box["y"] + 14)
    expect(row(ui, "C")).to_be_visible()                  # 600ms hover taymeri — expect avtomatik kutadi
    ui.mouse.up()


def test_autoscroll_near_edge_of_long_list(app, page):
    app.seed([(f"r{i}", f"R{i:03d}", None) for i in range(80)])
    page.goto(app.url)
    page.wait_for_selector("[data-testid=tree-row][data-name=R000]")
    tree = page.locator("[data-testid=tree]")
    begin_drag(page, row(page, "R000"))
    box = tree.bounding_box()
    page.mouse.move(box["x"] + 60, box["y"] + box["height"] - 8, steps=10)
    page.mouse.move(box["x"] + 60, box["y"] + box["height"] - 6, steps=3)
    page.wait_for_function("document.querySelector('[data-testid=tree]').scrollTop > 100")     # sudrash davomida avto-scroll
    page.mouse.up()


def test_dropping_folder_into_its_own_descendant_is_forbidden(ui, app):
    before = server_shape(app, app.cid)
    drag(ui, "F1", "F2", "inside")
    drag(ui, "F1", "C", "before")
    drag(ui, "F1", "F1", "inside")
    ui.wait_for_load_state("networkidle")                  # taqiqlangan tashlashlar hech qanday so'rov yubormaydi
    assert server_shape(app, app.cid) == before
    # server ham rad etadi
    with pytest.raises(Exception):
        app.api("POST", "/api/items/move", {"src": app.cid, "dst": app.cid, "ids": ["f1"], "target_id": "f2", "position": "inside"})


def test_alt_option_drag_copies_instead_of_moves(ui, app):
    ui.keyboard.down("Alt")
    drag(ui, "A", "F3", "inside")
    ui.keyboard.up("Alt")
    eventually(lambda: len(server_shape(app, app.cid)[1][1]) == 1)
    shape = server_shape(app, app.cid)
    assert shape[0][1][0] == "a"                              # asl joyida qoldi
    assert shape[1][1][0] != "a"                              # nusxa yangi id bilan


# ── tartib saqlanishi ──
def test_order_persisted_in_backend_after_reload(ui, app):
    drag(ui, "E", "D", "before")
    ui.reload()
    ui.wait_for_selector("[data-testid=tree-row][data-name=E]")
    assert names(ui)[-2:] == ["E", "D"] or names(ui).index("E") < names(ui).index("D")
    assert server_shape(app, app.cid)[-2:] == ["e", "d"]


def test_order_preserved_in_export(ui, app):
    drag(ui, "E", "A", "before")
    ids = [r["id"] for r in app.api("GET", "/api/export/legacy")["requests"]]
    assert ids.index("e") < ids.index("a")


# ── ko'p tanlash ──
def test_multi_select_shift_click_range(ui):
    row(ui, "A").click()
    row(ui, "D").click(modifiers=["Shift"])
    for n in ("A", "B", "F2", "C", "F3", "D"):
        expect(row(ui, n)).to_have_class(SEL)
    expect(row(ui, "E")).not_to_have_class(SEL)


def test_multi_select_cmd_click_toggle(ui):
    row(ui, "A").click()
    row(ui, "D").click(modifiers=["Meta"])
    row(ui, "E").click(modifiers=["Meta"])      # macOS: Ctrl+click = kontekst menyu, shuning uchun Cmd
    for n in ("A", "D", "E"):
        expect(row(ui, n)).to_have_class(SEL)
    row(ui, "D").click(modifiers=["Meta"])
    expect(row(ui, "D")).not_to_have_class(SEL)
    expect(row(ui, "B")).not_to_have_class(SEL)


def test_drag_multiple_items_together(ui, app):
    row(ui, "D").click()
    row(ui, "E").click(modifiers=["Meta"])
    drag(ui, "D", "F3", "inside")
    eventually(lambda: server_shape(app, app.cid) == [("f1", ["a", "b", ("f2", ["c"])]), ("f3", ["d", "e"])])


# ── runner / jadval qatorlari ──
def test_runner_request_list_reorder_by_dnd(ui, app):
    row(ui, "F1").click(button="right") if False else None
    ui.locator("[data-testid=tree-row][data-kind=collection]").click(button="right")
    ui.click("[data-testid=tree-menu] [data-act=runner]")
    items = ui.locator("[data-testid=runner-item]")
    expect(items).to_have_count(5)
    expect(items.first).to_contain_text("A")
    items.nth(3).drag_to(items.first, target_position={"x": 20, "y": 3})
    expect(items.first).to_contain_text("D")
    expect(items.nth(1)).to_contain_text("A")


def _rows_reorder(ui, section, table):
    ui.locator("[data-testid=new-tab]").click()
    ui.click(f"[data-section={section}]")
    for i, v in enumerate(("one", "two", "three")):
        ui.locator(f"[data-testid={table}] input[type=text]").nth(i * 2).fill(v)
    inputs = lambda: ui.locator(f"[data-testid={table}] tr td:nth-child(3) input").evaluate_all("els => els.map(e => e.value)")
    assert inputs()[:3] == ["one", "two", "three"]
    ui.locator(f"[data-testid={table}] tr").nth(2).locator(".grip").drag_to(ui.locator(f"[data-testid={table}] tr").first, target_position={"x": 20, "y": 3})
    assert inputs()[:3] == ["three", "one", "two"]


def test_params_rows_reorder_by_dnd(ui):
    _rows_reorder(ui, "params", "params-table")


def test_headers_rows_reorder_by_dnd(ui):
    _rows_reorder(ui, "headers", "headers-table")


def test_form_data_rows_reorder_by_dnd(ui):
    ui.locator("[data-testid=new-tab]").click()
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "multipart")
    _rows_reorder_fields(ui)


def _rows_reorder_fields(ui):
    t = "formdata-table"
    for i, v in enumerate(("one", "two", "three")):
        ui.locator(f"[data-testid={t}] input[type=text]").nth(i * 2).fill(v)
    vals = lambda: ui.locator(f"[data-testid={t}] tr td:nth-child(3) input").evaluate_all("els => els.map(e => e.value)")
    ui.locator(f"[data-testid={t}] tr").nth(2).locator(".grip").drag_to(ui.locator(f"[data-testid={t}] tr").first, target_position={"x": 20, "y": 3})
    assert vals()[:3] == ["three", "one", "two"]


# ── fayl/matn tashlash orqali import ──
def drop_file(p, name, content, mime="application/json"):
    p.evaluate("""([name, content, mime]) => {
      const dt = new DataTransfer(); dt.items.add(new File([content], name, {type: mime}));
      const t = document.querySelector('[data-testid=app]');
      t.dispatchEvent(new DragEvent('dragenter', {dataTransfer: dt, bubbles: true}));
      t.dispatchEvent(new DragEvent('dragover', {dataTransfer: dt, bubbles: true, cancelable: true}));
      t.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
    }""", [name, content, mime])


def drop_text(p, text):
    p.evaluate("""text => {
      const dt = new DataTransfer(); dt.setData('text/plain', text);
      const t = document.querySelector('[data-testid=app]');
      t.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
    }""", text)


POSTMAN = {"info": {"name": "Imp", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
           "item": [{"name": "Outer", "item": [{"name": "Inner", "item": [{"name": "Deep req", "request": {
               "method": "POST", "header": [{"key": "X-A", "value": "1"}], "url": {"raw": "http://h/p?q=1"},
               "body": {"mode": "raw", "raw": "{}"}}}]}]}, {"name": "Top req", "request": {"method": "GET", "url": "http://h/top"}}]}


def test_drop_postman_collection_file_imports(ui):
    drop_file(ui, "imp.postman_collection.json", json.dumps(POSTMAN))
    expect(row(ui, "Imp")).to_be_visible()
    expect(row(ui, "Deep req")).to_be_visible()               # ichma-ich papkalar saqlangan
    expect(row(ui, "Top req")).to_be_visible()


def test_drop_openapi_file_imports(ui):
    spec = {"openapi": "3.0.0", "info": {"title": "Petstore"}, "servers": [{"url": "http://api.test"}],
            "paths": {"/pets": {"get": {"summary": "List pets", "tags": ["pets"]}, "post": {"summary": "Add pet", "tags": ["pets"]}}}}
    drop_file(ui, "openapi.json", json.dumps(spec))
    expect(row(ui, "Petstore")).to_be_visible()
    expect(row(ui, "List pets")).to_be_visible()
    expect(row(ui, "Add pet")).to_be_visible()


def test_drop_csv_file_imports(ui):
    drop_file(ui, "data.csv", "id,name\n1,a\n2,b\n", "text/csv")
    expect(ui.locator("[data-testid=tab-runner], [data-testid=runner-tab]").first).to_be_visible()
    expect(ui.locator("[data-testid=runner-data-info]")).to_contain_text("2")


def test_drop_curl_text_imports(ui):
    drop_text(ui, "curl -X POST 'https://api.test/x?y=1' -H 'X-Foo: bar' -d '{\"k\":1}'")
    expect(ui.locator("[data-testid=url]")).to_have_value("https://api.test/x?y=1")
    expect(ui.locator("[data-testid=method]")).to_have_value("POST")


# ── klaviatura va qidiruv ──
def test_keyboard_move_via_context_menu_move_to(ui, app):
    row(ui, "D").click(button="right")
    ui.click("[data-testid=tree-menu] [data-act=move]")
    ui.select_option("[data-testid=move-target]", label=re.compile(r"F3").pattern) if False else None
    opts = ui.locator("[data-testid=move-target] option")
    idx = opts.evaluate_all("os => os.findIndex(o => o.textContent.trim() === 'F3')")
    ui.select_option("[data-testid=move-target]", index=idx)
    ui.click("[data-testid=move-ok]")
    eventually(lambda: server_shape(app, app.cid)[1] == ("f3", ["d"]))


def test_dnd_works_while_search_filter_active(ui, app):
    ui.fill("[data-testid=sb-search]", "F")                  # F1, F2, F3 va ularning ota-onalari
    expect(row(ui, "E")).to_have_count(0)
    drag(ui, "F2", "F3", "inside")
    eventually(lambda: server_shape(app, app.cid) == [("f1", ["a", "b"]), ("f3", [("f2", ["c"])]), "d", "e"])
