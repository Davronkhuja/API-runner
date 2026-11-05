"""UI audit: ilovani Playwright bilan matritsa bo'yicha aylanib, skrinshot oladi va avtomatik detektorlar bilan muammolarni yig'adi.

Ishlatish:  python3 tools/ui_audit.py --out /tmp/ui-audit [--quick] [--screens a,b] [--viewports 1440x900]
Natija:     <out>/shots/<viewport>-<theme>/<ekran>.png  va  <out>/findings.json  (har topilma: ekran, tur, tafsilot).
Faqat tmp workspace'da ishlaydi (foydalanuvchi ma'lumotiga tegmaydi).
"""
import argparse
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ["APIRUNNER_TESTING"] = "1"

import requests  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from apirunner.app import create_app  # noqa: E402

TOKEN = "audit-token"
AXE_EXCLUDE = "{ exclude: [['.tabs-scroll']] }"   # tablist + yopish tugmasi: qabul qilingan istisno (docs/ui-audit.md)
AXE = (ROOT / "web" / "node_modules" / "axe-core" / "axe.min.js")
LONG_NAME = "https://api.online-mahalla.uz/api/v1/hm/projects/item/with/a/very/long/path/that/keeps/going/and/going/for/more/than/one/hundred/characters"
VIEWPORTS = [("1280x800", 1280, 800), ("1440x900", 1440, 900), ("1920x1080", 1920, 1080), ("1440x900@80%", 1800, 1125), ("1440x900@125%", 1152, 720)]
THEMES = ["light", "dark"]

DETECT_JS = (ROOT / "tools" / "ui_detect.js").read_text(encoding="utf-8")


def start_servers(tmp):
    from conftest import _build_echo_app  # tests/conftest.py (faqat CLI'da; testlar seed()/scenes() ni ishlatadi)
    echo = make_server("127.0.0.1", 0, _build_echo_app(), threaded=True)
    threading.Thread(target=echo.serve_forever, daemon=True).start()
    app = create_app(workspace_dir=str(tmp / "workspace"), saved_file=str(tmp / "saved_requests.json"), upload_dir=str(tmp / "uploads"),
                     session_token=TOKEN, backup_dir=str(tmp / "backups"))
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_port}", f"http://127.0.0.1:{echo.server_port}", app


def api(base, method, path, js=None):
    r = requests.request(method, base + path, json=js, headers={"X-Session-Token": TOKEN})
    r.raise_for_status()
    return r.json()


def seed(base, echo, app):
    cid = api(base, "POST", "/api/collections", {"name": "Katta collection"})["id"]
    col = api(base, "GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base_url", "value": echo}, {"key": "token", "value": "eyJhbGciOiJIUzI1NiJ9", "type": "secret"}]
    col["auth"] = {"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}]}
    body = json.dumps({"applicant": {"pinfl": "30501900000000", "name": "Ali"}, "items": [{"id": i, "code": f"C-{i:04d}", "qty": i % 7, "ok": i % 2 == 0, "tags": ["a", "b"]} for i in range(42)]}, indent=2)
    heavy = {"id": "heavy", "name": "Og'ir so'rov", "request": {"method": "POST", "header": [{"key": f"X-Header-{i:02d}", "value": "value-" * (1 + i % 6), "description": "izoh"} for i in range(40)],
             "url": {"raw": "{{base_url}}/echo?pinfl=30501900000000&contract_id=C-1042&page=1&size=20&sort=created_at,desc&filter=status:active&fields=id,name,code,amount", "query": [{"key": "pinfl", "value": "30501900000000"}, {"key": "contract_id", "value": "C-1042"}]},
             "body": {"mode": "raw", "raw": body, "options": {"raw": {"language": "json"}}}}, "response": [],
             "event": [{"listen": "prerequest", "script": {"type": "text/javascript", "exec": ["pm.environment.set('x', 1)", "console.log('pre')"]}}, {"listen": "test", "script": {"type": "text/javascript", "exec": ["pm.test('200', () => pm.response.to.have.status(200))"]}}]}
    simple = {"id": "simple", "name": "Oddiy so'rov", "request": {"method": "GET", "header": [], "url": {"raw": "{{base_url}}/echo?a=1", "query": [{"key": "a", "value": "1"}]}}, "response": []}
    longn = {"id": "longn", "name": LONG_NAME, "request": {"method": "GET", "header": [], "url": {"raw": "{{base_url}}/echo"}}, "response": []}
    many = [{"id": f"m{i}", "name": f"v1/resource-{i:02d}/" + ("long-segment-" * (i % 5)), "request": {"method": ["GET", "POST", "PUT", "DELETE"][i % 4], "header": [], "url": {"raw": "{{base_url}}/echo?i=%d" % i}}, "response": []} for i in range(80)]
    col["item"] = [{"id": "fbig", "name": "Ko'p so'rovli papka", "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "FOLDER-TOK", "type": "string"}]}, "item": many}, heavy, simple, longn]
    api(base, "PUT", f"/api/collections/{cid}", col)
    for name, kind in (("Dev", "dev"), ("Prod", "prod")):
        eid = api(base, "POST", "/api/environments", {"name": name, "kind": kind})["id"]
        e = api(base, "GET", f"/api/environments/{eid}")
        e["values"] = [{"key": "base_url", "value": echo, "current": echo, "enabled": True, "type": "default"}, {"key": "api_token", "value": "secret-value-1234567890", "enabled": True, "type": "secret"}]
        api(base, "PUT", f"/api/environments/{eid}", e)
        if name == "Dev":
            api(base, "PUT", "/api/workspace/meta", {"active_environment_id": eid})
    db = app.extensions["db"]
    import time
    now = time.time()
    for i in range(14):
        db.add_history("request", {"method": ["GET", "POST"][i % 2], "url": f"https://api.online-mahalla.uz/api/v1/gcp/pinfl{i // 3}", "headers": [], "params": [{"name": "pinfl", "value": "3050"}], "status": [200, 404, 500][i % 3], "time": 0.2, "size": 900}, ts=now - i * 4000)
    return cid


def js_ready(page):
    page.wait_for_selector("[data-testid=app]")
    page.add_style_tag(content="*{caret-color:transparent!important;animation:none!important;transition:none!important}")


def open_req(page, name):
    page.locator(f"[data-name=\"{name}\"]").first.dblclick()
    page.wait_for_selector("[data-testid=request-editor]")


def send(page):
    with page.expect_response(lambda r: r.url.endswith("/run_one"), timeout=20000):
        page.click("[data-testid=send]")
        try:                                                  # Prod/tasdiq talab qiladigan muhitda yozuvchi so'rov dialogi
            page.wait_for_selector("[data-testid=confirm-ok]", timeout=800)
            page.click("[data-testid=confirm-ok]")
        except Exception:  # noqa: BLE001
            pass
    page.wait_for_selector("[data-testid=resp-status]")


def new_tab_req(page, echo, path, method="GET"):
    page.click("[data-testid=new-tab]")
    page.select_option("[data-testid=method]", method)
    page.fill("[data-testid=url]", echo + path)
    page.keyboard.press("Escape")                                    # URL tarixi ro'yxati yopilsin (u bo'limlar qatorini qoplaydi)


def scenes(base, echo):
    """{ekran_nomi: fn(page)} — har biri sahifani kerakli holatga keltiradi."""
    S = {}
    S["welcome"] = lambda p: None
    S["editor-empty"] = lambda p: p.click("[data-testid=new-tab]")
    def ed_ok(p):
        open_req(p, "Oddiy so'rov"); send(p)
    S["editor-simple-response"] = ed_ok
    def heavy(sec):
        def f(p):
            open_req(p, "Og'ir so'rov"); p.click(f"[data-section={sec}]")
        return f
    for sec in ("params", "headers", "auth", "body", "scripts", "settings", "batch"):
        S[f"heavy-{sec}"] = heavy(sec)
    def gql(p):
        new_tab_req(p, echo, "/echo", "POST"); p.click("[data-section=body]"); p.click("[data-testid=body-mode] [data-mode=graphql]")
    S["body-graphql"] = gql
    def formdata(p):
        new_tab_req(p, echo, "/echo", "POST"); p.click("[data-section=body]"); p.click("[data-testid=body-mode] [data-mode=multipart]")
    S["body-formdata"] = formdata
    def resp(path, tab=None, mode=None):
        def f(p):
            new_tab_req(p, echo, path, "GET"); send(p)
            if tab: p.click(f"[data-testid={tab}]")
        return f
    S["resp-2mb"] = resp("/bigjson?n=330000")
    S["resp-400"] = resp("/status/400")
    S["resp-image"] = resp("/png")
    S["resp-204"] = resp("/nocontent")
    S["resp-headers-tab"] = resp("/echo?z=1", "rp-headers-tab")
    S["resp-cookies-tab"] = resp("/cookie/set?name=a&value=1", "rp-cookies-tab")
    S["resp-tests-tab"] = resp("/echo?z=1", "rp-tests-tab")
    def code_dlg(p):
        open_req(p, "Og'ir so'rov"); p.click("[data-testid=curl-btn]"); p.wait_for_selector("[data-testid=curl-drawer]")
    S["dlg-code-long"] = code_dlg
    def saveas(p):
        new_tab_req(p, echo, "/echo?a=1"); p.click("[data-testid=save]"); p.wait_for_selector("[data-testid=saveas-dialog]")
    S["dlg-saveas"] = saveas
    def move(p):
        p.locator("[data-name=\"Oddiy so'rov\"]").first.click(button="right"); p.click("[data-act=move]"); p.wait_for_selector(".dialog")
    S["dlg-move"] = move
    def confirm(p):
        p.click("[data-testid=sb-environments]"); p.locator("[data-testid=env-row]").first.locator("button[aria-label=\"Muhitni o'chirish\"]").click(); p.wait_for_selector("[data-testid=confirm-dialog]")
    S["dlg-confirm"] = confirm
    def runguard(p):
        eid = [e for e in api(base, "GET", "/api/workspace")["environments"] if e["name"] == "Prod"][0]["id"]
        api(base, "PUT", "/api/workspace/meta", {"active_environment_id": eid}); p.reload(); js_ready(p)
        p.locator("[data-name=\"Katta collection\"]").first.click(button="right"); p.click("[data-act=runner]")
        p.click("[data-testid=runner-run]"); p.wait_for_selector("[data-testid=runguard]")
        p.click("[data-testid=rg-all]")
    S["dlg-runguard"] = runguard
    def bulk(p):
        p.locator("[data-name=\"Katta collection\"]").first.dblclick(); p.wait_for_selector("[data-testid=tab-collection]")
        p.click("[data-scope-section=auth]")
        p.select_option("[data-testid=auth-type]", "bearer") if p.locator("[data-testid=auth-type]").count() else None
    S["collection-auth"] = bulk
    def envtab(p):
        p.click("[data-testid=sb-environments]"); p.locator("[data-testid=env-row]").first.dblclick(); p.wait_for_selector("[data-testid=env-tab]")
    S["env-tab"] = envtab
    S["env-eye"] = lambda p: p.click("[data-testid=env-vars-btn]")
    def folder(p):
        p.locator("[data-name=\"Ko'p so'rovli papka\"]").first.dblclick(); p.wait_for_selector("[data-testid=tab-folder]")
    S["folder-overview-80"] = folder
    def hist(p):
        p.click("[data-testid=sb-history]"); p.click("[data-testid=history-btn]"); p.wait_for_selector("[data-testid=history-drawer]")
    S["history-drawer"] = hist
    S["sidebar-history"] = lambda p: p.click("[data-testid=sb-history]")
    S["settings"] = lambda p: p.click("[data-testid=settings-btn]")
    def runner(p):
        p.locator("[data-name=\"Katta collection\"]").first.click(button="right"); p.click("[data-act=runner]"); p.wait_for_selector("[data-testid=runner-tab]")
    S["runner"] = runner
    def run_done(p, times=1):
        runner(p)
        for _ in range(times):
            p.click("[data-testid=runner-run]")
            try:
                p.wait_for_selector("[data-testid=runguard]", timeout=800); p.click("[data-testid=runguard-run-get]")
            except Exception:  # noqa: BLE001 — Prod bo'lmasa RunGuard chiqmaydi
                pass
            p.wait_for_function("() => /Tugadi|To'xtatildi/.test(document.querySelector('[data-testid=runner-progress-label]')?.textContent || '')", timeout=30000)
    S["runner-results"] = lambda p: (run_done(p), p.locator("[data-testid=runner-row]").first.click())
    def run_compare(p):
        run_done(p, 2); p.click("[data-testid=runner-compare]"); p.wait_for_selector("[data-testid=runner-compare-dialog]")
    S["runner-compare"] = run_compare
    S["runner-export-menu"] = lambda p: (run_done(p), p.click("[data-testid=runner-export]"))
    def mock_version(p, **over):
        import apirunner
        info = {"version": apirunner.__version__, "ui_version": apirunner.__version__, "started": 1, "managed": True, "active": 0, **over}
        p.route("**/api/version", lambda r: r.fulfill(json=info))
        p.reload(); js_ready(p)
    S["server-stale"] = lambda p: (mock_version(p, version="0.0.1"), p.wait_for_selector("[data-testid=restart-server]"))
    S["server-stale-hint"] = lambda p: (mock_version(p, version="0.0.1", managed=False), p.wait_for_selector("[data-testid=restart-hint]"))
    S["new-build"] = lambda p: (mock_version(p, ui_version="99.0.0"), p.wait_for_selector("[data-testid=new-build]"))
    def restarting(p):
        mock_version(p, version="0.0.1")
        p.route("**/api/admin/restart", lambda r: r.fulfill(json={"ok": True}))
        p.click("[data-testid=restart-server]"); p.wait_for_selector("[data-testid=restarting]")
    S["restarting"] = restarting
    S["cookies"] = lambda p: p.click("[data-testid=cookies-btn]")
    def console(p):
        open_req(p, "Oddiy so'rov"); send(p); p.click("[data-testid=console-btn]"); p.wait_for_selector("[data-testid=console]")
    S["console"] = console
    def cmdk(p):
        p.keyboard.press("Control+k"); p.keyboard.type("res"); p.wait_for_selector("[data-testid=cmdk]")
    S["cmdk"] = cmdk
    def tabs30(p):
        tabs = [{"id": f"t{i}", "kind": "request", "ref": None, "title": f"So'rov raqami {i} va uzun sarlavha", "preview": False, "dirty": i % 5 == 0, "scroll": {"req": 0, "resp": 0}, "response": None,
                 "draft": {"name": f"So'rov {i}", "method": "GET", "url": echo + "/echo", "params": [{"key": "", "value": "", "enabled": True}], "headers": [{"key": "", "value": "", "enabled": True}]}} for i in range(30)]
        api(base, "PUT", "/api/ui-state", {"tabs": {"v": 1, "activeId": "t17", "tabs": tabs}}); p.reload(); js_ready(p)
    S["tabs-30"] = tabs30
    def longname(p):
        open_req(p, LONG_NAME)
    S["long-name-request"] = longname
    def side(p):
        p.click("[data-testid=layout-toggle]"); open_req(p, "Og'ir so'rov"); p.click("[data-section=body]"); send(p)
    S["layout-side"] = side
    def dense(p):
        p.click("[data-testid=settings-btn]"); p.check("[data-testid=view-dense]"); open_req(p, "Og'ir so'rov"); p.click("[data-section=headers]")
    S["layout-dense"] = dense
    def url120(p):
        open_req(p, "Og'ir so'rov"); p.focus("[data-testid=url]")
    S["url-120-focus"] = url120
    S["sidebar-80"] = lambda p: p.locator("[data-name=\"Ko'p so'rovli papka\"]").first.click()
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/ui-audit")
    ap.add_argument("--quick", action="store_true", help="faqat 1440x900 light/dark")
    ap.add_argument("--screens", default="")
    ap.add_argument("--viewports", default="")
    a = ap.parse_args()
    out = Path(a.out)
    findings = []
    with tempfile.TemporaryDirectory() as tmpd, sync_playwright() as pw:
        tmp = Path(tmpd)
        base, echo, app = start_servers(tmp)
        seed(base, echo, app)
        browser = pw.chromium.launch()
        vps = [v for v in VIEWPORTS if (not a.quick or v[0] == "1440x900") and (not a.viewports or v[0] in a.viewports.split(","))]
        S = scenes(base, echo)
        names = [n for n in S if not a.screens or n in a.screens.split(",")]
        for vname, w, h in vps:
            for theme in THEMES:
                ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="uz")
                ctx.add_init_script(f"try {{ localStorage.setItem('apiRunnerTheme','{theme}'); localStorage.removeItem('apirunner.view.v1') }} catch(e) {{}}")
                page = ctx.new_page()
                d = out / "shots" / f"{vname}-{theme}"
                d.mkdir(parents=True, exist_ok=True)
                for name in names:
                    api(base, "PUT", "/api/ui-state", {"tabs": {"v": 1, "activeId": None, "tabs": []}})
                    dev = [e for e in api(base, "GET", "/api/workspace")["environments"] if e["name"] == "Dev"]
                    if dev:
                        api(base, "PUT", "/api/workspace/meta", {"active_environment_id": dev[0]["id"]})      # har ekran Dev muhitida (runguard Prod'ga o'tkazadi)
                    page.goto(base); js_ready(page)
                    try:
                        S[name](page)
                        page.wait_for_timeout(250)
                    except Exception as exc:  # noqa: BLE001
                        findings.append({"screen": name, "viewport": vname, "theme": theme, "kind": "scenario-error", "detail": str(exc).splitlines()[0][:160]})
                        continue
                    shot = d / f"{name}.png"
                    page.screenshot(path=str(shot))
                    for f in page.evaluate(DETECT_JS):
                        findings.append({"screen": name, "viewport": vname, "theme": theme, "shot": str(shot.relative_to(out)), **f})
                    if AXE.exists():
                        page.add_script_tag(path=str(AXE))
                        res = page.evaluate("() => axe.run({ exclude: [['.tabs-scroll']] }, { resultTypes: ['violations'] }).then(r => r.violations.filter(v => ['serious','critical'].includes(v.impact)).map(v => ({ id: v.id, impact: v.impact, n: v.nodes.length, sample: v.nodes[0].target.join(' ') })))")
                        for v in res:
                            findings.append({"screen": name, "viewport": vname, "theme": theme, "shot": str(shot.relative_to(out)), "kind": f"axe-{v['id']}", "detail": f"{v['impact']} ×{v['n']} {v['sample']}"})
                ctx.close()
        browser.close()
    out.mkdir(parents=True, exist_ok=True)
    (out / "findings.json").write_text(json.dumps(findings, ensure_ascii=False, indent=1))
    print(f"{len(findings)} topilma → {out/'findings.json'}")


if __name__ == "__main__":
    main()
