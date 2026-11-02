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
    p.select_option("[data-testid=body-mode]", "json") if p.locator("[data-testid=body-mode] option[value=json]").count() else None
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
