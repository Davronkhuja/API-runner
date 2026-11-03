"""Favicon, apple-touch-icon, manifest va tab sarlavhasidagi holat."""
import json
import re
import struct

import pytest
import requests
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


def png_size(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_favicon_ico_is_real_multi_size_file_with_long_cache_and_no_token(app):
    r = requests.get(app.url + "/favicon.ico")                                   # sessiya tokensiz ham ochiq
    assert r.status_code == 200
    assert "icon" in r.headers["Content-Type"]
    assert "max-age=31536000" in r.headers["Cache-Control"] and "immutable" in r.headers["Cache-Control"]
    head = r.content[:6]
    assert head[:4] == b"\x00\x00\x01\x00" and struct.unpack("<H", head[4:6])[0] == 3     # ICO, 3 ta rasm
    sizes = sorted(r.content[6 + 16 * i] for i in range(3))
    assert sizes == [16, 32, 48]


def test_apple_touch_icon_is_180_png_at_root_and_static(app):
    for path in ("/apple-touch-icon.png", "/static/app/apple-touch-icon.png"):
        r = requests.get(app.url + path)
        assert r.status_code == 200 and r.headers["Content-Type"] == "image/png"
        assert png_size(r.content) == (180, 180)


@pytest.mark.parametrize("page_path", ["/", "/legacy"])
def test_pages_declare_icons_and_every_href_resolves(app, page, page_path):
    page.goto(app.url + page_path)
    links = page.evaluate("[...document.querySelectorAll('link[rel~=icon], link[rel=apple-touch-icon], link[rel=manifest]')].map(l => ({rel: l.rel, type: l.type, sizes: l.sizes.value, href: l.href}))")
    rels = {(l["rel"], l["type"]) for l in links}
    assert ("icon", "image/svg+xml") in rels
    assert ("icon", "image/x-icon") in rels
    assert any(l["rel"] == "apple-touch-icon" and l["sizes"] == "180x180" for l in links)
    assert any(l["rel"] == "manifest" for l in links)
    for l in links:
        r = page.request.get(l["href"])
        assert r.status == 200, (l, r.status)


def test_svg_matches_the_logo_and_raster_icons_render_it(app, page):
    svg = requests.get(app.url + "/static/app/favicon.svg").text
    assert 'fill="#4F46E5"' in svg and 'rx="8"' in svg and "M17.5 5 8 18h7l-1.5 9L23 14h-7z" in svg
    page.goto(app.url)
    px = page.evaluate("""async (base) => {
      const out = {}
      for (const n of ['icon-192.png', 'icon-512.png', 'apple-touch-icon.png']) {
        const img = new Image(); img.src = base + '/static/app/' + n; await img.decode()
        const c = document.createElement('canvas'); c.width = img.width; c.height = img.height
        const g = c.getContext('2d'); g.drawImage(img, 0, 0)
        const at = (x, y) => [...g.getImageData(Math.floor(x * img.width), Math.floor(y * img.height), 1, 1).data]
        out[n] = { size: img.width, corner: at(0.005, 0.005), bg: at(0.15, 0.5), bolt: at(0.46, 0.45) }
      }
      return out }""", app.url)
    for n, size in (("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)):
        d = px[n]
        assert d["size"] == size
        assert d["bg"][:3] == [79, 70, 229] and d["bg"][3] == 255             # indigo #4F46E5
        assert d["bolt"][:3] == [255, 255, 255]                                  # oq chaqmoq
    assert px["icon-192.png"]["corner"][3] == 0 and px["icon-512.png"]["corner"][3] == 0     # yumaloq burchak shaffof
    assert px["apple-touch-icon.png"]["corner"][3] == 255                      # apple: to'liq kvadrat


def test_manifest_is_valid_and_icons_exist(app):
    m = requests.get(app.url + "/static/app/manifest.webmanifest").json()
    assert m["name"] == "API Runner" and m["display"] == "standalone" and m["theme_color"] == "#4F46E5"
    sizes = {i["sizes"] for i in m["icons"]}
    assert {"192x192", "512x512"} <= sizes
    for i in m["icons"]:
        r = requests.get(app.url + i["src"])
        assert r.status_code == 200 and i["type"] in r.headers["Content-Type"]
        if i["type"] == "image/png":
            n = int(i["sizes"].split("x")[0])
            assert png_size(r.content) == (n, n)


def test_no_404_for_icon_requests_while_loading_the_app(app, page):
    bad = []
    page.on("response", lambda r: bad.append((r.url, r.status)) if r.status >= 400 and re.search(r"icon|manifest", r.url) else None)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.request.get(app.url + "/favicon.ico")
    assert not bad


# ── tab sarlavhasida holat ──
@pytest.fixture
def ui(app, page, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "C"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": f"s{i}", "name": f"Slow{i}", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/slow?s=0.5"}}, "response": []} for i in range(3)]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def test_title_shows_runner_progress_then_resets(ui):
    assert ui.title() == "API Runner"
    ui.locator("[data-name='C']").click(button="right")
    ui.click("[data-act=runner]")
    T(ui, "runner-run").click()
    ui.wait_for_function(r"/^● Runner \d+\/3 — API Runner$/.test(document.title)")
    expect(T(ui, "runner-run")).to_be_enabled(timeout=15000)
    ui.wait_for_function("document.title === 'API Runner'")


def test_title_shows_sending_state(ui, echo_server):
    ui.locator("[data-name='Slow0']").dblclick()
    ui.fill("[data-testid=url]", echo_server + "/slow?s=1.2")
    T(ui, "send").click()
    ui.wait_for_function("document.title === '● Yuborilmoqda — API Runner'")
    expect(T(ui, "resp-status")).to_have_text("200")
    ui.wait_for_function("document.title === 'API Runner'")
