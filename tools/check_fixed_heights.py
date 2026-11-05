#!/usr/bin/env python3
"""Qat'iy `height: NNNpx` lint: kontent konteynerlari (>56px) uchun taqiqlangan — flex / min-height / viewport birliklaridan foydalaning.

≤56px — boshqaruv elementlari (tugma, input, qator, ikonka, nuqta, progress): ruxsat. Katta qiymat zarur bo'lsa, `tools/fixed_heights_allow.txt` ga
`fayl :: selektor-yoki-parcha   # sabab` qatori qo'shing. Ishlatish: python3 tools/check_fixed_heights.py (xato bo'lsa chiqish kodi 1).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "src"
ALLOW = ROOT / "tools" / "fixed_heights_allow.txt"
LIMIT = 56
PAT = re.compile(r"(?<![\w-])height\s*:\s*(\d+)px")


def allowlist():
    out = []
    if ALLOW.exists():
        for line in ALLOW.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if "::" in line:
                f, frag = (x.strip() for x in line.split("::", 1))
                out.append((f, frag))
    return out


def scan():
    bad = []
    allow = allowlist()
    for path in sorted(SRC.rglob("*")):
        if path.suffix not in (".css", ".vue") or "node_modules" in path.parts:
            continue
        rel = str(path.relative_to(SRC))
        text = path.read_text(encoding="utf-8")
        for m in PAT.finditer(text):
            px = int(m.group(1))
            if px <= LIMIT:
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            ctx_start = text.rfind("\n", 0, m.start()) + 1
            ctx = text[max(0, text.rfind("}", 0, m.start()) + 1): m.end()].strip().replace("\n", " ")[:160] or text[ctx_start: m.end()]
            if any(f == rel and frag in ctx for f, frag in allow):
                continue
            bad.append(f"{rel}:{line_no}: height:{px}px  ← {ctx[-110:]}")
    return bad


if __name__ == "__main__":
    bad = scan()
    for b in bad:
        print("QAT'IY BALANDLIK:", b)
    if bad:
        print(f"\n{len(bad)} ta: kontent konteyneri uchun flex/min-height/vh ishlating, yoki tools/fixed_heights_allow.txt ga sabab bilan qo'shing.")
    sys.exit(1 if bad else 0)
