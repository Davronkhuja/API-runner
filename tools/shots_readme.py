"""docs/screenshots/README.md ni oldin/keyin skrinshotlaridan hosil qiladi:  python3 tools/shots_readme.py"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
TITLES = {
    "welcome": "Bosh sahifa (tab ochiq emas)", "editor-no-response": "So'rov muharriri — javob yo'q", "editor-params-response": "Muharrir — Params + javob",
    "editor-body": "Body (JSON) + javob", "editor-auth": "Auth (meros)", "editor-headers": "Headers", "editor-tabs-dirty-chips": "Ko'p tab, saqlanmagan nuqta, {{var}} chiplar",
    "sidebar-environments": "Yon panel — Muhitlar", "sidebar-history": "Yon panel — Tarix", "environment-tab": "Muhit tahrirlash", "runner-idle": "Runner — tayyor",
    "runner-results": "Runner — natijalar", "batch-results": "Batch natijalari", "settings": "Sozlamalar", "cookies": "Cookie Manager", "collection-settings": "Collection sozlamalari",
    "cmdk": "⌘K qidiruv", "editor-var-hover": "URL ichidagi {{var}} chip hover",
}
out = ["# Skrinshotlar: oldin / keyin\n", "Yaratish: `SHOT_PHASE=before|after python3 -m pytest tests/e2e/test_screenshots.py` (1440×900). `before` — dizayn yangilanishidan oldingi UI.\n"]
for theme in ("light", "dark"):
    out.append(f"\n## {'Yorug' if theme == 'light' else 'Qorong\'i'} tema\n")
    out.append("| Ekran | Oldin | Keyin |\n|---|---|---|")
    names = sorted({p.stem for ph in ("before", "after") for p in (ROOT / ph / theme).glob("*.png")}, key=lambda n: list(TITLES).index(n) if n in TITLES else 99)
    for n in names:
        cell = lambda ph: f"![{n}]({ph}/{theme}/{n}.png)" if (ROOT / ph / theme / f"{n}.png").exists() else "—"  # noqa: E731
        out.append(f"| {TITLES.get(n, n)} | {cell('before')} | {cell('after')} |")
(ROOT / "README.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("yozildi:", ROOT / "README.md")
