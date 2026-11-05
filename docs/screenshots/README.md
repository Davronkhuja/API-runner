# Skrinshotlar

Repoda **faqat vizual regressiya baseline'lari** saqlanadi: `docs/screenshots/baseline/<light|dark>/*.png` (1440×900). Qolgan skrinshotlar (`before/`, `after/`, `qa/`, `audit/`) `.gitignore` da — kerak bo'lsa qayta yaratiladi:

| Nima | Qanday |
|---|---|
| Vizual regressiya baseline | `UPDATE_BASELINE=1 .venv/bin/python -m pytest tests/e2e/test_visual_regression.py` (faqat dizayn ataylab o'zgargach) |
| Ekranlar galereyasi (`after/`, light/dark) | `SHOT_UPDATE=1 .venv/bin/python -m pytest tests/e2e/test_screenshots.py` → `docs/screenshots/after/` |
| QA ssenariylar (1440×900 va 1920×1080) | `QA_SHOT_DIR=docs/screenshots/qa/<versiya> .venv/bin/python -m pytest tests/e2e/test_qa_scenarios.py` |
| To'liq UI audit matritsasi | `.venv/bin/python tools/ui_audit.py --out /tmp/ui-audit` → `tools/ui_audit_report.py /tmp/ui-audit > docs/ui-audit.md` → `tools/ui_audit_pack.py /tmp/ui-audit after` (JPEG, `docs/screenshots/audit/after/`) |

`before/` (eski dizayn, v2.1 dan oldingi UI) endi qayta yaratilmaydi — eski UI kodi yo'q; u git tarixida (`git log -- docs/screenshots/before`) qolgan.
