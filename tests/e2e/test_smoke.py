from playwright.sync_api import expect


def test_page_loads(app_page):
    expect(app_page.locator("#url")).to_be_visible()
    expect(app_page.locator("#runBtn")).to_be_enabled()
    expect(app_page.locator("#statusTxt")).to_have_text("Tayyor")


def test_send_get_and_see_result(app_page, echo_server):
    p = app_page
    p.select_option("#method", "GET")
    p.fill("#url", echo_server + "/echo?hello=world")
    p.click("#runBtn")
    expect(p.locator("#statusTxt")).to_contain_text("Bajarildi")
    expect(p.locator("#resultsList")).to_contain_text("200")
    expect(p.locator("#sOk")).to_have_text("1")


def test_error_status_shown(app_page, echo_server):
    p = app_page
    p.select_option("#method", "GET")
    p.fill("#url", echo_server + "/status/404")
    p.click("#runBtn")
    expect(p.locator("#statusTxt")).to_contain_text("1 xatolik")
    expect(p.locator("#s4xx")).to_have_text("1")


def test_empty_url_warns_and_does_not_run(app_page):
    app_page.fill("#url", "")
    app_page.click("#runBtn")
    expect(app_page.locator("#statusTxt")).to_have_text("Tayyor")
