"""Javob matni serverda (SQLite) saqlanadi: yangilash/server qayta ishga tushishi, 5 MB chegara, binary, bo'sh javob, xato javob, tarix havolasi."""
import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page, echo_server):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.echo = echo_server
    return page


def send_to(p, path, method="GET"):
    T(p, "new-tab").click()
    p.select_option("[data-testid=method]", method)
    p.fill("[data-testid=url]", p.echo + path)
    with p.expect_response(lambda r: r.url.endswith("/run_one")) as i:
        T(p, "send").click()
    return i.value.json()


def reload(p):
    p.reload()
    p.wait_for_selector("[data-testid=app]")


def test_400_json_error_is_shown_immediately_and_restored_after_reload_and_server_restart(app, ui):
    d = send_to(ui, "/status/400")
    assert d["response_id"]
    expect(T(ui, "resp-status")).to_have_text("400")
    expect(T(ui, "resp-body")).to_contain_text('"code"')                                      # Body tabi ochilganda xato matni darhol ko'rinadi
    reload(ui)
    expect(T(ui, "resp-status")).to_have_text("400")
    expect(T(ui, "resp-body")).to_contain_text('"code"')
    expect(T(ui, "resp-not-saved")).to_have_count(0)
    app.restart()
    ui.goto(app.url)
    ui.wait_for_selector("[data-testid=app]")
    expect(T(ui, "resp-body")).to_contain_text('"code"')                                      # server qayta ishga tushgach ham


def test_headers_and_status_text_are_restored_too(ui):
    send_to(ui, "/echo?z=1")
    reload(ui)
    T(ui, "rp-headers-tab").click()
    expect(T(ui, "rp-headers")).to_contain_text("application/json")


def test_over_5mb_shows_first_5mb_with_clear_message_and_actions(ui, tmp_path):
    send_to(ui, "/bigtext?mb=6")
    reload(ui)
    banner = T(ui, "resp-trunc-banner")
    expect(banner).to_contain_text("To'liq javob saqlanmagan (6.0 MB)")
    expect(banner.locator("[data-testid=rp-save-file]")).to_have_text("Faylga saqlash")
    expect(banner.locator("[data-testid=resp-resend]")).to_have_text("Qayta yuborish")
    expect(T(ui, "resp-body")).to_be_visible()
    with ui.expect_download() as d:
        banner.locator("[data-testid=rp-save-file]").click()
    size = len(open(d.value.path(), "rb").read())
    assert 5 * 1024 * 1024 - 2048 <= size <= 5 * 1024 * 1024 + 2048                           # saqlangan 5 MB
    with ui.expect_response(lambda r: r.url.endswith("/run_one")):
        banner.locator("[data-testid=resp-resend]").click()
    expect(T(ui, "resp-trunc-banner")).to_have_count(0)


def test_image_response_is_previewed_and_survives_reload_and_can_be_saved(ui):
    d = send_to(ui, "/png")
    assert d["binary"] is True
    img = T(ui, "resp-image")
    expect(img).to_be_visible()
    ui.wait_for_function("document.querySelector('[data-testid=resp-image]').naturalWidth > 0")
    reload(ui)
    ui.wait_for_function("document.querySelector('[data-testid=resp-image]')?.naturalWidth > 0")
    expect(T(ui, "resp-not-saved")).to_have_count(0)
    with ui.expect_download() as dl:
        T(ui, "rp-save-file").click()
    assert open(dl.value.path(), "rb").read().startswith(b"\x89PNG") and dl.value.suggested_filename.endswith(".png")


def test_empty_204_response_shows_explicit_empty_state(ui):
    d = send_to(ui, "/nocontent")
    assert d["status"] == 204
    expect(T(ui, "resp-empty-body")).to_contain_text("Javob tanasi bo'sh")
    reload(ui)
    expect(T(ui, "resp-empty-body")).to_be_visible()


def test_history_keeps_only_a_reference_and_diff_reads_the_stored_response(app, ui):
    send_to(ui, "/echo?v=one")
    send_to(ui, "/echo?v=two")
    import time
    end = time.time() + 8
    while time.time() < end and len(app.api("GET", "/api/history?kind=request&limit=5")) < 2:
        time.sleep(0.1)                                                                       # tarixga yozish asinxron
    hist = app.api("GET", "/api/history?kind=request&limit=5")
    assert all("response_id" in h["payload"] and "resp_headers" not in h["payload"] for h in hist[:2])      # dublikat yo'q: matn bitta nusxada
    T(ui, "sb-history").click()
    T(ui, "history-btn").click()
    T(ui, "hd-pick").nth(0).check()
    T(ui, "hd-pick").nth(1).check()
    expect(T(ui, "hd-diff")).to_be_visible()
    expect(ui.locator(".hx-dl.add").first).to_be_visible()                                    # /echo?v=one vs ?v=two javoblarida farq bor


def test_closed_and_reopened_tab_keeps_its_response(ui):
    send_to(ui, "/status/418")
    ui.keyboard.press("Control+w")
    ui.wait_for_timeout(200)
    if T(ui, "close-dialog").count():
        ui.click("[data-testid=close-dialog] [data-act=discard]") if ui.locator("[data-testid=close-dialog] [data-act=discard]").count() else None
    ui.keyboard.press("Control+Shift+t")
    expect(T(ui, "resp-body")).to_contain_text("418")
