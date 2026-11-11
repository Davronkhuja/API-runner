# ADR 0010 — CLI, mock, hujjatlar, workspace'lar, monitor, proxy (Bosqich 7)

**Holat:** Qabul qilingan

## Qaror
- **CLI mavjud RunManager'ni qayta ishlatadi** (`cli.py`, `core/planner.py`): UI'dagi reja (`plan`) Python'da quriladi, vaqtinchalik `Workspace`+SQLite ichida yuriladi — foydalanuvchi ma'lumotiga tegmaydi, UI bilan bir xil dvigatel (skriptlar, auth, cookie). Hisobotlar `core/reporters.py` (JUnit/HTML UI bilan umumiy). Exit code: 0 / 1 (xato) / 2 (argument).
- **Mock server** (`mock.py`) — Flask + werkzeug, alohida portda, Example'lardan yo'nalishlar; statik yo'l parametrli yo'ldan ustun. `MockManager` ilova darajasida, workspace almashganda to'xtatiladi.
- **Hujjat** (`docs_gen.py`) — bitta o'z-o'zidan yetarli HTML (CSS ichida), tashqi resursiz.
- **Workspace'lar:** `workspaces.json` reestri + har biri alohida papka; `bind_workspace()` workspace'ga bog'liq hamma narsani (storage, DB, cookie, run/job menejerlari, savat, monitor ro'yxati) qayta quradi. O'chirish — Savat (`kind=workspace`), papka 30 kun saqlanadi. Almashtirishda faol run/mock/ulanish bo'lsa tasdiq (`force`).
- **Monitor** (`monitor.py`): o'z cron tahlilchisi (5 maydon, dom/dow OR semantikasi), `Scheduler` oqimi har 15 s tekshiradi, bir daqiqada bir marta, yurayotganini qayta boshlamaydi; natija `RunManager` orqali `kind=monitor` bilan run tarixiga. Ro'yxat — `workspace/monitors.json`. Cheklov: ilova ishlab turganda ishlaydi (PM2 bilan doimiy). Bildirishnoma — `osascript` (testda o'chiq).
- **Proxy capture** (`proxy.py`): stdlib `ThreadingHTTPServer`; HTTP so'rovlar `httpx` bilan uzatiladi va yoziladi; HTTPS `CONNECT` — ko'r tunnel (MITM sertifikat qo'ymaymiz: xavfsizlik va murakkablik). Saqlash — collection ichida yangi papka.
- **GraphQL sxema keshi** diskda (`storage/schema_cache.py`) — qayta yaratiladigan kesh; hard-delete testi uchun fayl o'chirish storage qatlamida.
