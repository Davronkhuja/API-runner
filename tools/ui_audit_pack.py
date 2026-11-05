#!/usr/bin/env python3
"""Hisobotda havola qilingan skrinshotlarni JPEG sifatida docs/screenshots/audit/<phase>/ ga ko'chiradi.

Ishlatish: python3 tools/ui_audit_pack.py <audit_dir> <before|after>   (audit_dir/findings.json + shots/ bo'lishi kerak)
"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))

root = Path(__file__).resolve().parents[1]
src, phase = Path(sys.argv[1]), sys.argv[2]
import re
md = (root / "docs" / "ui-audit.md").read_text(encoding="utf-8")
rels = set(re.findall(r"docs/screenshots/audit/(?:before|after)/([^)]+?)\.jpg", md))      # faqat hisobotda havola qilinganlar
n = 0
for rel in sorted(rels):
    f = src / "shots" / f"{rel}.png"
    if not f.exists():
        continue
    dst = root / "docs" / "screenshots" / "audit" / phase / f"{rel}.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(f).convert("RGB").save(dst, "JPEG", quality=78, optimize=True)
    n += 1
print(f"{n} ta skrinshot → docs/screenshots/audit/{phase}/")
