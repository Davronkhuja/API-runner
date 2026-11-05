"""Himoya: layout testlari — dialoglar viewport'dan oshmaydi, matn kesilmaydi, interaktiv elementlar ≥24px, muharrirlar panelni to'ldiradi, axe (serious/critical = 0)."""
import sys
from pathlib import Path

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import ui_audit  # noqa: E402

from conftest import E2E_TOKEN  # noqa: E402

DETECT = (ROOT / "tools" / "ui_detect.js").read_text(encoding="utf-8")
AXE = ROOT / "web" / "node_modules" / "axe-core" / "axe.min.js"
T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
ui_audit.TOKEN = E2E_TOKEN


@pytest.fixture
def world(app, echo_server):
    ui_audit.seed(app.url, echo_server, app.flask)
    return app, echo_server


@pytest.fixture(params=[(1280, 720, "light"), (1440, 900, "dark")], ids=lambda p: f"{p[0]}x{p[1]}-{p[2]}")
def page(request, world, browser):
    app, echo = world
    w, h, theme = request.param
    ctx = browser.new_context(viewport={"width": w, "height": h}, locale="uz")
    ctx.add_init_script(f"try {{ localStorage.setItem('apiRunnerTheme', '{theme}') }} catch (e) {{}}")
    p = ctx.new_page()
    p.goto(app.url)
    p.wait_for_selector("[data-testid=app]")
    p.add_style_tag(content="*{caret-color:transparent!important;animation:none!important;transition:none!important}")
    p.echo, p.app = echo, app
    yield p
    ctx.close()


SCENES = ["welcome", "editor-empty", "editor-simple-response", "heavy-params", "heavy-headers", "heavy-auth", "heavy-body", "heavy-scripts", "heavy-settings", "heavy-batch",
          "body-graphql", "body-formdata", "resp-400", "resp-headers-tab", "resp-cookies-tab", "resp-tests-tab", "dlg-code-long", "dlg-saveas", "dlg-move", "dlg-confirm",
          "env-tab", "env-eye", "folder-overview-80", "history-drawer", "sidebar-history", "settings", "runner", "runner-results", "runner-compare", "runner-export-menu", "cookies", "console", "cmdk", "tabs-30", "long-name-request",
          "layout-side", "layout-dense", "dlg-import", "dlg-nameclean"]


def go(page, name):
    scenes = ui_audit.scenes(page.app.url, page.echo)
    scenes.update(EXTRA(page))
    scenes[name](page)
    page.wait_for_timeout(200)


def EXTRA(page):
    def imp(p):
        p.click("[data-testid=import-btn]"); p.wait_for_selector("[data-testid=import-dialog]")
    def clean(p):
        p.wait_for_selector("[data-testid=nameclean-offer]"); p.click("[data-testid=nameclean-open]"); p.wait_for_selector("[data-testid=nameclean-dialog]")
    return {"dlg-import": imp, "dlg-nameclean": clean}


@pytest.mark.parametrize("name", ["dlg-code-long", "dlg-saveas", "dlg-move", "dlg-confirm", "dlg-import", "dlg-nameclean", "dlg-runguard", "runner-compare"])
def test_dialogs_never_exceed_the_viewport_and_keep_header_and_footer_visible(page, name):
    go(page, name)
    vw, vh = page.viewport_size["width"], page.viewport_size["height"]
    dlg = page.locator(".dialog.dlg").first
    expect(dlg).to_be_visible()
    r = dlg.bounding_box()
    assert r["x"] >= -1 and r["y"] >= -1 and r["x"] + r["width"] <= vw + 1 and r["y"] + r["height"] <= vh + 1, (name, r, vw, vh)
    for part in (".dlg-head", ".dlg-foot"):
        if dlg.locator(part).count():
            b = dlg.locator(part).bounding_box()
            assert 0 <= b["y"] and b["y"] + b["height"] <= vh + 1, (name, part, b)


def test_dialog_esc_closes_backdrop_closes_and_focus_returns_to_trigger(page):
    page.focus("[data-testid=import-btn]")
    page.click("[data-testid=import-btn]")
    expect(T(page, "import-dialog")).to_be_visible()
    assert page.evaluate("!!document.activeElement.closest('[data-testid=import-dialog]')")          # fokus dialog ichiga o'tdi
    for _ in range(12):
        page.keyboard.press("Tab")
    assert page.evaluate("!!document.activeElement.closest('[data-testid=import-dialog]')")          # fokus tuzog'i: tashqariga chiqmaydi
    page.keyboard.press("Escape")
    expect(T(page, "import-dialog")).to_have_count(0)
    assert page.evaluate("document.activeElement.getAttribute('data-testid')") == "import-btn"        # trigger'ga qaytdi
    page.click("[data-testid=import-btn]")
    page.mouse.click(5, 5)
    expect(T(page, "import-dialog")).to_have_count(0)


@pytest.mark.parametrize("name", [n for n in SCENES if n not in ("tabs-30",)])
def test_no_page_hscroll_no_overlay_outside_viewport_no_clipped_text_no_tiny_targets(page, name):
    go(page, name)
    found = page.evaluate(DETECT)
    bad = [f for f in found if f["kind"] in ("page-hscroll", "overlay-outside-viewport", "clipped-text", "small-target", "editor-dead-space", "editor-too-short")]
    assert not bad, (name, bad)


def test_tab_overflow_scrolls_and_active_tab_stays_visible(page):
    go(page, "tabs-30")
    box = page.locator(".tabs-scroll").bounding_box()
    act = page.locator("[data-testid=tab-body][aria-selected=true]").bounding_box()
    assert act["x"] >= box["x"] - 1 and act["x"] + act["width"] <= box["x"] + box["width"] + 1
    page.keyboard.press("Control+Home") if False else None
    T(page, "all-tabs").click()
    page.locator("[data-testid=all-tabs-list] button").first.click()
    page.wait_for_timeout(300)
    act = page.locator("[data-testid=tab-body][aria-selected=true]").bounding_box()
    box = page.locator(".tabs-scroll").bounding_box()
    assert act["x"] >= box["x"] - 1 and act["x"] + act["width"] <= box["x"] + box["width"] + 1


@pytest.mark.parametrize("name", ["welcome", "editor-simple-response", "heavy-headers", "heavy-body", "heavy-scripts", "resp-400", "dlg-code-long", "dlg-saveas", "dlg-import", "env-tab", "folder-overview-80", "settings", "runner", "history-drawer", "console", "cmdk", "layout-side"])
def test_axe_has_no_serious_or_critical_violations(page, name):
    go(page, name)
    page.add_script_tag(path=str(AXE))
    res = page.evaluate("() => axe.run({ exclude: [['.tabs-scroll']] }, { resultTypes: ['violations'] }).then(r => r.violations.filter(v => ['serious','critical'].includes(v.impact)).map(v => v.id + ' ×' + v.nodes.length + ' ' + v.nodes[0].target.join(' ')))")
    assert res == [], (name, res)


def test_sidebar_title_and_banner_do_not_squeeze_each_other(page):
    page.wait_for_selector("[data-testid=nameclean-offer]")                                          # seed'da URL nomli so'rov bor
    sb = page.locator("[data-testid=sidebar]").bounding_box()
    title = page.locator(".sb-title").bounding_box()
    banner = T(page, "nameclean-offer").bounding_box()
    assert title["height"] <= 56, title                                                              # sarlavha qatori bannerdan siqilib o'smaydi
    assert banner["y"] >= title["y"] + title["height"] - 1, (title, banner)                           # banner sarlavha ostida
    assert banner["width"] >= sb["width"] - 24, (sb, banner)                                          # to'liq kenglikda
    for t in ("sb-new-request", "new-collection"):
        b = T(page, t).bounding_box()
        assert b["width"] >= 24 and b["x"] + b["width"] <= sb["x"] + sb["width"] + 1                  # sarlavha tugmalari ko'rinadi va kichraymagan
    expect(T(page, "sb-title")).to_be_visible()
    T(page, "nameclean-close").click()
    expect(T(page, "nameclean-offer")).to_have_count(0)
    page.reload()
    page.wait_for_selector("[data-testid=app]")
    page.wait_for_timeout(300)
    expect(T(page, "nameclean-offer")).to_have_count(0)                                              # yopilgach qayta chiqmaydi (workspace'da saqlangan)
    assert page.app.api("GET", "/api/workspace")["meta"].get("nameclean_dismissed") is True


@pytest.mark.parametrize("name", ["dlg-code-long", "dlg-saveas", "dlg-move", "dlg-confirm", "dlg-import", "dlg-nameclean", "dlg-runguard"])
def test_dialog_body_leaves_no_big_empty_space_below_its_content(page, name):
    go(page, name)
    gap = page.evaluate("""() => {
      const b = document.querySelector('.dialog.dlg .dlg-body'); const bb = b.getBoundingClientRect()
      const last = [...b.children].filter(e => e.getBoundingClientRect().height > 0).pop()
      return Math.round(bb.bottom - parseFloat(getComputedStyle(b).paddingBottom) - last.getBoundingClientRect().bottom) }""")
    assert gap <= 24, (name, gap)


def test_code_dialog_height_follows_the_content(page):
    page.click("[data-testid=new-tab]")
    page.fill("[data-testid=url]", "http://h/x")
    page.keyboard.press("Escape")
    T(page, "curl-btn").click()
    short = page.locator(".dialog.dlg").bounding_box()["height"]
    page.keyboard.press("Escape")
    page.click("[data-section=headers]")
    for i in range(30):
        page.locator("[data-testid=headers-table] [data-cell='%d:0']" % i).fill(f"X-H{i}")
    T(page, "curl-btn").click()
    tall = page.locator(".dialog.dlg").bounding_box()
    assert short < 330 and tall["height"] > short + 200                                              # qisqa kodda katta oq maydon yo'q, uzunida o'sadi
    assert tall["height"] <= page.viewport_size["height"] - 60
