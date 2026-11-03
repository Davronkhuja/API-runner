import json

from playwright.sync_api import expect


def test_localstorage_import_button_posts_to_backend(app_page, app_url):
    p = app_page
    p.evaluate("""() => {
      localStorage.setItem('apiRunnerEnvs', JSON.stringify([{id:'e2e1', name:'E2E', vars:{k:'v'}}]));
      localStorage.setItem('apiRunnerUrlHistory', JSON.stringify(['http://h1']));
    }""")
    p.click("#lsImportBtn")
    expect(p.locator("body")).to_contain_text("Ko'chirildi")
    ws = p.evaluate("() => fetch('/api/workspace').then(r => r.json())")   # token fetch-patch orqali
    assert [e["id"] for e in ws["environments"]] == ["e2e1"]
    assert ws["environments"][0]["values"][0] == {"key": "k", "value": "v", "enabled": True, "type": "default"}


def test_import_with_empty_localstorage_warns(app_page):
    app_page.evaluate("() => localStorage.clear()")
    app_page.click("#lsImportBtn")
    expect(app_page.locator("body")).to_contain_text("ko'chiriladigan ma'lumot yo'q")


def test_api_without_token_is_rejected_from_page_context(app_page, app_url):
    status = app_page.evaluate("""url => { const f = Object.getPrototypeOf(window).fetch || window.fetch; 
        return new XMLHttpRequest && new Promise(res => { const x = new XMLHttpRequest();
        x.open('GET', url + '/saved'); x.onloadend = () => res(x.status); x.send(); }); }""", app_url)
    assert status == 401           # patch faqat fetch'da; XHR token'siz — server rad etadi


def test_existing_run_still_works_with_token(app_page, echo_server):
    app_page.select_option("#method", "GET")
    app_page.fill("#url", echo_server + "/echo")
    app_page.click("#runBtn")
    expect(app_page.locator("#statusTxt")).to_contain_text("Bajarildi")


def test_rejected_absolute_path_shows_clear_message(app_page, echo_server, tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("a")
    app_page.evaluate("""([url, path]) => fetch('/run_one', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({url, method:'POST', params:[{name:'d', value:path, type:'file'}]})}).then(r => r.json())
        .then(d => { window.__r = d; })""", [echo_server + "/echo", str(f)])
    app_page.wait_for_function("window.__r")
    assert "📎 orqali faylni qayta tanlang" in app_page.evaluate("window.__r.response")
