"""Bosqich 2b: binary / GraphQL body, qator tavsifi, Bulk Edit."""
import json
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import eventually

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def send(p, status=200):
    with p.expect_response(lambda r: r.url.endswith("/run_one")) as info:
        T(p, "send").click()
    d = info.value.json()
    assert d["status"] == status, d
    return d


def new_post(p, url):
    T(p, "new-tab").click()
    p.select_option("[data-testid=method]", "POST")
    p.fill("[data-testid=url]", url)
    p.click("[data-section=body]")


# ── binary ──
def test_binary_body_sends_raw_file(ui, echo_server, tmp_path):
    new_post(ui, echo_server + "/echo")
    ui.select_option("[data-testid=body-mode]", "binary")
    expect(T(ui, "content-type-auto")).to_contain_text("application/octet-stream")
    f = tmp_path / "data.bin"
    f.write_bytes(b"BINARY-CONTENT-123")
    T(ui, "binary-file").set_input_files(str(f))
    expect(T(ui, "binary-name")).to_contain_text("data.bin")
    d = send(ui)["response"]
    assert d["data"] == "BINARY-CONTENT-123" and d["headers"]["Content-Type"] == "application/octet-stream"
    T(ui, "binary-clear").click()
    expect(T(ui, "binary-name")).to_have_count(0)


def test_binary_custom_content_type(ui, echo_server, tmp_path):
    new_post(ui, echo_server + "/echo")
    ui.select_option("[data-testid=body-mode]", "binary")
    T(ui, "content-type").fill("image/png")
    f = tmp_path / "x.png"
    f.write_bytes(b"PNG?")
    T(ui, "binary-file").set_input_files(str(f))
    expect(T(ui, "binary-name")).to_be_visible()
    assert send(ui)["response"]["headers"]["Content-Type"] == "image/png"


# ── GraphQL ──
def test_graphql_body_is_json_envelope(ui, echo_server):
    new_post(ui, echo_server + "/echo")
    ui.select_option("[data-testid=body-mode]", "graphql")
    expect(T(ui, "content-type-auto")).to_contain_text("application/json")
    ui.fill("[data-testid=gql-query]", "query($id: ID!) { user(id: $id) { name } }")
    ui.fill("[data-testid=gql-vars]", '{"id": 7}')
    d = send(ui)["response"]
    assert d["json"] == {"query": "query($id: ID!) { user(id: $id) { name } }", "variables": {"id": 7}}
    assert d["headers"]["Content-Type"].startswith("application/json")
    ui.fill("[data-testid=gql-vars]", "")
    assert "variables" not in send(ui)["response"]["json"]


def test_graphql_invalid_variables_reported(ui, echo_server):
    new_post(ui, echo_server + "/echo")
    ui.select_option("[data-testid=body-mode]", "graphql")
    ui.fill("[data-testid=gql-query]", "{ a }")
    ui.fill("[data-testid=gql-vars]", "{nope")
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("ERR")
    expect(T(ui, "resp-body")).to_contain_text("GraphQL Variables")


def test_graphql_and_binary_persist_in_saved_request(ui, app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "B"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "g1", "name": "Gql", "request": {"method": "POST", "header": [], "url": {"raw": echo_server + "/echo"},
                    "body": {"mode": "graphql", "graphql": {"query": "{ q }", "variables": '{"a":1}'}}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='Gql']").dblclick()
    ui.click("[data-section=body]")
    expect(T(ui, "body-mode")).to_have_value("graphql")
    assert send(ui)["response"]["json"] == {"query": "{ q }", "variables": {"a": 1}}
    ui.fill("[data-testid=gql-query]", "{ changed }")
    T(ui, "save").click()
    eventually(lambda: app.api("GET", f"/api/collections/{cid}")["item"][0]["request"]["body"]["graphql"]["query"] == "{ changed }")


# ── qator tavsifi ──
def test_row_description_saved_and_restored(ui, app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "D"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "d1", "name": "Desc", "request": {"method": "GET", "header": [{"key": "X-K", "value": "v", "description": "eski izoh"}],
                    "url": {"raw": echo_server + "/echo?p=1", "query": [{"key": "p", "value": "1"}]}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='Desc']").dblclick()
    ui.click("[data-section=headers]")
    expect(ui.locator("[data-testid=headers-table] [data-testid=kv-desc]").first).to_have_value("eski izoh")
    ui.click("[data-section=params]")
    ui.locator("[data-testid=params-table] [data-testid=kv-desc]").first.fill("sahifa raqami")
    T(ui, "save").click()
    eventually(lambda: app.api("GET", f"/api/collections/{cid}")["item"][0]["request"]["url"]["query"][0].get("description") == "sahifa raqami")
    saved = app.api("GET", f"/api/collections/{cid}")["item"][0]["request"]
    assert saved["header"][0]["description"] == "eski izoh"
    d = send(ui)["response"]
    assert d["args"] == {"p": ["1"]} and d["headers"]["X-K"] == "v"            # tavsif so'rovga ta'sir qilmaydi


# ── Bulk Edit ──
def test_bulk_edit_params_and_back_to_table(ui, echo_server):
    T(ui, "new-tab").click()
    ui.fill("[data-testid=url]", echo_server + "/echo")
    T(ui, "kv-bulk").first.click()
    ui.fill("[data-testid=params-table-bulk]", "a:1\n//b:2\nc:x:y")
    T(ui, "kv-bulk").first.click()
    inputs = ui.locator("[data-testid=params-table] input[type=text]")
    vals = [inputs.nth(i).input_value() for i in range(0, 12) if inputs.nth(i).count()]
    assert vals[0:2] == ["a", "1"] and "b" in vals and "c" in vals and "x:y" in vals
    boxes = ui.locator("[data-testid=params-table] input[type=checkbox]")
    assert [boxes.nth(i).is_checked() for i in range(3)] == [True, False, True]
    qs = parse_qs(urlsplit(T(ui, "url").input_value()).query)
    assert qs == {"a": ["1"], "c": ["x:y"]}                                       # o'chirilgan 'b' URL'da yo'q
    assert send(ui)["response"]["args"] == {"a": ["1"], "c": ["x:y"]}


def test_bulk_edit_headers_sent_and_roundtrip_text(ui, echo_server):
    T(ui, "new-tab").click()
    ui.fill("[data-testid=url]", echo_server + "/echo")
    ui.click("[data-section=headers]")
    T(ui, "kv-bulk").first.click()
    ui.fill("[data-testid=headers-table-bulk]", "X-One: 1\nX-Two:2")
    T(ui, "kv-bulk").first.click()
    T(ui, "kv-bulk").first.click()                                                 # qayta bulk: matn qatorlardan tiklanadi
    assert T(ui, "headers-table-bulk").input_value() == "X-One:1\nX-Two:2"
    T(ui, "kv-bulk").first.click()
    h = send(ui)["response"]["headers"]
    assert h["X-One"] == "1" and h["X-Two"] == "2"
