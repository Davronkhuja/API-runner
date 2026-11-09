"""WebSocket va SSE tablari: ulanish, xabarlar oqimi, filtr/qidiruv, shablonlar, saqlash, qayta ulanish, multi-tab, tarix."""
import json

import pytest
from playwright.sync_api import expect

from apirunner.core import scripting

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    eid = app.api("POST", "/api/environments", {"name": "E"})["id"]
    app.api("PUT", "/api/workspace/meta", {"active_environment_id": eid})
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.cid, page.eid = cid, eid
    return page


def new_proto(p, proto, url):
    T(p, "new-tab").click()
    p.select_option("[data-testid=method]", proto)
    p.fill("[data-testid=url]", url) if False else None
    u = T(p, "url")
    u.click()
    p.keyboard.press("ControlOrMeta+a")
    p.keyboard.type(url)
    p.keyboard.press("Escape")


def connect(p):
    T(p, "proto-connect").click()


def msgs(p):
    return T(p, "proto-msg")


def test_websocket_connect_send_receive_filter_search_detail_and_close(ui, ws_server):
    new_proto(ui, "WS", ws_server.url + "/echo")
    expect(T(ui, "proto-ws")).to_be_visible()
    expect(T(ui, "proto-status")).to_have_text("Ulanmagan")
    connect(ui)
    expect(T(ui, "proto-status")).to_have_text("Ulangan")
    expect(T(ui, "proto-sys").first).to_contain_text("Ulanilmoqda")
    box = T(ui, "proto-compose-text")
    box.click()
    ui.keyboard.type("hello ws")
    T(ui, "proto-send").click()
    expect(msgs(ui)).to_have_count(2)
    expect(ui.locator("[data-testid=proto-msg][data-dir=out]")).to_contain_text("hello ws")
    expect(ui.locator("[data-testid=proto-msg][data-dir=in]")).to_contain_text("hello ws")
    expect(T(ui, "proto-counts")).to_contain_text("1 · 8 B")
    ui.click("[data-testid=proto-compose] [data-kind=json]")
    T(ui, "proto-compose-text").click()
    ui.keyboard.type('{bad')
    expect(T(ui, "proto-json-err")).to_be_visible()                                       # JSON validatsiyasi
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type('{"n": 1, "name": "Ali"}')
    expect(T(ui, "proto-json-err")).to_have_count(0)
    ui.keyboard.press("ControlOrMeta+Enter")
    expect(msgs(ui)).to_have_count(4)
    ui.click("[data-dir=in]")
    expect(msgs(ui)).to_have_count(2)
    ui.click("[data-dir=out]")
    expect(msgs(ui)).to_have_count(2)
    expect(ui.locator("[data-testid=proto-msg][data-dir=in]")).to_have_count(0)
    ui.click("[data-dir=all]")
    T(ui, "proto-search").fill("Ali")
    expect(msgs(ui)).to_have_count(2)
    T(ui, "proto-search").fill("")
    msgs(ui).nth(3).click()
    expect(T(ui, "proto-detail")).to_contain_text('"name": "Ali"')                          # JSON chiroyli ko'rsatiladi
    T(ui, "proto-system").uncheck()
    expect(T(ui, "proto-sys")).to_have_count(0)
    T(ui, "proto-disconnect").click()
    expect(T(ui, "proto-status")).to_have_text("Uzildi")
    T(ui, "proto-system").check()
    expect(ui.locator("[data-testid=proto-sys][data-type=close]")).to_contain_text("kod 1000")
    expect(T(ui, "proto-send")).to_be_disabled()


def test_websocket_binary_send_and_receive(ui, ws_server):
    new_proto(ui, "WS", ws_server.url + "/echo")
    connect(ui)
    expect(T(ui, "proto-status")).to_have_text("Ulangan")
    ui.click("[data-testid=proto-compose] [data-kind=binary]")
    T(ui, "proto-compose-text").fill("00 ff 10 41")
    T(ui, "proto-send").click()
    expect(msgs(ui)).to_have_count(2)
    expect(ui.locator("[data-testid=proto-msg][data-dir=in]")).to_contain_text("binary 4 B")
    msgs(ui).nth(1).click()
    expect(T(ui, "proto-detail")).to_contain_text("00 ff 10 41")
    expect(T(ui, "proto-detail")).to_contain_text(".A")                                     # hex dump ASCII ustuni
    T(ui, "proto-disconnect").click()


def test_websocket_headers_subprotocol_env_variables_and_auth(ui, ws_server, app):
    e = app.api("GET", f"/api/environments/{ui.eid}")
    e["values"] = [{"key": "wsbase", "value": ws_server.url, "enabled": True, "type": "default"}, {"key": "tok", "value": "s3cret", "enabled": True, "type": "default"}]
    app.api("PUT", f"/api/environments/{ui.eid}", e)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    new_proto(ui, "WS", "{{wsbase}}/headers")
    ui.locator("[data-cell='0:0']").fill("X-Env")
    ui.locator("[data-cell='0:1']").fill("{{tok}}")
    ui.click("[data-psection=settings]")
    T(ui, "proto-subprotocols").fill("json.v1, chat")
    ui.click("[data-psection=auth]")
    ui.select_option("[data-testid=auth-type]", "bearer")
    T(ui, "auth-token").fill("{{tok}}")
    connect(ui)
    expect(msgs(ui)).to_have_count(1)
    msgs(ui).click()
    detail = ui.locator("[data-testid=proto-detail] pre").inner_text()
    got = json.loads(detail)
    h = {k.lower(): v for k, v in got["headers"].items()}
    assert h["x-env"] == "s3cret" and h["authorization"] == "Bearer s3cret" and got["subprotocol"] == "json.v1"
    expect(ui.locator("[data-testid=proto-sys][data-type=open]")).to_contain_text("subprotokol: json.v1")
    T(ui, "proto-disconnect").click()


def test_websocket_errors_are_readable_and_auto_reconnect_shows_attempts(ui, ws_server):
    new_proto(ui, "WS", ws_server.url + "/secure")
    connect(ui)
    expect(ui.locator("[data-testid=proto-sys][data-type=error]")).to_contain_text("HTTP 401")
    expect(T(ui, "proto-status")).to_have_text("Uzildi")
    ui.locator("[data-testid=url]").click()
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type(ws_server.url + "/drop")
    ui.click("[data-psection=settings]")
    T(ui, "proto-rc-enabled").check()
    T(ui, "proto-rc-delay").fill("50")
    T(ui, "proto-rc-max").fill("2")
    connect(ui)
    expect(ui.locator("[data-testid=proto-sys][data-type=reconnecting]")).to_have_count(2, timeout=10000)
    expect(ui.locator("[data-testid=proto-sys][data-type=reconnecting]").first).to_contain_text("urinish 1")
    expect(T(ui, "proto-status")).to_have_text("Uzildi")
    expect(ui.locator("[data-testid=proto-sys]", has_text="urinishlari tugadi")).to_have_count(1)


def test_websocket_save_to_collection_templates_survive_reload_and_tree_badge(ui, ws_server, app):
    new_proto(ui, "WS", ws_server.url + "/echo")
    ui.click("[data-psection=settings]")
    T(ui, "proto-subprotocols").fill("chat")
    T(ui, "proto-rc-enabled").check()
    T(ui, "proto-compose-text").click()
    ui.keyboard.type('{"type":"ping"}')
    T(ui, "proto-tpl-name").fill("Ping")
    T(ui, "proto-tpl-save").click()
    expect(T(ui, "proto-tpl")).to_have_text("Ping")
    T(ui, "save").click()
    T(ui, "saveas-name").fill("Echo WS")
    T(ui, "saveas-target").select_option(label="Col")
    T(ui, "saveas-ok").click()
    badge = ui.locator("[data-testid=tree-row][data-name='Echo WS'] .m")
    expect(badge).to_have_text("WS")
    item = next(i for i in app.api("GET", f"/api/collections/{ui.cid}")["item"] if i["name"] == "Echo WS")
    assert item["x-apirunner"]["protocol"] == "ws" and item["x-apirunner"]["proto"]["subprotocols"] == "chat" and item["x-apirunner"]["proto"]["messages"][0]["name"] == "Ping"
    assert item["request"]["method"] == "GET" and item["request"]["url"]["raw"].startswith("ws://")             # Postman'da oddiy so'rov
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-testid=tree-row][data-name='Echo WS']").dblclick()
    expect(T(ui, "proto-ws")).to_be_visible()
    expect(T(ui, "proto-tpl")).to_have_text("Ping")
    T(ui, "proto-tpl").click()
    expect(T(ui, "proto-tpl-name")).to_have_value("Ping")
    connect(ui)
    expect(T(ui, "proto-status")).to_have_text("Ulangan")
    T(ui, "proto-send").click()
    expect(msgs(ui)).to_have_count(2)
    T(ui, "proto-disconnect").click()
    T(ui, "proto-tpl-del").click()
    expect(T(ui, "proto-tpl")).to_have_count(0)


def test_two_protocol_tabs_run_side_by_side_and_keep_their_logs(ui, ws_server, sse_server):
    new_proto(ui, "WS", ws_server.url + "/echo")
    connect(ui)
    expect(T(ui, "proto-status")).to_have_text("Ulangan")
    T(ui, "proto-compose-text").click()
    ui.keyboard.type("first tab")
    T(ui, "proto-send").click()
    expect(msgs(ui)).to_have_count(2)
    new_proto(ui, "SSE", sse_server + "/sse/forever")
    connect(ui)
    expect(T(ui, "proto-sse")).to_be_visible()
    expect(msgs(ui).nth(2)).to_be_visible()
    ui.locator("[data-testid=tab]").first.click()                                          # birinchi (WS) tabga qaytish — jurnal saqlangan, ulanish tirik
    expect(T(ui, "proto-ws")).to_be_visible()
    expect(msgs(ui)).to_have_count(2)
    expect(T(ui, "proto-status")).to_have_text("Ulangan")
    ui.locator("[data-testid=tab]").nth(1).click()
    expect(T(ui, "proto-status")).to_have_text("Ulangan")
    T(ui, "proto-disconnect").click()
    expect(T(ui, "proto-status")).to_have_text("Uzildi")
    ui.locator("[data-testid=tab]").first.click()
    T(ui, "proto-disconnect").click()


def test_sse_events_types_filter_search_comments_and_resume(ui, sse_server):
    new_proto(ui, "SSE", sse_server + "/sse/basic")
    connect(ui)
    expect(T(ui, "proto-status")).to_have_text("Uzildi")                                    # server oqimni tugatdi
    expect(msgs(ui)).to_have_count(3)
    expect(T(ui, "proto-etype").first).to_have_text("tick")
    expect(ui.locator("[data-testid=proto-sys][data-type=comment]")).to_contain_text("hello comment")
    expect(msgs(ui).nth(1)).to_contain_text("line a line b")
    msgs(ui).nth(1).click()
    expect(T(ui, "proto-detail")).to_contain_text("line a\nline b")
    expect(T(ui, "proto-types")).to_be_visible()
    ui.click("[data-testid=proto-types] [data-type=tick]")                                  # tick yashirildi
    expect(msgs(ui)).to_have_count(2)
    ui.click("[data-testid=proto-types] [data-type=tick]")
    expect(msgs(ui)).to_have_count(3)
    T(ui, "proto-search").fill("tick")
    expect(msgs(ui)).to_have_count(1)
    T(ui, "proto-search").fill("")
    T(ui, "proto-regex").click()
    T(ui, "proto-search").fill(r"^\{")
    expect(msgs(ui)).to_have_count(1)


def test_sse_reconnect_with_last_event_id_and_post_body_and_http_error(ui, sse_server):
    new_proto(ui, "SSE", sse_server + "/sse/resume")
    ui.click("[data-psection=settings]")
    T(ui, "proto-rc-enabled").check()
    T(ui, "proto-rc-delay").fill("50")
    T(ui, "proto-rc-max").fill("1")
    connect(ui)
    expect(T(ui, "proto-status")).to_have_text("Uzildi", timeout=10000)
    texts = msgs(ui).all_inner_texts()
    assert [t for t in texts if "msg" in t][:4] and any("msg 3" in t for t in texts)         # Last-Event-ID bilan davom ettirildi
    expect(ui.locator("[data-testid=proto-sys][data-type=reconnecting]").first).to_contain_text("Last-Event-ID: 2")
    ui.locator("[data-testid=url]").click()
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type(sse_server + "/sse/status/404")
    ui.click("[data-psection=settings]")
    T(ui, "proto-rc-enabled").uncheck()
    connect(ui)
    expect(ui.locator("[data-testid=proto-sys][data-type=error]").last).to_contain_text("HTTP 404")
    ui.locator("[data-testid=url]").click()
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type(sse_server + "/sse/post")
    ui.click("[data-psection=settings]")
    T(ui, "proto-sse-method").select_option("POST")
    ui.click("[data-psection=body]")
    T(ui, "proto-body").click()
    ui.keyboard.type('{"q": "posted"}')
    connect(ui)
    expect(msgs(ui).last).to_contain_text("posted")


def test_session_log_is_restored_after_page_reload_and_history_has_ws_entry(ui, ws_server, app):
    new_proto(ui, "WS", ws_server.url + "/greet")
    connect(ui)
    expect(msgs(ui)).to_have_count(1)
    ui.wait_for_timeout(500)                                                               # tab holati serverga yozilsin
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    expect(T(ui, "proto-ws")).to_be_visible()
    expect(msgs(ui)).to_have_count(1)                                                      # jurnal server sessiyasidan tiklandi
    expect(T(ui, "proto-status")).to_have_text("Ulangan")
    T(ui, "proto-disconnect").click()
    hist = [h for h in app.api("GET", "/api/history?kind=request&limit=10") if h["payload"].get("protocol") == "ws"]
    assert hist and hist[0]["payload"]["method"] == "WS" and hist[0]["payload"]["url"].endswith("/greet")
    ui.click("[data-testid=sb-history]")
    row = ui.locator("[data-testid=sh-row]").first if ui.locator("[data-testid=sh-row]").count() else None
    if row is not None:
        row.click()
        expect(T(ui, "proto-ws").last).to_be_visible()


@pytest.mark.skipif(not scripting.available(), reason="quickjs-ng o'rnatilmagan")
def test_prerequest_script_adds_header_for_websocket(ui, ws_server):
    new_proto(ui, "WS", ws_server.url + "/headers")
    ui.click("[data-psection=scripts]")
    T(ui, "script-pre").fill("pm.request.headers.add({key: 'X-Script', value: 'from-pre'}); console.log('connecting from script');")
    connect(ui)
    expect(msgs(ui)).to_have_count(1)
    msgs(ui).click()
    assert {k.lower(): v for k, v in json.loads(ui.locator("[data-testid=proto-detail] pre").inner_text())["headers"].items()}["x-script"] == "from-pre"
    T(ui, "console-btn").click()
    expect(T(ui, "console-text").filter(has_text="connecting from script")).to_have_count(1)
    T(ui, "proto-disconnect").click()
