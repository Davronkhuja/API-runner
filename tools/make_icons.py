"""web/public/favicon.svg dan favicon.ico (16/32/48), apple-touch-icon.png (180), icon-192.png, icon-512.png hosil qiladi.

Natija repoga commit qilinadi (Node'siz ishga tushish buzilmasin). Qayta yaratish: .venv/bin/python tools/make_icons.py
Rasterlash Playwright (Chromium) bilan; ICO — PNG ichiga o'ralgan standart format (stdlib).
"""
import struct
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PUB = Path(__file__).resolve().parents[1] / "web" / "public"
SVG = (PUB / "favicon.svg").read_text(encoding="utf-8")
FULL_BLEED = SVG.replace(' rx="8"', "")          # apple-touch-icon: iOS o'zi yumaloqlaydi, shaffof joy qora bo'lib qolmasin


def render(page, svg, size):
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(f"<style>html,body{{margin:0;background:transparent}}svg{{display:block;width:{size}px;height:{size}px}}</style>{svg}")
    return page.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": size, "height": size})


def ico(pngs):
    """pngs: [(size, bytes)] → ICO (PNG-in-ICO)."""
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset, entries, data = 6 + 16 * len(pngs), b"", b""
    for size, png in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset + len(data))
        data += png
    return head + entries + data


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(device_scale_factor=1)
        (PUB / "icon-192.png").write_bytes(render(page, SVG, 192))
        (PUB / "icon-512.png").write_bytes(render(page, SVG, 512))
        (PUB / "apple-touch-icon.png").write_bytes(render(page, FULL_BLEED, 180))
        (PUB / "favicon.ico").write_bytes(ico([(s, render(page, SVG, s)) for s in (16, 32, 48)]))
        b.close()
    print("yozildi:", ", ".join(sorted(f.name for f in PUB.iterdir())))


if __name__ == "__main__":
    sys.exit(main())
