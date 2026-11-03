"""URL maydoni — bir qatorli CodeMirror: belgilash ko'rinadi (yorug'/qorong'i), undo/redo, scroll, chiplar, paste."""
import re

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
SEL = "document.querySelector('.urlfield .cm-content')"


@pytest.fixture
def ui(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    T(page, "new-tab").click()
    return page


def sel_bg(p):
    """Belgilangan matn foni: ::selection computed style (pseudo-element)."""
    return p.evaluate(f"getComputedStyle({SEL}.querySelector('.cm-line'), '::selection').backgroundColor")


def token(p, name):
    return p.evaluate(f"getComputedStyle(document.documentElement).getPropertyValue('--{name}').trim()")


def rgb(hexcolor):
    h = hexcolor.lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def test_selection_has_a_visible_background_in_light_and_dark(ui):
    T(ui, "url").fill("https://example.com/path/{{id}}?a=1")
    T(ui, "url").press("ControlOrMeta+a")
    assert ui.evaluate("getSelection().toString()") == "https://example.com/path/{{id}}?a=1"
    light = sel_bg(ui)
    assert light == rgb(token(ui, "sel")) and light != "rgba(0, 0, 0, 0)"
    assert light != ui.evaluate("getComputedStyle(document.querySelector('.urlfield')).backgroundColor")        # maydon foni bilan bir xil emas
    T(ui, "theme").click()
    expect(ui.locator("html")).to_have_class(re.compile("th-dark"))
    dark = sel_bg(ui)
    assert dark == rgb(token(ui, "sel")) and dark != light
    shot = ui.locator(".urlbar").screenshot()
    assert len(shot) > 1000


def test_partial_selection_by_keyboard_and_text_stays_readable(ui):
    T(ui, "url").fill("http://h/abc")
    T(ui, "url").press("End")
    for _ in range(3):
        T(ui, "url").press("Shift+ArrowLeft")
    assert ui.evaluate("getSelection().toString()") == "abc"
    color = ui.evaluate(f"getComputedStyle({SEL}).color")
    assert color != "rgba(0, 0, 0, 0)"                                                       # matn shaffof emas (eski xato)
    T(ui, "url").press("Delete")
    expect(T(ui, "url")).to_have_text("http://h/")


def test_undo_redo(ui):
    T(ui, "url").click()
    ui.keyboard.type("http://one")
    ui.keyboard.press("ControlOrMeta+z")
    expect(ui.locator(".urlfield .cm-placeholder")).to_be_visible()                          # bo'sh — placeholder ko'rinadi
    ui.keyboard.press("ControlOrMeta+Shift+z")
    expect(T(ui, "url")).to_have_text("http://one")


def test_chips_colour_defined_and_undefined_and_tooltip_shows_scope_and_value(ui):
    T(ui, "url").fill("{{nope}}/x?a={{$guid}}")
    chips = ui.locator(".urlfield [data-testid=var-chip]")
    expect(chips).to_have_count(2)
    expect(chips.nth(0)).to_have_class(re.compile("var-undef"))
    expect(chips.nth(1)).to_have_class(re.compile("var-ok"))
    chips.nth(0).hover()
    expect(T(ui, "chip-tip")).to_contain_text("aniqlanmagan")
    ui.mouse.move(5, 5)
    expect(T(ui, "chip-tip")).to_have_count(0)


def test_multiline_paste_is_flattened_and_url_stays_one_line(ui):
    T(ui, "url").click()
    ui.evaluate(f"""() => {{ const i = {SEL}; i.focus();
      const dt = new DataTransfer(); dt.setData('text', "http://h/a\\nb?x=1\\n");
      i.dispatchEvent(new ClipboardEvent('paste', {{clipboardData: dt, bubbles: true, cancelable: true}})); }}""")
    expect(T(ui, "url")).to_have_text("http://h/ab?x=1")
    assert ui.locator(".urlfield .cm-line").count() == 1


def test_enter_sends_and_ctrl_enter_does_not_insert_newline(ui, echo_server):
    T(ui, "url").fill(echo_server + "/echo?k=1")
    T(ui, "url").press("Enter")
    expect(T(ui, "resp-status")).to_have_text("200")
    T(ui, "url").press("ControlOrMeta+Enter")
    assert ui.locator(".urlfield .cm-line").count() == 1


def test_caret_is_visible_and_field_keeps_focus_ring(ui):
    T(ui, "url").click()
    assert ui.evaluate(f"getComputedStyle({SEL}).caretColor") != "rgba(0, 0, 0, 0)"
    expect(ui.locator(".urlfield")).to_have_css("border-top-color", rgb(token(ui, "focus")))
