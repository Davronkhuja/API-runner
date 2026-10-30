from playwright.sync_api import expect


def test_new_ui_loads_with_version_and_default_collection(new_page):
    expect(new_page.locator("[data-testid=version]")).to_contain_text("v2.")
    expect(new_page.locator("[data-testid=tree-row][data-kind=collection]")).to_have_count(1)
    expect(new_page.locator("[data-testid=no-tabs]")).to_be_visible()


def test_new_tab_send_get_shows_response(new_page, echo_server):
    p = new_page
    p.click("[data-testid=new-tab]")
    p.select_option("[data-testid=method]", "GET")
    p.fill("[data-testid=url]", echo_server + "/echo?hello=world")
    p.click("[data-testid=send]")
    expect(p.locator("[data-testid=resp-status]")).to_have_text("200")
    expect(p.locator("[data-testid=resp-body]")).to_contain_text('"hello"')
    expect(p.locator("[data-testid=resp-timing]")).to_contain_text("DNS —")
    # URL matni to'liq turadi; query ayni paytda Params jadvalida ham bor
    expect(p.locator("[data-testid=url]")).to_have_value(echo_server + "/echo?hello=world")
    p.click("[data-section=params]")
    expect(p.locator("[data-testid=params-table] input[type=text]").first).to_have_value("hello")
