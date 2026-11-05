"""Har ekran uchun skrinshot (light va dark) → docs/screenshots/<faza>/<tema>/<ekran>.png (faqat SHOT_UPDATE=1 bilan; aks holda tmp).

Faza `SHOT_PHASE` (sukut "after"); "before" — eski UI uchun bir martalik suratga olish.
Ekranlar faqat barqaror `data-testid`lar bilan boshqariladi, shuning uchun bir xil skript ikkala UI'da ishlaydi.
"""
import os
import re
import struct
import zlib
from pathlib import Path

import pytest
from playwright.sync_api import expect

from conftest import set_body_mode

ROOT = Path(__file__).resolve().parents[2]
PHASE = os.environ.get("SHOT_PHASE", "after")
# Sukut bo'yicha vaqtinchalik papkaga (repo o'zgarmaydi); docs/screenshots/<faza> ni yangilash: SHOT_UPDATE=1
import tempfile  # noqa: E402
OUT = (ROOT / "docs" / "screenshots" / PHASE) if os.environ.get("SHOT_UPDATE") else Path(tempfile.mkdtemp(prefix="shots_")) / PHASE
T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


def png_unique_colors(path):
    """PNG'ni (stdlib bilan) o'qib, takrorlanmas piksellar sonini taxminan qaytaradi — bo'sh/bir rangli sahifani aniqlash uchun."""
    data = Path(path).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, w, h, depth, ctype = 8, b"", 0, 0, 0, 0
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", chunk[:10])
        elif kind == b"IDAT":
            idat += chunk
        pos += 12 + n
    raw = zlib.decompress(idat)
    return w, h, len(set(raw[i:i + 64] for i in range(0, min(len(raw), 400000), 64)))


@pytest.fixture
def world(app, echo_server):
    """Design maketiga o'xshash ma'lumotlar: collection (o'zgaruvchi + meros auth), 2 papka, env, tarix."""
    cid = app.api("POST", "/api/collections", {"name": "Ijara"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base_url", "value": echo_server}, {"key": "token", "value": "eyJhbGciOiJIUzI1NiJ9", "type": "secret"}]
    col["auth"] = {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}]}

    def req(i, name, method, path, body=None, query=None):
        r = {"method": method, "header": [{"key": "Accept", "value": "application/json"}], "url": {"raw": "{{base_url}}" + path, "query": query or []}}
        if body:
            r["body"] = {"mode": "raw", "raw": body, "options": {"raw": {"language": "json"}}}
        return {"id": i, "name": name, "request": r, "response": []}
    col["item"] = [
        {"id": "f1", "name": "Shartnomalar", "item": [
            req("r1", "v2/mobile/contracts/main", "GET", "/echo", query=[{"key": "page", "value": "1", "description": "Sahifa raqami"}, {"key": "size", "value": "20"}, {"key": "status", "value": "active", "disabled": True}]),
            req("r2", "v4/uzasbo", "POST", "/echo", body='{\n  "contract_id": "{{contract_id}}",\n  "amount": 1250000,\n  "paid": true,\n  "note": null\n}'),
            req("r3", "v1/contracts/:id", "DELETE", "/echo/:id")]},
        {"id": "f2", "name": "Hisob-kitoblar", "item": [req("r4", "v1/payments/list", "GET", "/echo"), req("r5", "v1/payments", "PUT", "/echo")]},
        req("r6", "health", "GET", "/text"),
    ]
    app.api("PUT", f"/api/collections/{cid}", col)
    for name, vals in (("Ijara — dev", [("contract_id", "C-1042")]), ("Ijara — prod", [("contract_id", "C-9")])):
        eid = app.api("POST", "/api/environments", {"name": name})["id"]
        env = app.api("GET", f"/api/environments/{eid}")
        env["values"] = [{"key": k, "value": v, "enabled": True, "type": "default"} for k, v in vals]
        app.api("PUT", f"/api/environments/{eid}", env)
        if "dev" in name:
            app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    for m, u in (("GET", "/echo?page=1"), ("POST", "/echo"), ("GET", "/text")):
        app.api("POST", "/api/history", {"kind": "request", "payload": {"method": m, "url": echo_server + u, "headers": [], "params": []}})
    return cid


def seed_rich(app, echo_server):
    """Yangi ekranlar uchun: javob matnli tarix (diff), env turlari/joriy qiymat."""
    import time
    db = app.flask.extensions["db"]
    now = time.time()
    hdr = {"Date": "x", "Content-Type": "application/json"}
    for i, (st, body) in enumerate([(200, '{"success": true, "data": {"regions": [{"id": 1, "name": "Toshkent sh."}, {"id": 3, "name": "Samarqand"}], "version": "2.4"}}'),
                                   (200, '{"success": true, "data": {"regions": [{"id": 1, "name": "Toshkent sh."}, {"id": 3, "name": "Samarqand vil."}, {"id": 4, "name": "Buxoro vil."}], "payment_methods": ["click", "payme"], "version": "2.4"}}')]):
        db.add_history("request", {"method": "GET", "url": "https://api.online-ijara.uz/api/v2/mobile/lists", "headers": [], "params": [], "status": st, "time": 0.241 - i * 0.04, "size": 3100 + i * 200, "resp_headers": hdr, "body": body}, ts=now - 7200 + i * 3600)
    db.add_history("request", {"method": "POST", "url": "https://api.online-mahalla.uz/api/v1/document/certified_seedlings_survey", "headers": [], "params": [], "status": 200, "time": 0.4, "size": 90, "resp_headers": hdr, "body": "{}"}, ts=now - 600)
    db.add_history("request", {"method": "GET", "url": "https://api.online-mahalla.uz/api/v1/gcp/pinfl", "headers": [], "params": [], "status": 404, "time": 0.1, "size": 20, "resp_headers": hdr, "body": "{}"}, ts=now - 500)
    db.add_history("request", {"method": "POST", "url": "https://api.online-ijara.uz/api/v1/mobile/basic_tool", "headers": [], "params": [], "status": 500, "time": 1.2, "size": 40, "resp_headers": hdr, "body": "{}"}, ts=now - 400)
    for e in app.api("GET", "/api/workspace")["environments"]:
        env = app.api("GET", f"/api/environments/{e['id']}")
        if "prod" in e["name"]:
            env["kind"], env["confirm_writes"] = "prod", True
            env["values"] += [{"key": "om_token", "value": "eyJhbGciOiJIUzI1NiJ9", "current": "eyJ.live.token", "enabled": True, "type": "secret"}, {"key": "base_url", "value": "https://api.online-mahalla.uz", "enabled": True, "type": "default"}]
        else:
            env["kind"] = "dev"
            env["values"] += [{"key": "base_url", "value": "http://localhost:8000", "current": "http://127.0.0.1:8000", "enabled": True, "type": "default"}]
        app.api("PUT", f"/api/environments/{e['id']}", env)


def shooter(page, theme):
    outdir = OUT / theme
    outdir.mkdir(parents=True, exist_ok=True)

    def shoot(name):
        page.wait_for_timeout(250)                       # animatsiya/transition tugashi (faqat suratga olishdan oldin)
        page.mouse.move(2, 2)
        path = outdir / f"{name}.png"
        page.screenshot(path=str(path))
        w, h, uniq = png_unique_colors(path)
        assert (w, h) == (1440, 900) and uniq > 5, f"{name}: bo'sh yoki noto'g'ri o'lcham ({w}x{h}, {uniq})"
    return shoot


@pytest.fixture(params=["light", "dark"])
def shot_page(request, app, browser, world):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, locale="uz")
    ctx.add_init_script(f"try {{ localStorage.setItem('apiRunnerTheme', '{request.param}') }} catch (e) {{}}")
    page = ctx.new_page()
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.add_style_tag(content="*{caret-color:transparent!important;animation:none!important;transition:none!important}")
    yield page, request.param
    ctx.close()


def open_req(p, name):
    p.locator(f"[data-name='{name}']").dblclick()
    expect(T(p, "request-editor")).to_be_visible()


def send_ok(p):
    with p.expect_response(lambda r: r.url.endswith("/run_one")):
        T(p, "send").click()
    expect(T(p, "resp-status")).to_have_text(re.compile(r"^(200|ERR)"))


def test_screen_welcome(shot_page):
    p, theme = shot_page
    expect(T(p, "no-tabs")).to_be_visible()
    shooter(p, theme)("welcome")


def test_screen_editor_empty_response(shot_page):
    p, theme = shot_page
    open_req(p, "v2/mobile/contracts/main")
    shooter(p, theme)("editor-no-response")


def test_screen_editor_params_with_response(shot_page):
    p, theme = shot_page
    open_req(p, "v2/mobile/contracts/main")
    send_ok(p)
    shooter(p, theme)("editor-params-response")


def test_screen_editor_body_and_auth_and_headers(shot_page):
    p, theme = shot_page
    open_req(p, "v4/uzasbo")
    shoot = shooter(p, theme)
    p.click("[data-section=body]")
    send_ok(p)
    shoot("editor-body")
    p.click("[data-section=auth]")
    shoot("editor-auth")
    p.click("[data-section=headers]")
    shoot("editor-headers")


def test_screen_multi_tabs_with_dirty_dot(shot_page):
    p, theme = shot_page
    open_req(p, "v2/mobile/contracts/main")
    open_req(p, "v4/uzasbo")
    open_req(p, "v1/payments/list")
    p.click("[data-section=body]")
    set_body_mode(p, "json")
    p.fill("[data-testid=url]", "{{base_url}}/echo?changed={{undefined_var}}")
    shooter(p, theme)("editor-tabs-dirty-chips")


def test_screen_sidebar_panels(shot_page):
    p, theme = shot_page
    open_req(p, "v1/payments/list")
    shoot = shooter(p, theme)
    p.click("[data-testid=sb-environments]")
    shoot("sidebar-environments")
    p.click("[data-testid=sb-history]")
    shoot("sidebar-history")


def test_screen_environment_tab(shot_page):
    p, theme = shot_page
    p.click("[data-testid=sb-environments]")
    T(p, "env-row").first.click()
    expect(T(p, "env-tab")).to_be_visible()
    shooter(p, theme)("environment-tab")


def test_screen_runner(shot_page):
    p, theme = shot_page
    p.locator("[data-name='Ijara']").click(button="right")
    p.click("[data-act=runner]")
    expect(T(p, "runner-tab")).to_be_visible()
    shoot = shooter(p, theme)
    shoot("runner-idle")
    T(p, "runner-run").click()
    expect(T(p, "runner-result").first).to_be_visible()
    expect(T(p, "runner-run")).to_be_enabled()
    shoot("runner-results")


def test_screen_batch_results(shot_page, tmp_path):
    p, theme = shot_page
    open_req(p, "v1/payments/list")
    p.click("[data-section=batch]")
    f = tmp_path / "shartnomalar.csv"
    f.write_text("contract_id,pinfl\n1,3050\n2,3051\n3,3052\n")
    T(p, "batch-file").set_input_files(str(f))
    T(p, "batch-run").click()
    expect(T(p, "batch-status")).to_contain_text("Bajarildi")
    shooter(p, theme)("batch-results")


def test_screen_settings_and_cookies(shot_page, echo_server):
    p, theme = shot_page
    shoot = shooter(p, theme)
    T(p, "settings-btn").click()
    expect(T(p, "settings-tab")).to_be_visible()
    shoot("settings")
    p.evaluate("fetch('/api/cookies',{method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':window.__API_TOKEN__},body:JSON.stringify({domain:'127.0.0.1',name:'sessionid',value:'abc123',httponly:true})})")
    T(p, "cookies-btn").click()
    expect(T(p, "cookies-tab")).to_be_visible()
    shoot("cookies")


def test_screen_collection_settings(shot_page):
    p, theme = shot_page
    p.locator("[data-name='Ijara']").dblclick()
    expect(T(p, "tab-collection")).to_be_visible()
    shooter(p, theme)("collection-settings")


@pytest.mark.skipif(PHASE == "before", reason="⌘K va chip tooltip eski UI'da yo'q")
def test_screen_cmdk_and_var_hover(shot_page):
    p, theme = shot_page
    open_req(p, "v2/mobile/contracts/main")
    shoot = shooter(p, theme)
    p.locator(".urlfield [data-testid=var-chip]").first.hover()
    expect(T(p, "chip-tip")).to_be_visible()
    shoot("editor-var-hover")
    p.mouse.move(5, 5)
    p.keyboard.press("Control+k")
    p.keyboard.type("pay")
    expect(T(p, "cmdk-row").first).to_be_visible()
    shoot("cmdk")


@pytest.mark.skipif(PHASE == "before", reason="skriptlar eski UI'da yo'q")
def test_screen_scripts_tests_tab_and_console(shot_page):
    p, theme = shot_page
    open_req(p, "v2/mobile/contracts/main")
    shoot = shooter(p, theme)
    p.click("[data-section=scripts]")
    T(p, "script-pre").fill("// Token bo'lmasa — pre-request'da olamiz\nif (!pm.environment.get('token')) {\n    pm.environment.set('token', 'abc-123');\n}\npm.request.headers.add({ key: 'X-Request-Id', value: pm.variables.replaceIn('{{$guid}}') });")
    p.click("[data-testid=script-tab-test]")
    T(p, "script-test").fill("pm.test('Status kodi 200', function () {\n    pm.response.to.have.status(200);\n});\npm.test('Javob vaqti < 500 ms', function () {\n    pm.expect(pm.response.responseTime).to.be.below(500);\n});\npm.test('Sahifa 2 ga teng', function () {\n    pm.expect(pm.response.json().args.page[0]).to.equal('2');\n});\nconsole.log('Tekshiruv tugadi', pm.info.requestName);")
    shoot("scripts-editor")
    send_ok(p)
    T(p, "rp-tests-tab").click()
    expect(T(p, "test-row").first).to_be_visible()
    shoot("tests-tab")
    T(p, "console-btn").click()
    expect(T(p, "console-entry").first).to_be_visible()
    shoot("console-panel")


# ── Bosqich 4 oldi ekranlari: Folder Overview, Env (Boshlang'ich/Joriy), Tarix diff, joylashuv, RunGuard, fayllar ──
@pytest.mark.skipif(PHASE == "before", reason="yangi ekranlar eski UI'da yo'q")
def test_screen_folder_overview(shot_page, app, echo_server):
    p, theme = shot_page
    open_req(p, "v2/mobile/contracts/main")
    send_ok(p)
    p.locator("[data-name='Shartnomalar']").dblclick()
    expect(T(p, "tab-folder")).to_be_visible()
    expect(T(p, "ov-row-status")).to_have_count(1)
    shooter(p, theme)("folder-overview")


@pytest.mark.skipif(PHASE == "before", reason="yangi ekranlar eski UI'da yo'q")
def test_screen_environment_prod_initial_current(shot_page, app, echo_server):
    p, theme = shot_page
    seed_rich(app, echo_server)
    prod = next(e["id"] for e in app.api("GET", "/api/workspace")["environments"] if "prod" in e["name"])
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": prod})
    p.reload()
    p.wait_for_selector("[data-testid=app]")
    p.add_style_tag(content="*{caret-color:transparent!important;animation:none!important;transition:none!important}")
    p.click("[data-testid=sb-environments]")
    T(p, "env-row").nth(1).dblclick()
    expect(T(p, "env-tab")).to_be_visible()
    expect(T(p, "prod-badge")).to_be_visible()
    shooter(p, theme)("environment-prod")


@pytest.mark.skipif(PHASE == "before", reason="yangi ekranlar eski UI'da yo'q")
def test_screen_history_compare(shot_page, app, echo_server):
    p, theme = shot_page
    seed_rich(app, echo_server)
    p.reload()
    p.wait_for_selector("[data-testid=app]")
    p.add_style_tag(content="*{caret-color:transparent!important;animation:none!important;transition:none!important}")
    p.click("[data-testid=sb-history]")
    T(p, "history-btn").click()
    T(p, "hd-search").fill("mobile/lists")
    T(p, "hd-expand").click()
    T(p, "hd-pick-sub").nth(0).check()
    T(p, "hd-pick-sub").nth(1).check()
    expect(T(p, "hd-diff")).to_be_visible()
    T(p, "hd-search").fill("")
    p.wait_for_timeout(100)
    shooter(p, theme)("history-compare")


@pytest.mark.skipif(PHASE == "before", reason="yangi ekranlar eski UI'da yo'q")
def test_screen_layout_side_by_side_and_dense(shot_page):
    p, theme = shot_page
    T(p, "layout-toggle").click()
    open_req(p, "v2/mobile/contracts/main")
    send_ok(p)
    shoot = shooter(p, theme)
    shoot("layout-side-by-side")
    T(p, "settings-btn").click()
    T(p, "view-dense").check()
    open_req(p, "v2/mobile/contracts/main")
    shoot("dense-mode")


@pytest.mark.skipif(PHASE == "before", reason="yangi ekranlar eski UI'da yo'q")
def test_screen_runguard_dialog(shot_page, app, echo_server):
    p, theme = shot_page
    seed_rich(app, echo_server)
    prod = next(e["id"] for e in app.api("GET", "/api/workspace")["environments"] if "prod" in e["name"])
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": prod})
    p.reload()
    p.wait_for_selector("[data-testid=app]")
    p.add_style_tag(content="*{caret-color:transparent!important;animation:none!important;transition:none!important}")
    p.locator("[data-name='Ijara']").click(button="right")
    p.click("[data-act=runner]")
    for cb in p.locator("[data-testid=runner-item] input[type=checkbox]").all():
        cb.check()
    T(p, "runner-run").click()
    expect(T(p, "runguard")).to_be_visible()
    T(p, "rg-all").check()
    shooter(p, theme)("runguard")
    T(p, "rg-cancel").click()


@pytest.mark.skipif(PHASE == "before", reason="yangi ekranlar eski UI'da yo'q")
def test_screen_form_data_files(shot_page, tmp_path):
    p, theme = shot_page
    T(p, "new-tab").click()
    p.select_option("[data-testid=method]", "POST")
    p.fill("[data-testid=url]", "{{base_url}}/upload")
    p.click("[data-section=body]")
    set_body_mode(p, "multipart")
    grid = "[data-testid=formdata-table]"
    p.locator(f"{grid} [data-cell='0:0']").fill("title")
    p.locator(f"{grid} [data-cell='0:1']").fill("Ariza")
    p.locator(f"{grid} [data-cell='1:0']").fill("file")
    p.locator(f"{grid} [data-testid=fd-type]").nth(1).select_option("file")
    a, b = tmp_path / "ariza.pdf", tmp_path / "ilova.pdf"
    a.write_bytes(b"%PDF" * 3000)
    b.write_bytes(b"%PDF" * 120)
    p.locator(f"{grid} input[type=file]").first.set_input_files([str(a), str(b)])
    expect(T(p, "fd-file")).to_have_count(2)
    p.locator(f"{grid} [data-cell='2:0']").fill("eskirgan")
    p.locator(f"{grid} [data-testid=fd-type]").nth(2).select_option("file")
    shooter(p, theme)("form-data-files")
