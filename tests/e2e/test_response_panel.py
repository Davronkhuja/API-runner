"""Bosqich 2 / Response paneli: Pretty/Raw/Preview, Headers, qidiruv, JSONPath, virtual scroll, Save as Example."""
import json
import re

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def send(p, url):
    T(p, "new-tab").click()
    p.fill("[data-testid=url]", url)
    T(p, "send").click()
    expect(T(p, "resp-status")).to_have_text("200")


def test_pretty_vs_raw_for_json(ui, echo_server):
    send(ui, echo_server + "/echo?a=1")
    pretty = T(ui, "resp-body").inner_text()
    assert "\n  " in pretty and ui.locator("[data-testid=resp-body] .hl-key").count() > 0
    ui.click("[data-mode=raw]")
    raw = T(ui, "resp-body").inner_text()
    assert "\n" not in raw.strip() and json.loads(raw) == json.loads(pretty)


def test_headers_tab(ui, echo_server):
    send(ui, echo_server + "/echo")
    expect(T(ui, "rp-headers-tab")).to_contain_text("Headers (")
    T(ui, "rp-headers-tab").click()
    expect(T(ui, "rp-headers")).to_contain_text(re.compile("content-type", re.I))
    T(ui, "rp-body-tab").click()
    expect(T(ui, "resp-body")).to_be_visible()


def test_search_counts_marks_and_navigates(ui, echo_server):
    send(ui, echo_server + "/echo?needle=1&needle2=2")
    T(ui, "rp-search").fill("needle")
    expect(T(ui, "rp-count")).to_have_text(re.compile(r"1 / [2-9]"))
    n = ui.locator("[data-testid=resp-body] mark").count()
    assert n >= 2
    expect(ui.locator("[data-testid=resp-body] mark.cur")).to_have_count(1)
    T(ui, "rp-next").click()
    expect(T(ui, "rp-count")).to_have_text(re.compile(r"^2 / "))
    T(ui, "rp-prev").click()
    T(ui, "rp-prev").click()                                                # aylanadi: oxirgisi
    expect(T(ui, "rp-count")).to_have_text(re.compile(rf"^{n} / {n}$"))
    T(ui, "rp-search").fill("")
    expect(ui.locator("[data-testid=resp-body] mark")).to_have_count(0)


def test_jsonpath_results_and_errors(ui, echo_server):
    send(ui, echo_server + "/echo?k=v")
    T(ui, "rp-jsonpath").fill("$.method")
    expect(T(ui, "rp-jp-count")).to_have_text("1 natija")
    assert json.loads(T(ui, "resp-body").inner_text()) == ["GET"]
    T(ui, "rp-jsonpath").fill("$.args.k[0]")
    assert json.loads(T(ui, "resp-body").inner_text()) == ["v"]
    T(ui, "rp-jsonpath").fill("$.args[")
    expect(T(ui, "rp-jp-error")).to_be_visible()
    T(ui, "rp-jsonpath").fill("")
    assert "method" in T(ui, "resp-body").inner_text()


def test_jsonpath_disabled_for_text_response(ui, echo_server):
    send(ui, echo_server + "/text")
    expect(T(ui, "rp-jsonpath")).to_be_disabled()
    expect(T(ui, "resp-body")).to_contain_text("salom dunyo")


def test_preview_for_html_only(ui, echo_server):
    send(ui, echo_server + "/html")
    ui.click("[data-mode=preview]")
    expect(ui.frame_locator("[data-testid=rp-preview]").locator("#hi")).to_have_text("Salom HTML")
    assert T(ui, "rp-preview").get_attribute("sandbox") == ""               # skriptlar bloklangan
    send(ui, echo_server + "/echo")
    expect(ui.locator("[data-mode=preview]")).to_be_disabled()


def test_virtual_scroll_for_huge_body(ui, echo_server):
    send(ui, echo_server + "/bigjson?n=5000")
    box = T(ui, "resp-body")
    expect(box).to_have_attribute("data-virtual", "true")
    assert ui.locator("[data-testid=resp-body] .vline").count() < 200        # DOM'da faqat ko'rinadigan oyna
    expect(T(ui, "rp-virtual-note")).to_contain_text("qator")
    box.evaluate("e => e.scrollTop = e.scrollHeight")
    expect(ui.locator("[data-testid=resp-body] .vline").last).to_contain_text("}")
    expect(box).to_contain_text("4999")
    T(ui, "rp-search").fill("needle")
    expect(T(ui, "rp-count")).to_have_text("1 / 1")
    expect(ui.locator("[data-testid=resp-body] mark.cur")).to_be_visible()   # qidiruv virtual ro'yxatda ham topadi va ko'rsatadi
    T(ui, "rp-search").fill("")
    T(ui, "rp-jsonpath").fill("$.items[0:3]")
    expect(T(ui, "rp-jp-count")).to_have_text("3 natija")
    expect(T(ui, "resp-body")).not_to_have_attribute("data-virtual", "true")


def test_save_as_example_persists_lists_and_loads(ui, app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Ex"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "e1", "name": "ExReq", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/echo?z=1"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='ExReq']").dblclick()
    expect(T(ui, "examples-select")).to_have_count(0)
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("200")
    T(ui, "save-example").click()
    expect(T(ui, "examples-select")).to_be_visible()
    ex = app.api("GET", f"/api/collections/{cid}")["item"][0]["response"]
    assert len(ex) == 1 and ex[0]["code"] == 200 and ex[0]["_postman_previewlanguage"] == "json"
    assert json.loads(ex[0]["body"])["args"] == {"z": ["1"]} and any(h["key"].lower() == "content-type" for h in ex[0]["header"])
    assert ex[0]["originalRequest"]["method"] == "GET"
    T(ui, "send").click()
    ui.select_option("[data-testid=examples-select]", index=1)
    expect(T(ui, "rp-example-label")).to_be_visible()
    expect(T(ui, "resp-body")).to_contain_text('"z"')


def test_save_as_example_requires_saved_request(ui, echo_server):
    send(ui, echo_server + "/echo")
    T(ui, "save-example").click()
    expect(ui.locator(".toast")).to_contain_text("saqlang")
