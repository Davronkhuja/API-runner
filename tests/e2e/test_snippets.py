"""Bosqich 2 / Code snippet generatori: UI + haqiqiy bajarish (cURL, Python, Node)."""
import json
import shutil
import subprocess
import sys

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
MARK = {"curl": "curl -X", "python": "requests.request", "fetch": "await fetch(", "axios": "axios({", "node": ".request(options",
        "go": "http.NewRequest", "php": "curl_init", "java": "OkHttpClient", "csharp": "HttpClient"}


@pytest.fixture
def ui(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def setup_post(p, url):
    T(p, "new-tab").click()
    p.select_option("[data-testid=method]", "POST")
    p.fill("[data-testid=url]", url)
    p.click("[data-section=headers]")
    p.locator("[data-testid=headers-table] input[type=text]").nth(0).fill("X-Trace")
    p.locator("[data-testid=headers-table] input[type=text]").nth(1).fill("it's-1")
    p.click("[data-section=body]")
    p.select_option("[data-testid=body-mode]", "json")
    p.fill("[data-testid=body-raw]", '{"name":"Ali","q":"a\\"b"}')


def code(p, lang):
    p.select_option("[data-testid=snippet-lang]", lang)
    expect(T(p, "curl-output")).to_contain_text(MARK[lang])
    return T(p, "curl-output").inner_text()


def test_all_nine_languages_render(ui, echo_server):
    setup_post(ui, echo_server + "/echo?x=1")
    T(ui, "curl-btn").click()
    expect(T(ui, "snippet-lang").locator("option")).to_have_count(9)
    for lang in MARK:
        out = code(ui, lang)
        assert "/echo" in out and "X-Trace" in out and "Ali" in out, lang
    ui.keyboard.press("Escape")
    expect(T(ui, "curl-drawer")).to_have_count(0)


def test_variables_inherited_auth_and_apikey_are_resolved(app, page, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Sn"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "host", "value": echo_server}, {"key": "sec", "value": "S3CR3T", "type": "secret"}]
    col["auth"] = {"type": "bearer", "bearer": [{"key": "token", "value": "{{sec}}"}]}
    col["item"] = [{"id": "n1", "name": "Snip", "request": {"method": "GET", "header": [], "url": {"raw": "{{host}}/echo?k=v"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.locator("[data-name='Snip']").dblclick()
    T(page, "curl-btn").click()
    out = code(page, "curl")
    assert echo_server + "/echo?k=v" in out and "Authorization: Bearer S3CR3T" in out and "{{" not in out
    page.keyboard.press("Escape")
    page.click("[data-section=auth]")
    page.select_option("[data-testid=auth-type]", "apikey")
    T(page, "auth-f-key").fill("api_key")
    T(page, "auth-f-value").fill("{{sec}}")
    page.select_option("[data-testid=auth-f-in]", "query")
    T(page, "curl-btn").click()
    out = code(page, "python")
    assert "api_key=S3CR3T" in out
    page.keyboard.press("Escape")
    page.select_option("[data-testid=auth-type]", "jwt")
    T(page, "auth-f-secret").fill("x")
    T(page, "curl-btn").click()
    expect(T(page, "curl-output")).to_contain_text("JWT auth")                  # kodga kiritilmaydigan auth haqida eslatma


def test_unresolvable_url_does_not_break_the_page(ui):
    T(ui, "new-tab").click()
    ui.fill("[data-testid=url]", "http://")
    T(ui, "curl-btn").click()
    ui.select_option("[data-testid=snippet-lang]", "node")                       # new URL() xato beradi — sahifa ishlashda qolishi shart
    expect(T(ui, "curl-output")).to_contain_text("hosil qilib bo'lmadi")
    ui.select_option("[data-testid=snippet-lang]", "curl")
    expect(T(ui, "curl-output")).to_contain_text("curl -X GET")


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, **kw)


def test_generated_curl_actually_runs(ui, echo_server, tmp_path):
    if not shutil.which("curl"):
        pytest.skip("curl yo'q")
    setup_post(ui, echo_server + "/echo?x=1")
    T(ui, "curl-btn").click()
    r = run(["bash", "-c", code(ui, "curl")])
    assert r.returncode == 0, r.stderr
    j = json.loads(r.stdout)
    assert j["method"] == "POST" and j["args"] == {"x": ["1"]} and j["headers"]["X-Trace"] == "it's-1" and j["json"] == {"name": "Ali", "q": 'a"b'}


def test_generated_python_actually_runs(ui, echo_server, tmp_path):
    setup_post(ui, echo_server + "/echo?x=1")
    T(ui, "curl-btn").click()
    f = tmp_path / "snip.py"
    f.write_text(code(ui, "python"))
    r = run([sys.executable, str(f)])
    assert r.returncode == 0, r.stderr
    j = json.loads(r.stdout)
    assert j["method"] == "POST" and j["headers"]["X-Trace"] == "it's-1" and j["json"] == {"name": "Ali", "q": 'a"b'}


def test_generated_node_actually_runs(ui, echo_server, tmp_path):
    if not shutil.which("node"):
        pytest.skip("node yo'q")
    setup_post(ui, echo_server + "/echo?x=1")
    T(ui, "curl-btn").click()
    f = tmp_path / "snip.js"
    f.write_text(code(ui, "node"))
    r = run(["node", str(f)])
    assert r.returncode == 0, r.stderr
    j = json.loads(r.stdout)
    assert j["method"] == "POST" and j["args"] == {"x": ["1"]} and j["json"] == {"name": "Ali", "q": 'a"b'}
