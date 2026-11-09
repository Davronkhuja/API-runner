"""Vizual regressiya: 15 asosiy ekran × light/dark (1440×900) docs/screenshots/baseline/ bilan solishtiriladi.

Yangilash (ataylab dizayn o'zgargach):  UPDATE_BASELINE=1 python3 -m pytest tests/e2e/test_visual_regression.py
Taqqoslash: kanal farqi >24 bo'lgan piksellar ulushi ≤0.15% (shrift antialiasing farqi uchun). Javoblar `page.route` bilan qotirilgan, versiya/vaqt yashirilgan.
"""
import io
import json
import os
from pathlib import Path

import pytest
from PIL import Image, ImageChops
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "screenshots" / "baseline"
T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
UPDATE = bool(os.environ.get("UPDATE_BASELINE"))
BODY = json.dumps({"applicant": {"pinfl": "30501900000000", "name": "Ali"}, "items": [{"id": i, "code": f"C-{i:03d}", "ok": i % 2 == 0} for i in range(6)]}, indent=2)
HIDE = "[data-testid=version],[data-testid=backup-time],[data-testid=resp-time],[data-testid=settings-status]{visibility:hidden!important}*{caret-color:transparent!important;animation:none!important;transition:none!important}"


def canned(status=200, body=None, headers=None):
    payload = {"status": status, "time": 0.123, "size": 321, "url": "https://api.example.test/v1/contracts", "response": body if body is not None else {"success": True, "data": [{"id": 1, "name": "Alpha"}, {"id": 2, "name": "Beta"}]},
               "resp_headers": headers or {"Content-Type": "application/json", "X-Request-Id": "abc-123", "Cache-Control": "no-store"}, "set_cookies": [], "redirects": 0, "scripts": None}
    return lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(payload))


@pytest.fixture(params=["light", "dark"])
def vp(request, app, browser):
    cid = app.api("POST", "/api/collections", {"name": "Kolleksiya"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base", "value": "https://api.example.test"}]
    mk = lambda i, n, m: {"id": i, "name": n, "request": {"method": m, "header": [{"key": "Accept", "value": "application/json"}], "url": {"raw": "{{base}}/v1/" + n}, "body": {"mode": "raw", "raw": BODY, "options": {"raw": {"language": "json"}}} if m == "POST" else None}, "response": []}  # noqa: E731
    col["item"] = [{"id": "f", "name": "Shartnomalar", "item": [mk("a", "contracts", "GET"), mk("b", "payments", "POST"), mk("c", "users", "GET")]}, mk("d", "health", "GET")]
    app.api("PUT", f"/api/collections/{cid}", col)
    eid = app.api("POST", "/api/environments", {"name": "Dev", "kind": "dev"})["id"]
    e = app.api("GET", f"/api/environments/{eid}")
    e["values"] = [{"key": "base", "value": "https://api.example.test", "enabled": True, "type": "default"}, {"key": "token", "value": "secret-123", "enabled": True, "type": "secret"}]
    app.api("PUT", f"/api/environments/{eid}", e)
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, locale="uz")
    ctx.add_init_script(f"try {{ localStorage.setItem('apiRunnerTheme', '{request.param}') }} catch (e) {{}}")
    page = ctx.new_page()
    page.route("**/run_one", canned())
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.add_style_tag(content=HIDE)
    page.theme = request.param
    yield page
    ctx.close()


def snap(page, name):
    page.wait_for_timeout(300)
    page.mouse.move(2, 2)
    got = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    path = BASE / page.theme / f"{name}.png"
    if UPDATE or not path.exists():
        if not UPDATE:
            pytest.fail(f"Baseline yo'q: {path.relative_to(ROOT)} (UPDATE_BASELINE=1 bilan yarating)")
        path.parent.mkdir(parents=True, exist_ok=True)
        got.save(path, optimize=True)
        return
    want = Image.open(path).convert("RGB")
    assert got.size == want.size, f"{name}: o'lcham {got.size} != {want.size}"
    diff = ImageChops.difference(got, want).convert("L").point(lambda v: 255 if v > 24 else 0)
    ratio = sum(1 for v in diff.getdata() if v) / (got.size[0] * got.size[1])
    if ratio > 0.0015:
        out = ROOT / "test-results" / "visual"
        out.mkdir(parents=True, exist_ok=True)
        got.save(out / f"{page.theme}-{name}.actual.png")
        diff.save(out / f"{page.theme}-{name}.diff.png")
    assert ratio <= 0.0015, f"{name} ({page.theme}): {ratio:.2%} piksel farq qildi — test-results/visual/ ga qarang"


def open_req(p, name):
    p.locator(f"[data-name='{name}']").first.dblclick()
    expect(T(p, "request-editor")).to_be_visible()


def send(p):
    T(p, "send").click()
    expect(T(p, "resp-status")).to_be_visible()


def test_01_welcome(vp):
    expect(T(vp, "no-tabs")).to_be_visible()
    snap(vp, "01-welcome")


def test_02_editor_empty(vp):
    T(vp, "new-tab").click()
    snap(vp, "02-editor-empty")


def test_03_editor_json_body(vp):
    open_req(vp, "payments")
    vp.click("[data-section=body]")
    snap(vp, "03-editor-json-body")


def test_04_response_json(vp):
    open_req(vp, "contracts")
    send(vp)
    snap(vp, "04-response-json")


def test_05_response_400(vp):
    vp.route("**/run_one", canned(400, {"error": "Validation failed", "fields": {"pinfl": "14 xonali bo'lishi kerak"}}))
    open_req(vp, "payments")
    vp.click("[data-section=body]")
    send(vp)
    snap(vp, "05-response-400")


def test_06_response_headers(vp):
    open_req(vp, "contracts")
    send(vp)
    T(vp, "rp-headers-tab").click()
    snap(vp, "06-response-headers")


def test_07_folder_overview(vp):
    vp.locator("[data-name='Shartnomalar']").first.dblclick()
    expect(T(vp, "tab-folder")).to_be_visible()
    snap(vp, "07-folder-overview")


def test_08_environment(vp):
    T(vp, "sb-environments").click()
    T(vp, "env-row").first.dblclick()
    expect(T(vp, "env-tab")).to_be_visible()
    snap(vp, "08-environment")


def test_09_settings(vp):
    T(vp, "settings-btn").click()
    expect(T(vp, "settings-tab")).to_be_visible()
    snap(vp, "09-settings")


def test_10_runner(vp):
    vp.locator("[data-name='Kolleksiya']").first.click(button="right")
    vp.click("[data-act=runner]")
    expect(T(vp, "runner-tab")).to_be_visible()
    snap(vp, "10-runner")


def test_11_code_dialog(vp):
    open_req(vp, "payments")
    T(vp, "curl-btn").click()
    expect(T(vp, "curl-drawer")).to_be_visible()
    snap(vp, "11-code-dialog")


def test_12_import_dialog(vp):
    T(vp, "import-btn").click()
    expect(T(vp, "import-dialog")).to_be_visible()
    snap(vp, "12-import-dialog")


def test_13_cmdk(vp):
    vp.keyboard.press("Control+k")
    vp.keyboard.type("pay")
    expect(T(vp, "cmdk-row").first).to_be_visible()
    snap(vp, "13-cmdk")


def test_14_layout_side_by_side(vp):
    T(vp, "layout-toggle").click()
    open_req(vp, "payments")
    send(vp)
    snap(vp, "14-side-by-side")


def test_15_scripts(vp):
    open_req(vp, "contracts")
    vp.click("[data-section=scripts]")
    snap(vp, "15-scripts")


MASK_RUN = "[data-testid=runner-sub],[data-testid=runner-history],[data-testid=runner-s-avg],[data-testid=runner-row]>span:nth-child(5),[data-testid=rc-table] td:nth-child(5),[data-testid=rc-table] td:nth-child(3),[data-testid=rc-table] td:nth-child(4),[data-testid=rc-summary]{visibility:hidden!important}"


def _run_on_echo(vp, app, echo_server, times):
    """Haqiqiy Runner ishga tushiriladi (lokal echo server); vaqtga bog'liq kataklar yashiriladi."""
    cid = next(c["id"] for c in app.api("GET", "/api/workspace")["collections"] if c["name"] == "Kolleksiya")
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base", "value": echo_server}]
    app.api("PUT", f"/api/collections/{cid}", col)
    vp.reload()
    vp.wait_for_selector("[data-testid=app]")
    vp.add_style_tag(content=HIDE + MASK_RUN)
    vp.locator("[data-name='Kolleksiya']").first.click(button="right")
    vp.click("[data-act=runner]")
    for _ in range(times):
        vp.click("[data-testid=runner-run]")
        expect(T(vp, "runner-progress-label")).to_contain_text("Tugadi", timeout=30000)


def test_16_runner_results(vp, app, echo_server):
    _run_on_echo(vp, app, echo_server, 1)
    snap(vp, "16-runner-results")


def test_17_runner_compare(vp, app, echo_server):
    _run_on_echo(vp, app, echo_server, 2)
    T(vp, "runner-compare").click()
    expect(T(vp, "runner-compare-dialog")).to_be_visible()
    snap(vp, "17-runner-compare")


def test_18_batch_settings(vp):
    open_req(vp, "payments")
    vp.click("[data-section=batch]")
    snap(vp, "18-batch-settings")


def _cid(app):
    return next(c["id"] for c in app.api("GET", "/api/workspace")["collections"] if c["name"] == "Kolleksiya")


def test_19_example_tab(vp, app):
    cid = _cid(app)
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"][1]["response"] = [{"id": "e1", "name": "200 OK", "code": 200, "status": "OK", "header": [{"key": "Content-Type", "value": "application/json"}], "body": '{\n  "ok": true,\n  "items": [1, 2, 3]\n}', "_postman_previewlanguage": "json"}]
    app.api("PUT", f"/api/collections/{cid}", col)
    vp.reload()
    vp.wait_for_selector("[data-testid=app]")
    vp.add_style_tag(content=HIDE)
    vp.locator("[data-name='health']").first.locator("[data-testid=ex-chevron]").click()
    vp.locator("[data-testid=example-row]").first.dblclick()
    expect(T(vp, "example-tab")).to_be_visible()
    snap(vp, "19-example-tab")


def test_20_docs_panel(vp):
    open_req(vp, "contracts")
    T(vp, "docs-btn").click()
    T(vp, "req-docs-edit").click()
    T(vp, "req-docs-text").fill("# Shartnomalar\n\nRo'yxatni **qaytaradi**.\n\n- `page` — sahifa\n- `size` — hajm\n\n```json\n{\"page\": 1}\n```")
    T(vp, "req-docs-view").click()
    snap(vp, "20-docs-panel")


def test_21_trash(vp, app):
    cid = _cid(app)
    app.api("DELETE", f"/api/collections/{cid}/items/c")
    vp.reload()
    vp.wait_for_selector("[data-testid=app]")
    vp.add_style_tag(content=HIDE + "[data-testid=trash-days]{visibility:hidden!important}")
    T(vp, "trash-open").click()
    expect(T(vp, "trash-row")).to_have_count(1)
    snap(vp, "21-trash")


def test_22_find_replace(vp):
    T(vp, "find-open").click()
    T(vp, "fr-query").fill("api.example.test")
    T(vp, "fr-replacement").fill("api.new.test")
    expect(T(vp, "fr-row").first).to_be_visible()
    snap(vp, "22-find-replace")


def test_23_import_preview_with_conflict(vp):
    vp.add_style_tag(content=".toast,[data-testid=toast],[data-testid=tree]{visibility:hidden!important}")            # collection tartibi (fayl nomi = uuid) har safar boshqacha
    for _ in range(2):
        T(vp, "import-btn").click()
        T(vp, "import-dlg-file").set_input_files(str(ROOT / "tests" / "fixtures" / "insomnia" / "insomnia_v4.json"))
        expect(T(vp, "import-item")).to_have_count(2)
        if _ == 0:
            T(vp, "import-confirm").click()
            expect(T(vp, "import-dialog")).to_have_count(0)
    expect(T(vp, "import-conflict").first).to_be_visible()
    snap(vp, "23-import-conflict")


def test_24_export_dialog(vp):
    vp.locator("[data-testid=tree-row][data-kind=collection]").first.click(button="right")
    vp.click("[data-act=export]")
    expect(T(vp, "export-dialog")).to_be_visible()
    snap(vp, "24-export-dialog")


def test_25_settings_import_export(vp):
    vp.add_style_tag(content="#s-backups ~ *{display:none!important}*{scroll-behavior:auto!important}")                  # zaxiralar ro'yxatida vaqt tamg'alari bor
    T(vp, "settings-btn").click()
    expect(T(vp, "io-workspace-zip")).to_be_attached()
    expect(vp.locator("text=Jami:")).to_be_visible()                                          # asinxron bo'limlar (Fayllar, Skriptlar) yuklangach
    vp.wait_for_timeout(500)
    snap(vp, "25-settings-io")
