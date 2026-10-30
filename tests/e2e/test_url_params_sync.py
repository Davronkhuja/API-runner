"""Params <-> URL ikki tomonlama sinxron (eski UI'da bor edi; regressiya tuzatildi)."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    T(page, "new-tab").click()
    return page


def cell(p, row, col):
    return p.locator("[data-testid=params-table] tr").nth(row).locator("input[type=text]").nth(col)


def test_typing_query_in_url_fills_params_table(ui):
    T(ui, "url").fill("http://h/p?a=1&b=x%20y&c")
    ui.click("[data-section=params]")
    assert [cell(ui, i, 0).input_value() for i in range(3)] == ["a", "b", "c"]
    assert [cell(ui, i, 1).input_value() for i in range(3)] == ["1", "x y", ""]
    expect(T(ui, "url")).to_have_value("http://h/p?a=1&b=x%20y&c")        # foydalanuvchi yozgani buzilmaydi


def test_editing_params_table_updates_url(ui):
    T(ui, "url").fill("http://h/p")
    ui.click("[data-section=params]")
    cell(ui, 0, 0).fill("q")
    cell(ui, 0, 1).fill("a b")
    expect(T(ui, "url")).to_have_value("http://h/p?q=a%20b")
    cell(ui, 1, 0).fill("z")
    cell(ui, 1, 1).fill("2")
    expect(T(ui, "url")).to_have_value("http://h/p?q=a%20b&z=2")


def test_disabling_and_removing_rows_updates_url(ui):
    T(ui, "url").fill("http://h/p?a=1&b=2")
    ui.click("[data-section=params]")
    ui.locator("[data-testid=params-table] input[type=checkbox]").nth(0).uncheck()
    expect(T(ui, "url")).to_have_value("http://h/p?b=2")
    ui.locator("[data-testid=params-table] tr").nth(1).locator("button").click()
    expect(T(ui, "url")).to_have_value("http://h/p")
    # o'chirilgan (disabled) qator jadvalda qoladi va URL tahririda yo'qolmaydi
    assert cell(ui, 0, 0).input_value() == "a"
    T(ui, "url").fill("http://h/p?z=9")
    assert [cell(ui, i, 0).input_value() for i in range(2)] == ["z", "a"]


def test_variables_stay_readable_in_url(ui):
    ui.click("[data-section=params]")
    T(ui, "url").fill("http://h/{{base}}?k={{v}}")
    expect(T(ui, "url")).to_have_value("http://h/{{base}}?k={{v}}")
    ui.click("[data-section=params]")
    cell(ui, 0, 1).fill("{{w}}")
    expect(T(ui, "url")).to_have_value("http://h/{{base}}?k={{w}}")


def test_send_uses_table_as_source_of_truth(ui, echo_server):
    T(ui, "url").fill(echo_server + "/echo?a=1&b=2")
    ui.click("[data-section=params]")
    ui.locator("[data-testid=params-table] input[type=checkbox]").nth(1).uncheck()
    T(ui, "send").click()
    expect(T(ui, "resp-body")).to_contain_text('"a"')
    expect(T(ui, "resp-body")).not_to_contain_text('"b"')


def test_saved_request_roundtrip_keeps_query_and_params(ui, app, echo_server):
    T(ui, "url").fill(echo_server + "/echo?a=1")
    ui.click("[data-section=params]")
    cell(ui, 1, 0).fill("off")
    cell(ui, 1, 1).fill("2")
    ui.locator("[data-testid=params-table] input[type=checkbox]").nth(1).uncheck()
    T(ui, "save").click()
    T(ui, "saveas-ok").click()
    ui.wait_for_timeout(800)                                  # tab holati debounce bilan serverga yoziladi
    ui.reload()
    ui.wait_for_selector("[data-testid=tab]")
    expect(T(ui, "url")).to_have_value(echo_server + "/echo?a=1")
    ui.click("[data-section=params]")
    assert cell(ui, 1, 0).input_value() == "off"
    expect(ui.locator("[data-testid=params-table] input[type=checkbox]").nth(1)).not_to_be_checked()
