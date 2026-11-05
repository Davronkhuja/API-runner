#!/usr/bin/env python3
"""findings.json (tools/ui_audit.py) -> docs/ui-audit.md jadvali: ID | ekran | holat | nima noto'g'ri | og'irlik | skrinshot | status.

Ishlatish: python3 tools/ui_audit_report.py /tmp/ui-audit [--closed docs/ui-audit-closed.json] > docs/ui-audit.md
Qo'lda kiritilgan qatorlar (MANUAL) — foydalanuvchi/reviewer Chrome'da tasdiqlagan muammolar va skrinshotni ko'zdan kechirish topilmalari.
"""
import collections
import json
import re
import sys
from pathlib import Path

SEV = {"overlay-outside-viewport": "bloklaydi", "page-hscroll": "xalaqit beradi", "clipped-text": "xalaqit beradi", "editor-dead-space": "xalaqit beradi", "editor-too-short": "xalaqit beradi",
       "small-target": "kosmetik", "scenario-error": "xalaqit beradi"}
WHAT = {"overlay-outside-viewport": "Dialog/popover viewport'dan oshib ketadi", "page-hscroll": "Sahifada gorizontal scroll", "clipped-text": "Matn kesilgan (overflow:hidden, ellipsis yo'q)",
        "small-target": "Interaktiv element 24px dan kichik", "editor-dead-space": "Muharrir ostida o'lik bo'sh joy", "editor-too-short": "Muharrir juda past", "scenario-error": "Ssenariy bajarilmadi (UI elementi topilmadi/xato)"}
MANUAL = [
    ("A1", "Kod dialogi (uzun body)", "default", "`<pre>` cheklanmasdan o'sadi; dialog ekrandan oshadi, sarlavha/Nusxa/× ko'rinmaydi (.dialog da max-height yo'q)", "bloklaydi", "dlg-code-long"),
    ("A2", "Kod dialogi", "default", "640px tor; oddiy `<pre>` — qator raqami va ranglash yo'q", "xalaqit beradi", "dlg-code-long"),
    ("A3", "Import", "default", "Tugma faqat OS fayl tanlash oynasini ochadi: sudrash/matn/URL/oldindan ko'rish yo'q", "xalaqit beradi", "welcome"),
    ("A4", "Muhit \"ko'z\" tugmasi", "click", "To'liq Globals tabini ochadi; Postman'dagidek tezkor popover yo'q", "xalaqit beradi", "env-eye"),
    ("B5", "Body/GraphQL/Skript muharrirlari", "default", "Qat'iy 220px; ostida o'lik bo'sh joy", "xalaqit beradi", "heavy-body"),
    ("B6", "Body/Skript/Javob muharrirlari", "default", "Qator raqamlari, fold, qavs moslashtirish, ⌘F qidiruv yo'q (body'da)", "xalaqit beradi", "heavy-body"),
    ("B7", "Body JSON", "xato JSON", "Xato qatori belgilanmaydi; Beautify xabarida qator raqami yo'q", "xalaqit beradi", "heavy-body"),
    ("B8", "Skriptlar tabi", "default", "Muharrir past, snippetlar ro'yxati juda mayda", "xalaqit beradi", "heavy-scripts"),
    ("B9", "Body", "default", "Content-Type ham input'da, ham matnda (takror)", "kosmetik", "heavy-body"),
    ("C10", "Javob paneli", "yangilashdan keyin", "Javob matni saqlanmaydi (\"Javob saqlanmagan\")", "bloklaydi", "resp-400"),
    ("C11", "Javob tablari", "Body/Headers/Cookies/Testlar", "Tablar o'rtasida toolbar joylashuvi har xil — kontent sakraydi", "kosmetik", "resp-headers-tab"),
    ("C12", "Javob Headers tabi", "default", "Qidiruv, nusxa olish yo'q; ustun kengligi o'zgaruvchan; uzun qiymatlar o'ralmaydi", "xalaqit beradi", "resp-headers-tab"),
    ("C13", "Javob toolbar", "Headers/Cookies/Testlar", "Pretty/Raw/Preview faqat Body'da bo'lishi kerak", "kosmetik", "resp-headers-tab"),
    ("D14", "Batch/Runner formasi", "default", "Input'lar 1/3 kenglikka cho'zilgan, RUN o'ng chetda yolg'iz", "xalaqit beradi", "heavy-batch"),
    ("D15", "Sozlamalar", "default", "Har bo'limda alohida Saqlash; chap navigatsiya yo'q; matn ustuni cheklanmagan", "xalaqit beradi", "settings"),
    ("D16", "Resizer", "hover", "Ushlash zonasi ingichka, hover'da yo'g'onlashmaydi — birinchi urinishda ilinmaydi", "xalaqit beradi", "editor-simple-response"),
    ("D17", "Tablar", "30 ta ochiq tab", "Gorizontal scroll/∨ ro'yxat va faol tabni ko'rinadigan joyga scroll qilish tekshirilsin", "xalaqit beradi", "tabs-30"),
    ("D18", "Sidebar Tarix", "default", "To'liq URL'lar ro'yxati: status, vaqt, guruhlash yo'q (Tarix oynasi bilan har xil komponent)", "xalaqit beradi", "sidebar-history"),
    ("D19", "Nomlar", "URL nomli so'rovlar", "Nomi to'liq URL bo'lib qolgan so'rovlar uchun tozalash taklifi yo'q", "xalaqit beradi", "long-name-request"),
    ("E20", "Dizayn tizimi", "—", "Ikonka-tugma/radius/bo'shliq/shrift o'lchamlari tokenlarga yig'ilmagan", "kosmetik", "settings"),
    ("E21", "Holat naqshlari", "bo'sh/xato/yuklanish", "Bo'sh, xato va yuklanish holatlari har joyda har xil", "kosmetik", "resp-204"),
    ("E22", "Dark rejim", "jadvallar/dialoglar/popover", "Oq fon qolib ketmasligi va kontrast ≥4.5:1 tizimli tekshirilmagan", "xalaqit beradi", "env-tab"),
]


def norm(detail):
    d = re.sub(r"\d+px|\d+x\d+|\(\d+,-?\d+,\d+,-?\d+\)|viewport \d+x\d+|rect\([^)]*\)|×\d+|\(×\d+\)|data-tab=\"[^\"]*\"|:nth-child\(\d+\)|ID\d+", "#", detail)
    return re.sub(r"\s+", " ", d).strip()[:140]


def main():
    out = Path(sys.argv[1])
    closed = {}
    if "--closed" in sys.argv:
        closed = json.loads(Path(sys.argv[sys.argv.index("--closed") + 1]).read_text())
    f = [x for x in json.loads((out / "findings.json").read_text()) if "url-editor" not in x.get("detail", "")]
    groups = collections.OrderedDict()
    for x in f:
        kind = x["kind"]
        key = (kind, norm(x["detail"]))
        g = groups.setdefault(key, {"screens": collections.Counter(), "combos": set(), "shot": x.get("shot", ""), "detail": x["detail"]})
        g["screens"][x["screen"]] += 1
        g["combos"].add(f'{x["viewport"]}/{x["theme"]}')
    rows = []
    n = 0
    for (kind, _), g in sorted(groups.items(), key=lambda kv: ({"bloklaydi": 0, "xalaqit beradi": 1, "kosmetik": 2}[SEV.get(kv[0][0], "xalaqit beradi" if kv[0][0].startswith("axe-") else "kosmetik")], kv[0])):
        n += 1
        sev = SEV.get(kind) or ("xalaqit beradi" if kind.startswith("axe-") else "kosmetik")
        if kind.startswith("axe-") and "critical" in g["detail"]:
            sev = "bloklaydi"
        what = WHAT.get(kind) or f"a11y (axe): {kind[4:]}"
        scr = ", ".join(f"{s}" for s, _ in g["screens"].most_common(3)) + (f" (+{len(g['screens']) - 3})" if len(g["screens"]) > 3 else "")
        rows.append((f"AUD-{n:03d}", scr, f"{len(g['combos'])} kombinatsiya", f"{what}: `{g['detail'][:110]}`", sev, g["shot"]))
    print("# UI audit\n")
    print(f"Avtomatik audit (`tools/ui_audit.py`): 5 oyna (1280×800, 1440×900, 1920×1080, 1440×900@80%, @125%) × light/dark × {len({x['screen'] for x in f} | {m[5] for m in MANUAL})}+ ekran/holat. "
          "Detektorlar: dialog viewport'dan oshishi, sahifa gorizontal scroll, kesilgan matn, <24px nishon, muharrir ostida bo'sh joy, axe (serious/critical). Qo'lda tasdiqlanganlar (MAN) va skrinshotlarni ko'zdan kechirish topilmalari alohida.\n")
    sev_count = collections.Counter(r[4] for r in rows) + collections.Counter(m[4] for m in MANUAL)
    print("Jami:", ", ".join(f"{k}: {v}" for k, v in sev_count.items()), "\n")
    print("| ID | ekran | holat | nima noto'g'ri | og'irlik | oldin | status (commit · keyin) |\n|---|---|---|---|---|---|---|")
    def link(rel, phase):
        return f"docs/screenshots/audit/{phase}/{rel}.jpg"

    def cell(i, rel):
        before = f"[oldin]({link(rel, 'before')})"
        st = closed.get(i)
        return before, (f"{st} · [keyin]({link(rel, 'after')})" if st else "**ochiq**")
    for (mid, scr, state, what, sev, shot) in MANUAL:
        rel = f"1440x900-light/{shot}"
        b, st = cell(mid, rel)
        print(f"| {mid} | {scr} | {state} | {what} | {sev} | {b} | {st} |")
    for r in rows:
        rel = (r[5] or "").replace("shots/", "", 1).removesuffix(".png")
        b, st = cell(r[0], rel) if rel else ("—", closed.get(r[0], "**ochiq**"))
        print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {b} | {st} |")


if __name__ == "__main__":
    main()
