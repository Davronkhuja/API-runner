"""Ajratgichlar: javob paneli (ustma-ust/yonma-yon), sidebar, Console — o'lcham HAQIQATAN ko'rinadigan joyni o'zgartirishi (rect), clamp, dblclick, saqlash, klaviatura."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "r", "name": "Req", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/echo?a=1"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.set_viewport_size({"width": 1280, "height": 860})
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.locator("[data-name='Req']").dblclick()
    expect(T(page, "request-editor")).to_be_visible()
    T(page, "send").click()
    expect(T(page, "resp-status")).to_have_text("200")
    return page


def box(p, sel):
    return p.locator(sel).first.bounding_box()


def drag(p, sel, dx=0, dy=0, steps=6):
    b = box(p, sel)
    x, y = b["x"] + b["width"] / 2 - (b["width"] / 2 - 4 if sel.endswith("resp-resizer]") and b["width"] > 200 else 0), b["y"] + b["height"] / 2
    x = b["x"] + 40 if b["width"] > 200 else b["x"] + b["width"] / 2
    y = b["y"] + 4 if b["height"] > 200 else b["y"] + b["height"] / 2
    p.mouse.move(x, y)
    p.mouse.down()
    p.mouse.move(x + dx, y + dy, steps=steps)
    p.mouse.up()


RES = "[data-testid=resp-resizer]"
RESP = "[data-testid=response]"
REQ = ".req-pane"
WORK = "[data-testid=work]"


def sizes(p):
    r, q, w = box(p, RESP), box(p, REQ), box(p, WORK)
    return r, q, w


# ── ustma-ust ──
def test_dragging_up_and_down_really_moves_the_response_top_and_resizes_both_panes(ui):
    r0, q0, w = sizes(ui)
    drag(ui, RES, dy=-120)
    r1, q1, _ = sizes(ui)
    assert r1["height"] > r0["height"] + 100 and r1["y"] < r0["y"] - 100                          # javob balandligi VA top o'zgardi
    assert q1["height"] < q0["height"] - 100                                                      # so'rov qismi qisqardi (oldin qisqarmasdi)
    assert r1["y"] + r1["height"] <= w["y"] + w["height"] + 1                                     # pastga, ko'rinmas joyga o'smaydi
    drag(ui, RES, dy=90)
    r2, q2, _ = sizes(ui)
    assert r2["height"] < r1["height"] - 70 and r2["y"] > r1["y"] + 70 and q2["height"] > q1["height"] + 70


def test_clamp_keeps_each_pane_at_least_120px(ui):
    drag(ui, RES, dy=-3000)
    r, q, _ = sizes(ui)
    assert q["height"] >= 119 - 0 and r["height"] > q["height"]
    drag(ui, RES, dy=3000)
    r, q, w = sizes(ui)
    assert r["height"] >= 119 and q["height"] > r["height"]
    assert r["y"] + r["height"] <= w["y"] + w["height"] + 1


def test_double_click_restores_50_50(ui):
    drag(ui, RES, dy=-150)
    ui.locator(RES).dblclick(position={"x": 60, "y": 6})
    r, q, w = sizes(ui)
    assert abs(r["height"] - q["height"]) <= 14                                                   # taxminan teng (ajratgich qalinligi hisobga olinadi)


def test_size_is_stored_as_percent_per_layout_and_restored_after_reload(ui):
    drag(ui, RES, dy=-100)
    r1, _, _ = sizes(ui)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    expect(T(ui, "request-editor")).to_be_visible()
    r2, _, _ = sizes(ui)
    assert abs(r2["height"] - r1["height"]) <= 2
    saved = ui.evaluate("JSON.parse(localStorage.getItem('apirunner.split.v1'))")
    assert 0.5 < saved["stack"] < 1 and saved["side"] == 0.5                                      # foiz; yonma-yon alohida


def test_keyboard_arrows_resize_by_24px(ui):
    r0, _, _ = sizes(ui)
    T(ui, "resp-resizer").focus()
    ui.keyboard.press("ArrowUp")
    r1, _, _ = sizes(ui)
    assert abs(r1["height"] - r0["height"] - 24) <= 2 and r1["y"] < r0["y"]
    ui.keyboard.press("ArrowDown")
    ui.keyboard.press("ArrowDown")
    r2, _, _ = sizes(ui)
    assert abs(r1["height"] - r2["height"] - 48) <= 2


def test_dragging_sets_global_cursor_and_disables_text_selection_then_clears(ui):
    b = box(ui, RES)
    ui.mouse.move(b["x"] + 40, b["y"] + 6)
    ui.mouse.down()
    ui.mouse.move(b["x"] + 40, b["y"] - 40, steps=3)
    assert ui.evaluate("document.body.classList.contains('resizing-row')")
    assert ui.evaluate("getComputedStyle(document.querySelector('[data-testid=response]')).userSelect") == "none"
    assert ui.evaluate("getComputedStyle(document.querySelector('[data-testid=response]')).cursor") == "row-resize"
    ui.mouse.move(2, 2, steps=3)                                                                  # kursor panel tashqarisida ham sudrash davom etadi (pointer capture)
    ui.mouse.up()
    assert not ui.evaluate("document.body.classList.contains('resizing-row')")


def test_hit_zone_is_at_least_10px_and_hover_uses_accent(ui):
    assert box(ui, RES)["height"] >= 10
    ui.locator(RES).hover(position={"x": 60, "y": 5})
    bg = ui.evaluate("getComputedStyle(document.querySelector('[data-testid=resp-resizer]')).backgroundColor")
    assert bg != "rgba(0, 0, 0, 0)" and bg != ui.evaluate("getComputedStyle(document.querySelector('.work')).backgroundColor")


def test_window_resize_reclamps(ui):
    drag(ui, RES, dy=-3000)
    ui.set_viewport_size({"width": 1280, "height": 640})
    ui.wait_for_function("document.querySelector('.req-pane').getBoundingClientRect().height >= 119")        # ResizeObserver qayta hisoblaydi
    r, q, w = sizes(ui)
    assert q["height"] >= 119 and r["height"] >= 119
    assert r["y"] + r["height"] <= w["y"] + w["height"] + 1


def test_maximize_response_and_restore(ui):
    T(ui, "resp-maximize").click()
    _, _, w = sizes(ui)
    r = box(ui, RESP)
    assert not ui.locator(REQ).is_visible() and r["height"] >= w["height"] - 20
    T(ui, "resp-maximize").click()
    assert ui.locator(REQ).is_visible()
    r, q, _ = sizes(ui)
    assert q["height"] >= 119 and r["height"] >= 119


# ── yonma-yon ──
def test_side_by_side_drag_changes_width_and_left_edge_with_clamp_and_separate_ratio(ui):
    stack_h = sizes(ui)[0]["height"]
    T(ui, "layout-toggle").click()
    r0, q0, w = sizes(ui)
    assert r0["x"] > q0["x"]
    drag(ui, RES, dx=-150)
    r1, q1, _ = sizes(ui)
    assert r1["width"] > r0["width"] + 120 and r1["x"] < r0["x"] - 120 and q1["width"] < q0["width"] - 120
    drag(ui, RES, dx=-5000)
    r, q, _ = sizes(ui)
    assert q["width"] >= 119 and r["width"] > q["width"]
    drag(ui, RES, dx=5000)
    r, q, w = sizes(ui)
    assert r["width"] >= 119 and r["x"] + r["width"] <= w["x"] + w["width"] + 1
    ui.locator(RES).dblclick()
    r, q, _ = sizes(ui)
    assert abs(r["width"] - q["width"]) <= 14
    T(ui, "resp-resizer").focus()
    ui.keyboard.press("ArrowLeft")
    r2, _, _ = sizes(ui)
    assert abs(r2["width"] - r["width"] - 24) <= 2
    T(ui, "layout-toggle").click()                                                                # ustma-ust: oldingi balandlik tegilmagan
    assert abs(sizes(ui)[0]["height"] - stack_h) <= 2


# ── sidebar ──
def test_sidebar_resize_moves_main_area_clamps_resets_and_persists(ui):
    SB = "[data-testid=sb-wrap]"
    MAIN = ".main"
    w0, m0 = box(ui, SB), box(ui, MAIN)
    drag(ui, "[data-testid=sb-resizer]", dx=70)
    w1, m1 = box(ui, SB), box(ui, MAIN)
    assert w1["width"] > w0["width"] + 55 and m1["x"] > m0["x"] + 55 and m1["width"] < m0["width"] - 55      # ish maydoni haqiqatan siljidi
    drag(ui, "[data-testid=sb-resizer]", dx=2000)
    assert box(ui, SB)["width"] <= 421
    drag(ui, "[data-testid=sb-resizer]", dx=-2000)
    assert 179 <= box(ui, SB)["width"] <= 181
    ui.locator("[data-testid=sb-resizer]").dblclick()
    assert abs(box(ui, SB)["width"] - 284) <= 2
    T(ui, "sb-resizer").focus()
    ui.keyboard.press("ArrowRight")
    assert abs(box(ui, SB)["width"] - 300) <= 2
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    assert abs(box(ui, SB)["width"] - 300) <= 2
    ui.set_viewport_size({"width": 700, "height": 860})                                           # tor oynada clamp: yarmidan oshmaydi
    assert box(ui, SB)["width"] <= 351


# ── Console ──
def test_console_resize_changes_top_and_shrinks_workspace_clamps_resets_persists(ui):
    T(ui, "console-btn").click()
    expect(T(ui, "console")).to_be_visible()
    c0, m0 = box(ui, "[data-testid=console]"), box(ui, WORK)
    drag(ui, "[data-testid=console-resizer]", dy=-80)
    c1, m1 = box(ui, "[data-testid=console]"), box(ui, WORK)
    assert c1["height"] > c0["height"] + 60 and c1["y"] < c0["y"] - 60                            # top o'zgardi
    assert m1["height"] < m0["height"] - 60                                                       # ish maydoni qisqardi
    drag(ui, "[data-testid=console-resizer]", dy=-3000)
    assert box(ui, WORK)["height"] >= 100
    drag(ui, "[data-testid=console-resizer]", dy=3000)
    assert box(ui, "[data-testid=console]")["height"] >= 99
    ui.locator("[data-testid=console-resizer]").dblclick()
    assert abs(box(ui, "[data-testid=console]")["height"] - 240) <= 2
    T(ui, "console-resizer").focus()
    ui.keyboard.press("ArrowUp")
    assert abs(box(ui, "[data-testid=console]")["height"] - 264) <= 2
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    T(ui, "console-btn").click()
    assert abs(box(ui, "[data-testid=console]")["height"] - 264) <= 2
