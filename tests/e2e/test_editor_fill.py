"""Muharrirlar so'rov panelining qolgan balandligini to'liq egallaydi (qat'iy px emas): JSON/GraphQL/skript, resizer bilan birga o'zgaradi, yonma-yon ham."""
import json

import pytest
from playwright.sync_api import expect

from conftest import set_body_mode

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
BIG = json.dumps({"items": [{"id": i, "name": f"item-{i}", "ok": True} for i in range(24)]}, indent=2)      # 100+ qator


@pytest.fixture(params=[(1440, 900), (1920, 1080)], ids=["1440x900", "1920x1080"])
def ui(request, app, page, echo_server):
    page.set_viewport_size({"width": request.param[0], "height": request.param[1]})
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    T(page, "new-tab").click()
    page.select_option("[data-testid=method]", "POST")
    page.fill("[data-testid=url]", echo_server + "/echo")
    page.click("[data-section=body]")
    return page


def rect(p, sel):
    return p.locator(sel).first.bounding_box()


def fill_json(p):
    p.locator("[data-testid=body-raw]").click()
    p.keyboard.insert_text(BIG)


def gap_below(p, inner):
    """Muharrir pastki chegarasi bilan .editor (so'rov paneli) pastki chegarasi orasidagi bo'sh joy."""
    return rect(p, ".editor")["y"] + rect(p, ".editor")["height"] - (rect(p, inner)["y"] + rect(p, inner)["height"])


def test_json_editor_fills_panel_even_when_content_is_short_and_shows_first_line(ui):
    expect(ui.locator(".body-editor .cm-editor")).to_be_visible()
    assert gap_below(ui, ".body-editor") <= 22                                                    # qisqa kontent — baribir panelni to'ldiradi, "o'lik" bo'sh joy yo'q
    h = rect(ui, ".body-editor")["height"]
    assert h > 120
    fill_json(ui)
    ui.evaluate("document.querySelector('.body-editor .cm-scroller').scrollTop = 0")
    first = ui.locator(".body-editor .cm-line").first
    expect(first).to_have_text("{")
    assert first.bounding_box()["y"] >= rect(ui, ".body-editor")["y"] - 1                         # birinchi qator ko'rinadi
    sc = ui.evaluate("(() => { const s = document.querySelector('.body-editor .cm-scroller'); return [s.scrollHeight, s.clientHeight] })()")
    assert sc[0] > sc[1]                                                                          # 100+ qator: scroll faqat kontent sig'masa


def test_editor_follows_the_resizer_in_both_directions_without_gaps(ui):
    ed0 = rect(ui, ".body-editor")["height"]
    b = rect(ui, "[data-testid=resp-resizer]")
    for dy, grow in ((-150, False), (260, True)):
        ui.mouse.move(b["x"] + 40, b["y"] + 6)
        ui.mouse.down()
        ui.mouse.move(b["x"] + 40, b["y"] + 6 + dy, steps=6)
        ui.mouse.up()
        b = rect(ui, "[data-testid=resp-resizer]")
        h = rect(ui, ".body-editor")["height"]
        assert (h < ed0 - 100) if not grow else (h > ed0 - 60)
        assert gap_below(ui, ".body-editor") <= 22
        ed0 = h if not grow else ed0


def test_json_with_short_content_after_reload_editor_still_fills(ui):
    fill_json(ui)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.click("[data-section=body]")
    expect(ui.locator(".body-editor .cm-line").first).to_have_text("{")
    assert gap_below(ui, ".body-editor") <= 22


def test_graphql_editors_share_the_remaining_height(ui):
    set_body_mode(ui, "graphql")
    q, v = rect(ui, "[data-testid=gql-query]"), rect(ui, "[data-testid=gql-vars]")
    qh, vh = q["height"], v["height"]
    assert qh > vh > 40
    assert gap_below(ui, "[data-testid=graphql-panel]") <= 22


def test_scripts_editor_fills_and_follows_side_by_side_layout(ui):
    ui.click("[data-section=scripts]")
    box = ".script-box"
    assert gap_below(ui, box) <= 24 and rect(ui, box)["height"] > 120
    T(ui, "layout-toggle").click()
    assert gap_below(ui, box) <= 24
    assert rect(ui, box)["height"] > rect(ui, ".editor")["height"] - 140


def test_content_type_is_one_text_that_becomes_an_input_on_click(ui):
    T(ui, "body-format").select_option("json")
    expect(T(ui, "content-type-auto")).to_have_text("Content-Type: application/json")
    expect(T(ui, "content-type")).to_have_count(0)                                                # takror yo'q: faqat matn
    T(ui, "content-type-auto").click()
    expect(T(ui, "content-type")).to_be_focused()
    expect(T(ui, "content-type-auto")).to_have_count(0)
    T(ui, "content-type").fill("application/vnd.api+json")
    T(ui, "content-type").press("Enter")
    expect(T(ui, "content-type-auto")).to_have_text("Content-Type: application/vnd.api+json")
