# ADR 0007 — Skript sandbox (`pm.*`)

**Holat:** Ochiq — Bosqich 3 boshida spike bilan hal qilinadi

Variantlar: (A) Python `quickjs` — jarayon ichida, fayl/tarmoq sukut bo'yicha yo'q, xotira/vaqt limiti bor, lekin chai/lodash/CryptoJS bundle'larini yuklash va Python 3.14 wheel mavjudligi tekshirilishi kerak. (B) Node sidecar — to'liq V8 va npm kutubxonalari, lekin Node bog'liqligi (`run.command` Node'siz ishlashi talabiga zid) va sandbox uchun `vm`/`isolated-vm` murakkabligi.
Bosqich 1 da hech narsa tanlanmadi; `engine.execute` ga pre/post hook nuqtalari Bosqich 3 da qo'shiladi.
