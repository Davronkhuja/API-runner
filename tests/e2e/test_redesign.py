"""Yangi dizayn (docs/design): qobiq, tema, shriftlar, mikro-detallar, bo'sh holatlar, klaviatura va a11y."""
import re

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def world(app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Ijara"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base_url", "value": echo_server}]
    col["item"] = [
        {"id": "f1", "name": "Shartnomalar", "item": [
            {"id": "r1", "name": "Main", "request": {"method": "GET", "header": [], "url": {"raw": "{{base_url}}/echo?x=1", "query": [{"key": "x", "value": "1"}]}}, "response": []},
            {"id": "r2", "name": "Create", "request": {"method": "POST", "header": [], "url": {"raw": "{{base_url}}/echo"}}, "response": []}]},
        {"id": "r3", "name": "Missing", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/status/404"}}, "response": []},
    ]
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


def send(p):
    with p.expect_response(lambda r: r.url.endswith("/run_one")) as i:
        T(p, "send").click()
    return i.value.json()


# ── qobiq ──
def test_layout_regions_exist_in_order(ui):
    open_req(ui, "Main")
    boxes = {t: T(ui, t).bounding_box() for t in ("header", "rail", "sidebar", "tabbar", "request-editor", "statusbar")}
    assert all(boxes.values())
    assert boxes["header"]["y"] < boxes["rail"]["y"] and boxes["rail"]["x"] < boxes["sidebar"]["x"] < boxes["request-editor"]["x"]
    assert boxes["statusbar"]["y"] > boxes["request-editor"]["y"] and abs(boxes["header"]["height"] - 48) < 1 and abs(boxes["statusbar"]["height"] - 28) < 1
    assert abs(boxes["rail"]["width"] - 64) < 1
    for t in ("urlfield", "resp-resizer", "response", "sections"):
        pass
    expect(ui.locator(".urlfield")).to_be_visible()
    expect(T(ui, "resp-resizer")).to_be_visible()
    expect(T(ui, "response")).to_be_visible()


def test_header_controls(ui):
    for t in ("cmdk-open", "import-btn", "env-select", "env-vars-btn", "theme", "settings-btn"):
        expect(T(ui, t)).to_be_visible()
    T(ui, "settings-btn").click()
    expect(T(ui, "settings-tab")).to_be_visible()
    T(ui, "env-vars-btn").click()
    expect(T(ui, "env-quicklook")).to_be_visible()                             # faol muhit yo'q → popover (Globals)
    T(ui, "ql-open-all").click()
    expect(T(ui, "env-tab")).to_be_visible()


def test_statusbar_server_console_cookies_version(ui, app):
    expect(T(ui, "server-status")).to_contain_text("Server ulangan")
    expect(T(ui, "console-btn")).to_be_enabled()
    expect(T(ui, "version")).to_contain_text("v2.")
    T(ui, "cookies-btn").click()
    expect(T(ui, "cookies-tab")).to_be_visible()


def test_rail_switches_sidebar_panels(ui):
    expect(T(ui, "sb-collections")).to_have_attribute("aria-pressed", "true")
    for rail, title in (("sb-environments", "Muhitlar"), ("sb-history", "Tarix"), ("sb-runner", "Runner"), ("sb-collections", "Kolleksiyalar")):
        T(ui, rail).click()
        expect(T(ui, "sb-title")).to_have_text(title)
        expect(T(ui, rail)).to_have_attribute("aria-pressed", "true")
    T(ui, "sb-runner").click()
    T(ui, "open-runner").click()
    expect(T(ui, "runner-tab")).to_be_visible()


# ── tema va shriftlar ──
def test_theme_toggle_in_header_persists_and_switches_tokens(ui):
    html = ui.locator("html")
    light_panel = ui.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--panel').trim()")
    T(ui, "theme").click()
    expect(html).to_have_class(re.compile("th-dark"))
    expect(html).to_have_attribute("data-theme", "dark")
    assert ui.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--panel').trim()") != light_panel
    assert ui.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(14, 16, 21)"
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    expect(html).to_have_class(re.compile("th-dark"))                          # saqlangan
    T(ui, "theme").click()
    expect(html).to_have_class(re.compile("th-light"))
    assert ui.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(246, 247, 249)"


def test_theme_applied_before_first_paint_from_saved_choice(app, browser):
    ctx = browser.new_context()
    ctx.add_init_script("localStorage.setItem('apiRunnerTheme','dark')")
    p = ctx.new_page()
    p.goto(app.url)
    expect(p.locator("html")).to_have_class(re.compile("th-dark"))
    ctx.close()


def test_fonts_are_local_inter_and_jetbrains_mono_no_external_requests(app, browser, world):
    ctx = browser.new_context()
    p = ctx.new_page()
    hosts = set()
    p.on("request", lambda r: hosts.add(re.sub(r"^https?://([^/]+).*", r"\1", r.url)))
    p.goto(app.url)
    p.wait_for_selector("[data-testid=app]")
    open_req(p, "Main")
    p.evaluate("document.fonts.ready")
    assert p.evaluate("document.fonts.check('13px \"Inter Variable\"') && document.fonts.check('13px \"JetBrains Mono Variable\"')")
    assert "Inter" in p.evaluate("getComputedStyle(document.body).fontFamily")
    assert "JetBrains Mono" in p.evaluate("getComputedStyle(document.querySelector('[data-testid=url]')).fontFamily")
    loaded = p.evaluate("[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)")
    assert any("Inter" in f for f in loaded) and any("JetBrains" in f for f in loaded)
    assert hosts <= {app.url.split("//")[1]}, hosts                            # CDN'ga hech qanday so'rov yo'q
    ctx.close()


# ── mikro-detallar ──
def test_active_tab_top_line_and_dirty_dot_and_method_label(ui):
    open_req(ui, "Main")
    open_req(ui, "Create")
    tab = ui.locator("[data-testid=tab].active")
    assert ui.evaluate("(el) => getComputedStyle(el, '::after').height", tab.element_handle()) == "2px"
    expect(tab.locator(".m")).to_have_text("POST")
    expect(T(ui, "dirty-dot")).to_have_count(0)
    ui.fill("[data-testid=url]", "{{base_url}}/echo?changed=1")
    expect(T(ui, "dirty-dot")).to_have_count(1)
    expect(T(ui, "dirty-dot")).to_have_attribute("aria-label", re.compile("Saqlanmagan"))


def test_url_variable_chip_colors_and_hover_tooltip(ui):
    open_req(ui, "Main")
    chip = ui.locator(".urlfield [data-testid=var-chip]", has_text="base_url")
    expect(chip).to_have_class(re.compile("var-ok"))
    chip.hover()
    expect(T(ui, "chip-tip")).to_contain_text("Collection: http://127.0.0.1")
    ui.mouse.move(5, 5)
    expect(T(ui, "chip-tip")).to_have_count(0)
    ui.fill("[data-testid=url]", "{{nope}}/x?a={{nope2}}")
    bad = ui.locator(".urlfield [data-testid=var-chip]")
    expect(bad).to_have_count(2)
    expect(bad.first).to_have_class(re.compile("var-undef"))
    colors = ui.evaluate("[...document.querySelectorAll('.urlfield [data-testid=var-chip]')].map(e => getComputedStyle(e).backgroundColor)")
    assert colors[0] == colors[1] != "rgba(0, 0, 0, 0)"


def test_long_url_scrolls_inside_the_editor_and_chip_stays_on_its_text(ui):
    T(ui, "new-tab").click()
    ui.fill("[data-testid=url]", "https://example.com/" + "a" * 200 + "/{{who}}")
    ui.evaluate("document.querySelector('.urlfield .cm-scroller').scrollLeft = 99999")
    chip = ui.locator(".urlfield [data-testid=var-chip]")
    box, field = chip.bounding_box(), ui.locator(".urlfield").bounding_box()
    assert chip.inner_text() == "{{who}}" and field["x"] < box["x"] < field["x"] + field["width"]       # chip matn bilan birga siljigan va ko'rinadi


def test_status_pill_ok_and_err_and_timing_tooltip(ui):
    open_req(ui, "Main")
    send(ui)
    pill = ui.locator(".resp-meta .status-pill")
    expect(pill).to_have_class(re.compile(r"\bok\b"))
    expect(pill).to_contain_text("OK")
    expect(T(ui, "resp-status")).to_have_text("200")
    expect(ui.locator(".tipwrap .tip")).to_be_hidden()
    T(ui, "resp-timing").hover()
    expect(ui.locator(".tipwrap .tip")).to_be_visible()
    expect(ui.locator(".tipwrap .tip")).to_contain_text("TTFB")
    open_req(ui, "Missing")
    send(ui)
    pill = ui.locator(".resp-meta .status-pill")
    expect(pill).to_have_class(re.compile(r"\berr\b"))
    expect(pill).to_contain_text("Not Found")


def test_empty_states_response_and_no_tabs(ui):
    open_req(ui, "Main")
    expect(T(ui, "resp-empty")).to_contain_text("Javob shu yerda chiqadi")
    expect(T(ui, "resp-empty")).to_contain_text("Yuborish")
    ui.keyboard.press("Control+w")
    expect(T(ui, "no-tabs")).to_contain_text("Nimadan boshlaymiz?")


def test_request_section_badges_and_breadcrumbs(ui):
    open_req(ui, "Main")
    expect(T(ui, "crumbs")).to_contain_text("Ijara")
    expect(T(ui, "crumbs")).to_contain_text("Shartnomalar")
    expect(T(ui, "crumbs")).to_contain_text("Main")
    expect(ui.locator("[data-section=params] .badge")).to_have_text("1")


def test_resizer_by_mouse_and_keyboard(ui):
    open_req(ui, "Main")
    h0 = T(ui, "response").bounding_box()["height"]
    T(ui, "resp-resizer").focus()
    ui.keyboard.press("ArrowUp")
    ui.keyboard.press("ArrowUp")
    assert T(ui, "response").bounding_box()["height"] > h0 + 30


# ── bosh sahifa ──
def close_active(p):
    """Ctrl+W; saqlanmagan bo'lsa dialogda "Saqlamaslik"."""
    p.keyboard.press("Control+w")
    p.wait_for_timeout(150)
    if T(p, "dlg-discard").count():
        T(p, "dlg-discard").click()


def test_welcome_cards_recent_shortcuts_and_drop_import(ui, app, tmp_path):
    for m in ("GET", "POST"):
        app.api("POST", "/api/history", {"kind": "request", "payload": {"method": m, "url": "http://x.test/" + m.lower(), "headers": [], "params": []}})
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    expect(T(ui, "no-tabs")).to_be_visible()
    expect(T(ui, "wl-recent-row")).to_have_count(2)
    T(ui, "wl-recent-row").first.click()
    expect(T(ui, "request-editor")).to_be_visible()
    close_active(ui)
    expect(T(ui, "no-tabs")).to_be_visible()
    T(ui, "wl-new").click()
    expect(T(ui, "request-editor")).to_be_visible()
    close_active(ui)
    T(ui, "wl-runner").click()
    expect(T(ui, "runner-tab")).to_be_visible()
    close_active(ui)
    f = tmp_path / "c.json"
    f.write_text('{"info":{"name":"Imp","schema":"https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},"item":[{"name":"q","request":{"method":"GET","url":"http://a.b/c"}}]}')
    T(ui, "wl-file").set_input_files(str(f))
    T(ui, "sb-collections").click()
    expect(ui.locator("[data-name='Imp']")).to_be_visible()


def test_welcome_curl_paste_fills_new_tab(ui):
    ui.evaluate("""() => { const dt = new DataTransfer(); dt.setData('text', "curl -X PUT 'https://a.io/x' -H 'X-A: b'");
      document.body.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""")
    expect(T(ui, "url")).to_have_text("https://a.io/x")
    expect(T(ui, "method")).to_have_value("PUT")


# ── ⌘K ──
def test_cmdk_opens_filters_navigates_and_closes(ui):
    ui.keyboard.press("Control+k")
    expect(T(ui, "cmdk")).to_be_visible()
    expect(T(ui, "cmdk-input")).to_be_focused()
    ui.keyboard.type("creat")
    expect(T(ui, "cmdk-row")).to_have_count(1)
    expect(T(ui, "cmdk-row")).to_contain_text("Create")
    ui.keyboard.press("Enter")
    expect(T(ui, "cmdk")).to_have_count(0)
    expect(T(ui, "method")).to_have_value("POST")
    T(ui, "cmdk-open").click()
    ui.keyboard.type("zzzz")
    expect(T(ui, "cmdk-empty")).to_be_visible()
    ui.keyboard.press("Escape")
    expect(T(ui, "cmdk")).to_have_count(0)
    T(ui, "cmdk-open").click()
    ui.keyboard.press("ArrowDown")
    ui.keyboard.press("ArrowDown")
    expect(T(ui, "cmdk-row").nth(2)).to_have_class(re.compile("sel"))


def test_cmdk_actions_theme_and_environment(ui, app):
    app.api("POST", "/api/environments", {"name": "Prod muhit"})
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.keyboard.press("Control+k")
    ui.keyboard.type("temani")
    ui.keyboard.press("Enter")
    expect(ui.locator("html")).to_have_class(re.compile("th-dark"))
    ui.keyboard.press("Control+k")
    ui.keyboard.type("prod")
    ui.keyboard.press("Enter")
    expect(T(ui, "env-tab")).to_be_visible()


# ── klaviatura ──
def test_tree_keyboard_navigation_and_open(ui):
    row = ui.locator("[data-name='Main']")
    row.focus()
    ui.keyboard.press("ArrowDown")
    expect(ui.locator("[data-name='Create']")).to_be_focused()
    ui.keyboard.press("Enter")
    expect(T(ui, "request-editor")).to_be_visible()
    ui.locator("[data-name='Shartnomalar']").focus()
    ui.keyboard.press("ArrowLeft")
    expect(ui.locator("[data-name='Main']")).to_have_count(0)                  # papka yopildi
    ui.keyboard.press("ArrowRight")
    expect(ui.locator("[data-name='Main']")).to_have_count(1)


def test_tabs_and_sections_arrow_keys(ui):
    open_req(ui, "Main")
    open_req(ui, "Create")
    ui.locator("[data-testid=tab].active [role=tab]").focus()
    ui.keyboard.press("ArrowLeft")
    expect(ui.locator("[data-testid=tab].active")).to_contain_text("Main")
    ui.locator("[data-section=params]").focus()
    ui.keyboard.press("ArrowRight")
    expect(ui.locator("[data-section=headers]")).to_have_attribute("aria-selected", "true")


def test_global_focus_ring_is_visible(ui):
    open_req(ui, "Main")
    ui.keyboard.press("Tab")
    outline = ui.evaluate("(() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle + '|' + s.outlineWidth })()")
    assert outline.startswith("solid|") or document_has_box_shadow(ui)


def document_has_box_shadow(p):
    return p.evaluate("getComputedStyle(document.activeElement.closest('.urlfield') || document.activeElement).boxShadow !== 'none'")


# ── a11y ──
A11Y_JS = """() => {
  const name = el => (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.title || el.innerText || el.textContent || '').trim()
  const vis = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden' }
  const bad = []
  document.querySelectorAll('button, [role=button], a[href]').forEach(el => { if (vis(el) && !name(el)) bad.push('button:' + (el.dataset.testid || el.className)) })
  document.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(el => {
    if (!vis(el)) return
    const lab = el.labels && el.labels.length
    if (!lab && !name(el) && !el.placeholder) bad.push('field:' + (el.dataset.testid || el.className || el.type))
  })
  document.querySelectorAll('svg').forEach(el => { if (!el.closest('button, a') && el.getAttribute('aria-hidden') !== 'true' && !el.getAttribute('aria-label')) bad.push('svg') })
  return bad
}"""


@pytest.mark.parametrize("screen", ["welcome", "editor", "runner", "settings", "env", "cookies", "history-panel", "collection"])
def test_every_control_has_an_accessible_name(ui, screen):
    if screen == "editor":
        open_req(ui, "Main")
        send(ui)
    elif screen == "runner":
        ui.locator("[data-name='Ijara']").click(button="right")
        ui.click("[data-act=runner]")
        T(ui, "runner-run").click()
        expect(T(ui, "runner-result").first).to_be_visible()
    elif screen == "settings":
        T(ui, "settings-btn").click()
    elif screen == "env":
        T(ui, "env-vars-btn").click()
        T(ui, "ql-open-all").click()
    elif screen == "cookies":
        T(ui, "cookies-btn").click()
    elif screen == "history-panel":
        T(ui, "sb-history").click()
    elif screen == "collection":
        ui.locator("[data-name='Ijara']").dblclick()
    assert ui.evaluate(A11Y_JS) == []


def test_dialogs_have_roles(ui):
    open_req(ui, "Main")
    T(ui, "curl-btn").click()
    expect(ui.locator("[role=dialog][aria-modal=true]")).to_have_count(1)
    ui.keyboard.press("Escape")
    ui.keyboard.press("Control+k")
    expect(ui.locator("[role=dialog][aria-modal=true]")).to_have_count(1)


# ── Runner ──
CSV = "contract_id,pinfl\n1,3050\n2,3051\n3,3052\n"


def runner(ui):
    ui.locator("[data-name='Ijara']").click(button="right")
    ui.click("[data-act=runner]")
    expect(T(ui, "runner-tab")).to_be_visible()
    for cb in ui.locator("[data-testid=runner-item] input[type=checkbox]").all():       # sukut: faqat GET belgilangan — bu testlarga hammasi kerak
        cb.check()


def test_runner_layout_iterations_stats_progress_and_filters(ui, tmp_path):
    runner(ui)
    expect(T(ui, "runner-selcount")).to_contain_text("3 / 3")
    f = tmp_path / "d.csv"
    f.write_text(CSV)
    T(ui, "runner-file").set_input_files(str(f))
    expect(T(ui, "runner-data-info")).to_contain_text("d.csv: 3 qator")
    expect(T(ui, "runner-run")).to_contain_text("9 so'rov")                    # 3 iteratsiya × 3 so'rov
    ui.locator("[data-testid=runner-item] input[type=checkbox]").nth(1).uncheck()
    expect(T(ui, "runner-run")).to_contain_text("6 so'rov")
    T(ui, "runner-run").click()
    expect(T(ui, "runner-s-done")).to_contain_text("6 / 6")
    expect(T(ui, "runner-row")).to_have_count(6)
    expect(T(ui, "runner-s-ok")).to_have_text("3")                              # /status/404 har iteratsiyada xato
    expect(T(ui, "runner-s-fail")).to_have_text("3")
    expect(ui.locator("[role=progressbar]")).to_have_attribute("aria-valuenow", "100")
    ui.click("[data-filter=err]")
    expect(T(ui, "runner-row")).to_have_count(3)
    ui.click("[data-filter=ok]")
    expect(T(ui, "runner-row")).to_have_count(3)
    ui.click("[data-filter=all]")
    expect(T(ui, "runner-row")).to_have_count(6)


def test_runner_stop_on_first_error_and_manual_stop_and_delay(ui):
    runner(ui)
    T(ui, "runner-iterations").fill("4")
    T(ui, "runner-stop-on-error").check()
    T(ui, "runner-run").click()
    expect(T(ui, "runner-run")).to_be_enabled()
    expect(T(ui, "runner-row")).to_have_count(3)                                # Main, Create(echo 200), Missing(404) → shu yerda to'xtadi
    T(ui, "runner-stop-on-error").uncheck()
    T(ui, "runner-delay").fill("400")
    T(ui, "runner-run").click()
    expect(T(ui, "runner-stop")).to_be_visible()
    T(ui, "runner-stop").click()
    expect(T(ui, "runner-run")).to_be_visible()
    assert T(ui, "runner-row").count() < 12                                     # to'liq 4×3 bajarilmadi


def test_runner_data_file_clear_and_preview(ui, tmp_path):
    runner(ui)
    f = tmp_path / "d.csv"
    f.write_text(CSV)
    T(ui, "runner-file").set_input_files(str(f))
    expect(T(ui, "data-preview")).to_contain_text("3050")
    T(ui, "runner-data-clear").click()
    expect(T(ui, "runner-dropzone")).to_be_visible()


# ── Import / Runner: ⌘K palitrasida (⌘⇧O/⌘⇧R brauzer yorliqlari bilan to'qnashgani uchun olib tashlangan) ──
def test_import_and_runner_are_cmdk_commands(ui):
    ui.keyboard.press("Control+k")
    ui.keyboard.type("import")
    expect(T(ui, "cmdk-row")).to_contain_text("Import")
    ui.keyboard.press("Enter")
    expect(T(ui, "import-dialog")).to_be_visible()                                 # Import endi dialog ochadi
    ui.keyboard.press("Escape")
    ui.keyboard.press("Control+k")
    ui.keyboard.type("runner")
    ui.keyboard.press("Enter")
    expect(T(ui, "runner-tab")).to_be_visible()


def test_shift_shortcuts_are_gone_and_welcome_points_to_cmdk(ui):
    ui.keyboard.press("Control+Shift+R")
    ui.keyboard.press("Control+Shift+O")
    expect(T(ui, "runner-tab")).to_have_count(0)
    expect(T(ui, "no-tabs")).to_be_visible()
    expect(T(ui, "no-tabs")).not_to_contain_text("⇧")
    expect(T(ui, "wl-import")).to_contain_text("⌘K")
    expect(T(ui, "wl-runner")).to_contain_text("⌘K")
