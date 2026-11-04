"""Dizayn tokenlari: har ikki temada matn kontrasti WCAG AA (≥4.5:1), komponentlar faqat tokenlardan foydalanadi."""
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "web" / "src"
TOKENS = (WEB / "styles" / "tokens.css").read_text(encoding="utf-8")


def block(selector_re):
    m = re.search(selector_re + r"\s*\{(.*?)\n\}", TOKENS, re.S)
    assert m, selector_re
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", m.group(1)))


ROOT = dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", re.search(r":root\s*\{(.*?)\n\}", TOKENS, re.S).group(1)))
LIGHT = {**ROOT, **block(r":root,\n\.th-light")}
DARK = {**ROOT, **block(r"\.th-dark")}


def lum(h):
    r, g, b = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + .05) / (lo + .05)


SURFACES = ("bg", "panel", "rail", "subtle", "hover", "code")
TEXT_ON_SURFACES = ("text", "muted", "accent-text", "m-get", "m-post", "m-put", "m-patch", "m-delete", "ok", "err", "var")
PAIRS = (
    [(t, s) for t in ("text", "muted") for s in SURFACES]
    + [(t, s) for t in ("accent-text", "env-dev", "env-test", "m-get", "m-post", "m-put", "m-patch", "m-delete", "ok", "err") for s in ("panel", "bg", "subtle", "hover", "accent-weak")]
    + [(t, "code") for t in ("j-key", "j-str", "j-num", "j-bool", "j-punc", "text", "muted")]
    + [("ok", "ok-bg"), ("err", "err-bg"), ("var", "var-bg"), ("accent-text", "accent-weak"), ("on-accent", "accent"), ("mark-text", "mark"), ("mark-text", "mark-cur"), ("muted", "accent-weak"), ("text", "sel"), ("env-prod", "env-prod-bg"), ("env-prod", "panel"), ("env-prod", "bg"), ("env-prod", "subtle"), ("panel", "env-prod")]
)


@pytest.mark.parametrize("theme,t", [("light", LIGHT), ("dark", DARK)])
def test_text_contrast_is_wcag_aa(theme, t):
    bad = [(fg, bg, round(ratio(t[fg], t[bg]), 2)) for fg, bg in PAIRS if ratio(t[fg], t[bg]) < 4.5]
    assert not bad, f"{theme}: kontrast < 4.5 → {bad}"


@pytest.mark.parametrize("theme,t", [("light", LIGHT), ("dark", DARK)])
def test_focus_ring_and_borders_meet_3_to_1(theme, t):
    assert ratio(t["focus"], t["panel"]) >= 3 and ratio(t["focus"], t["bg"]) >= 3


def test_both_themes_define_the_same_tokens():
    assert set(block(r":root,\n\.th-light")) == set(block(r"\.th-dark"))


def test_design_tokens_present():
    for k in ("m-get", "m-post", "m-put", "m-patch", "m-delete", "j-key", "j-str", "j-num", "j-bool", "ok", "err", "var", "accent-weak", "code"):
        assert k in LIGHT and k in DARK


def test_components_use_only_defined_tokens():
    defined = set(re.findall(r"--([\w-]+)\s*:", TOKENS))     # hex bo'lmaganlar (shrift, o'lcham, soya) ham
    used = set()
    for f in list(WEB.rglob("*.vue")) + list(WEB.rglob("*.ts")) + [WEB / "style.css"]:
        if f.name.endswith(".test.ts"):
            continue
        used |= set(re.findall(r"var\(--([\w-]+)\)", f.read_text(encoding="utf-8")))
    assert not (used - defined), f"aniqlanmagan o'zgaruvchilar: {sorted(used - defined)}"


def test_no_hardcoded_colors_outside_tokens():
    offenders = {}
    for f in list(WEB.rglob("*.vue")) + [WEB / "style.css"]:
        txt = f.read_text(encoding="utf-8")
        hits = re.findall(r"(?<![&\w])#[0-9a-fA-F]{3,8}\b|rgba?\(", txt)
        hits = [h for h in hits if not re.fullmatch(r"#\d+", h)]
        if hits:
            offenders[f.name] = hits[:5]
    # istisnolar: javob Preview iframe oq fon (begona sahifa); kartochka hover soyasi
    offenders.pop("style.css", None)
    assert not offenders, offenders


def test_fonts_are_bundled_locally():
    css = (WEB / "styles" / "fonts.css").read_text(encoding="utf-8")
    assert "http" not in css and "fonts.googleapis" not in css and "Inter Variable" in css and "JetBrains Mono Variable" in css
    for f in re.findall(r"url\(([^)]+\.woff2)\)", css):
        assert (WEB / "styles" / f).resolve().exists(), f
