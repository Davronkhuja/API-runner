"""Sifat jarayoni (QA): real ssenariylar 1440×900 va 1920×1080, light/dark. Layout tekshiruvlari har doim; skrinshotlar `QA_SHOT_DIR` berilganda saqlanadi."""
import json
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect

from conftest import set_body_mode

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
OUT = Path(os.environ["QA_SHOT_DIR"]) if os.environ.get("QA_SHOT_DIR") else None
BODY60 = json.dumps({"applicant": {"pinfl": "30501900000000", "name": "Ali"}, "items": [{"id": i, "code": f"C-{i:03d}", "qty": i % 7, "ok": i % 2 == 0} for i in range(11)], "note": "test"}, indent=2)
assert BODY60.count("\n") >= 50


@pytest.fixture(params=[(1440, 900, "light"), (1440, 900, "dark"), (1920, 1080, "light"), (1920, 1080, "dark")], ids=lambda p: f"{p[0]}-{p[2]}")
def qa(request, app, browser, echo_server):
    w, h, theme = request.param
    ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="uz")
    ctx.add_init_script(f"try {{ localStorage.setItem('apiRunnerTheme', '{theme}') }} catch (e) {{}}")
    page = ctx.new_page()
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.add_style_tag(content="*{caret-color:transparent!important;animation:none!important;transition:none!important}")
    page.echo, page.tag = echo_server, f"{w}x{h}-{theme}"
    yield page
    ctx.close()


def shot(p, name):
    if OUT:
        d = OUT / p.tag
        d.mkdir(parents=True, exist_ok=True)
        p.wait_for_timeout(200)
        p.mouse.move(2, 2)
        p.screenshot(path=str(d / f"{name}.png"))


def rect(p, sel):
    return p.locator(sel).first.bounding_box()


def new_post(p, path):
    T(p, "new-tab").click()
    p.select_option("[data-testid=method]", "POST")
    p.fill("[data-testid=url]", p.echo + path)


def send(p):
    with p.expect_response(lambda r: r.url.endswith("/run_one")):
        T(p, "send").click()
    expect(T(p, "resp-status")).to_be_visible()


def assert_no_dead_space(p):
    """So'rov paneli va javob paneli orasida/ostida bo'sh "o'lik" joy yo'q: ikkalasi ham konteynerni to'liq to'ldiradi."""
    w, q, r = rect(p, "[data-testid=work]"), rect(p, ".req-pane"), rect(p, "[data-testid=response]")
    side = p.evaluate("document.documentElement.classList.contains('view-side')")
    if side:
        assert abs((q["width"] + r["width"] + 12) - w["width"]) <= 3, (q, r, w)
    else:
        assert abs((q["height"] + r["height"] + 12) - w["height"]) <= 3, (q, r, w)
    assert q["height"] > 100 and r["height"] > 100 or side


def test_01_post_60_line_json_400_then_reload_keeps_body_and_response(qa):
    new_post(qa, "/status/400")
    qa.click("[data-section=body]")
    qa.locator("[data-testid=body-raw]").click()
    qa.keyboard.insert_text(BODY60)
    qa.evaluate("document.querySelector('.body-editor .cm-scroller').scrollTop = 0")
    shot(qa, "01a-json-body-60-lines")
    send(qa)
    expect(T(qa, "resp-status")).to_have_text("400")
    expect(T(qa, "resp-body")).to_contain_text('"code"')
    shot(qa, "01b-after-send-400")
    qa.reload()
    qa.wait_for_selector("[data-testid=app]")
    qa.add_style_tag(content="*{caret-color:transparent!important;animation:none!important;transition:none!important}")
    qa.click("[data-section=body]")
    expect(qa.locator(".body-editor .cm-line").first).to_have_text("{")                          # birinchi qator ko'rinadi
    qa.evaluate("document.querySelector('.body-editor .cm-scroller').scrollTop = 1e6")
    expect(qa.locator(".body-editor")).to_contain_text("C-010")                                  # body to'liq: oxirgi elementgacha
    qa.evaluate("document.querySelector('.body-editor .cm-scroller').scrollTop = 0")
    expect(T(qa, "resp-status")).to_have_text("400")
    expect(T(qa, "resp-body")).to_contain_text('"code"')
    assert_no_dead_space(qa)
    shot(qa, "01c-after-reload")


def test_02_two_mb_json_response(qa):
    new_post(qa, "/bigjson?n=330000")
    qa.select_option("[data-testid=method]", "GET")
    send(qa)
    assert int(qa.evaluate("document.querySelector('[data-testid=resp-size]').textContent.match(/[\\d.]+/)[0] * 1") ) >= 1                  # MB/KB
    expect(T(qa, "resp-body")).to_be_visible()
    shot(qa, "02a-json-2mb")
    qa.reload()
    qa.wait_for_selector("[data-testid=app]")
    expect(T(qa, "resp-body")).to_contain_text("items")
    expect(T(qa, "resp-not-saved")).to_have_count(0)
    shot(qa, "02b-json-2mb-after-reload")


def test_03_image_response(qa):
    new_post(qa, "/png")
    qa.select_option("[data-testid=method]", "GET")
    send(qa)
    qa.wait_for_function("document.querySelector('[data-testid=resp-image]')?.naturalWidth > 0")
    shot(qa, "03-image")


def test_04_empty_204(qa):
    new_post(qa, "/nocontent")
    qa.select_option("[data-testid=method]", "GET")
    send(qa)
    expect(T(qa, "resp-empty-body")).to_be_visible()
    shot(qa, "04-empty-204")


def drag(p, dy=0, dx=0):
    b = rect(p, "[data-testid=resp-resizer]")
    x, y = (b["x"] + 4, b["y"] + b["height"] / 2 + 40) if dx else (b["x"] + 40, b["y"] + 6)
    if dx:
        x, y = b["x"] + 6, b["y"] + 60
    p.mouse.move(x, y)
    p.mouse.down()
    p.mouse.move(x + dx, y + dy, steps=6)
    p.mouse.up()


def prepare_json(p):
    new_post(p, "/status/400")
    p.click("[data-section=body]")
    p.locator("[data-testid=body-raw]").click()
    p.keyboard.insert_text(BODY60)
    p.evaluate("document.querySelector('.body-editor .cm-scroller').scrollTop = 0")
    send(p)


def test_05_resizer_stacked_grow_and_shrink_response(qa):
    prepare_json(qa)
    r0 = rect(qa, "[data-testid=response]")["height"]
    drag(qa, dy=-170)
    assert rect(qa, "[data-testid=response]")["height"] > r0 + 80
    assert_no_dead_space(qa)
    assert qa.locator(".body-editor").bounding_box()["height"] >= 100
    shot(qa, "05a-response-bigger")
    drag(qa, dy=330)
    assert rect(qa, "[data-testid=response]")["height"] < r0 - 60 or rect(qa, "[data-testid=response]")["height"] <= 140
    assert_no_dead_space(qa)
    shot(qa, "05b-response-smaller")


def test_06_side_by_side_and_resize(qa):
    prepare_json(qa)
    T(qa, "layout-toggle").click()
    assert_no_dead_space(qa)
    shot(qa, "06a-side-by-side")
    w0 = rect(qa, "[data-testid=response]")["width"]
    drag(qa, dx=-220)
    assert rect(qa, "[data-testid=response]")["width"] > w0 + 150
    assert_no_dead_space(qa)
    assert rect(qa, ".body-editor")["height"] > 150
    shot(qa, "06b-side-response-wider")
    drag(qa, dx=420)
    assert_no_dead_space(qa)
    shot(qa, "06c-side-response-narrower")
