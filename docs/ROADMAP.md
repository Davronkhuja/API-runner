# ROADMAP — Postman darajasiga olib chiqish

Batafsil vazifa: [`AGENT_PROMPT_postman_level.md`](AGENT_PROMPT_postman_level.md).
Branch: `feature/postman-level`. Testlar: `.venv/bin/python -m pytest` (dev: `pip install -r requirements-dev.txt && playwright install chromium`).

## Bosqich 0 — Xavfsiz boshlang'ich nuqta
- [x] `feature/postman-level` branch
- [x] pytest + characterization testlar (`/run`, `/run_one`, `/saved/*`, `replace_variables`)
- [x] cURL parse characterization (brauzerda, Playwright orqali — parser frontendda)
- [x] Playwright smoke test (sahifa, GET, natija)
- [x] Multi-tab va drag&drop e2e spetsifikatsiyasi (`tests/e2e/test_*_spec.py`, hozircha skip — Bosqich 2 da yoqiladi)
- [x] `docs/ROADMAP.md`

## Bosqich 1 — Refaktor va poydevor ⛔ (tugagach to'xta, hisobot)
- [x] ADR'lar (`docs/adr/0001–0007`; 0003 httpx, 0006 frontend — **tasdiq kutilmoqda**, 0007 sandbox — ochiq)
- [x] Monolitni `apirunner/{core,storage,api}` ga bo'lish
- [x] Yagona `execute()` engine; `job_worker`/`run_one` dublikati yo'q; concurrency hisobi tuzatilgan
- [x] Ma'lumot modeli: Workspace → Collection → ichma-ich Folder → Request (+Examples), Environment, Globals
- [x] Migratsiya: `saved_requests.json` (+`.bak`), localStorage bir martalik import (⇪ tugma)
- [x] Xavfsizlik: Host/Origin tekshiruvi, session token, fayl yuklash siyosati
- [ ] Frontend yangi stackka ko'chirish boshlanishi — **tasdiqni kutadi** (UI hozircha `apirunner/static/index.html`)
- [ ] (Bosqich 2 ga qoldi) UI env/tarixni localStorage o'rniga serverdan o'qishi

## Bosqich 2 — Frontend skeleti va PARITET (tasdiqlangan shartlar: ADR 0006)
Qoidalar: eski UI `/legacy` da ishlab turadi; paritet e2e yashil bo'lgach o'chiriladi. Tab store, tree store, `order` boshidan arxitekturada. Env va tarix serverdan o'qiladi (localStorage faqat UI sozlamalari: tema, panel kengligi). Build `apirunner/static/app/` ga commit qilinadi.

### Paritet checklisti (eski UI → yangi frontend; e2e: `tests/e2e/test_parity.py`)
Belgilar: [x] bajarildi va e2e bilan qoplangan · [~] qisman / ataylab boshqacha · [ ] qilinmagan
**URL bar:** [x] method select · [x] URL input · [x] Run/Stop (Stop — Batch bo'limida) · [x] cURL paste → parse · [x] URL ↔ Params ikki tomonlama sinxron · [x] URL tarixi dropdown · [x] Save (dirty bo'lmasa disabled, Save As dialog) · [x] Copy as cURL drawer · [x] cURL sintaksis ranglash · [x] metod rangi select'da
**Tablar:** [x] Params/Headers kv + checkbox + DnD · [x] 📎 fayl yuklash + rad etilgan yo'l xabari · [x] Auth None/Bearer/Basic/Custom (+ ko'z, preview) · [x] Body JSON/Raw/Form/Multipart · [x] Beautify (+Cmd/Ctrl+B) · [x] body sintaksis ranglash va Tab tugmasi (CodeMirror 6) · [x] Content-Type avtomatik ko'rsatish
**Runner:** [x] data fayl CSV/JSON · [x] data fayl preview jadvali va drop zona (oynaga tashlash Runner tabini ochadi) · [x] rows mode · [x] delay · [x] timeout · [x] parallel · [x] retry · [x] SSL · [x] collapse (karta bo'yicha va hammasi) · [x] Postman collection runner (import + Runner tabi, ketma-ket `/run_one`) · [x] `/run` + SSE + Stop · [x] status line
**Natijalar:** [x] progress · [x] stats (+2xx/4xx/5xx) · [x] filtrlar · [x] result kartalar (badge, vaqt, hajm, retry, headers, copy) · [x] JSON sintaksis ranglash · [x] fullscreen viewer (copy, TXT) · [x] Esc bilan yopish · [x] time chart (60) · [x] export JSON/CSV · [x] run'larni solishtirish (server tarixi) · [x] resizer (editor/javob vertikal)
**Sidebar:** [x] collapse + kenglik · [x] qidiruv · [x] daraxt (ichma-ich) · [x] yangi so'rov · [x] Save modal · [x] papka yaratish/qayta nomlash/o'chirish (confirm) · [x] Move (modal va DnD) · [x] kontekst menyu · [x] inline rename (+tab sarlavhasi) · [x] duplicate (" Copy") · [x] Postman/OpenAPI import (tugma va tashlash) · [x] Environments: ro'yxat, activate, yaratish, tahrirlash (tab), o'chirish (confirm), header selector, `env_vars` · [x] eski "Default" env va yagona o'zgaruvchilar → Globals (bir martalik xabar bilan) · [x] History: ro'yxat, yuklash, o'chirish, tozalash · [x] History drawer
**Umumiy:** [x] tema · [x] yorliqlar (Cmd+Enter/S/T/W/Tab) · [x] toast · [x] confirm · [x] dirty tracking · [x] ⇪ localStorage import · [x] versiya · [x] workspace → saved_requests.json eksport tugmasi

### Skelet va arxitektura
- [x] Backend: daraxt API (`order` = `item[]` tartibi, move/copy/cycle-guard), `/api/ui-state`, server tarixi, faol env
- [x] `web/` Vite+Vue3+TS+Pinia; stores: `tabs`, `tree`, `workspace`, `history` (+`lib/batch`) · [x] CodeMirror 6 (body)
- [x] Build → `apirunner/static/app/` (commit), `/` yangi UI, `/legacy` eski
- [x] Vitest unit (32) · [x] Playwright: multi-tab 31, DnD 27, paritet 40 · [ ] eski UI'ni o'chirish (paritet [ ]/[~] bandlari yopilgach)

### Oraliq hisobot → keyin yangi funksiyalar
## Bosqich 2b — Asosiy so'rov imkoniyatlari (paritetdan keyin)
### Multi-tab (majburiy) — e2e: `tests/e2e/test_multitab_spec.py`
- [x] 31 test (`test_multitab_spec.py`) — hammasi yashil
### Sidebar va drag&drop (majburiy) — e2e: `tests/e2e/test_dnd_spec.py`
- [x] 27 test (`test_dnd_spec.py`) — hammasi yashil
### Qolganlari
- [x] Collection/folder darajasidagi Auth, Variables, Description (meros) · Scripts saqlanadi, bajarilishi Bosqich 3 (v2.1.14)
- [x] Variable scope'lar (Globals<Collection<Papka<Env), path variables, dinamik o'zgaruvchilar, secret maskalash (v2.1.13–14); Data/Local — `pm.iterationData` / `pm.variables` (v2.2.4)
- [x] Auth turlari (API Key, Digest, OAuth 2.0 [CC/Password/Code/PKCE/Implicit], AWS SigV4, JWT HS*) — v2.1.15–16; JWT RS*/ES* ochiq
- [x] Body turlari (form-data, urlencoded jadval, binary, GraphQL) — v2.2.0
- [x] Qator checkbox/tavsif/bulk edit — v2.2.0
- [x] Sozlamalar (redirect, HTTP/2, proxy, client cert, CA, SSL, cookie jar) — v2.1.18–19; SOCKS proxy ochiq
- [x] Cookie jar (SQLite) + Cookie Manager + Response Cookies tabi — v2.1.18–19
- [x] Response paneli (Pretty/Raw/Preview, Headers, qidiruv, JSONPath, virtual scroll, Save as Example) — v2.1.17; Cookies/Test natijalari tablari keyingi bandlarda
- [x] Code snippet generatori (9 til) — v2.2.0
- [x] Server tomonda tarix (SQLite; v2.1.x)

## Bosqich 3 — Skriptlar va testlar
- [x] Pre-request / Tests skriptlari (meros tartibida), `pm.*` API, kutubxonalar — v2.2.4 (ADR 0007: quickjs-ng)
- [x] Avtoto'ldirish, snippet'lar, Postman skriptlari o'zgarishsiz (real namunalar bilan testlangan) — v2.3.0
- [x] **Console paneli** (status bardan ochiladi: so'rov/javob loglari, `console.log`, skript xatolari) — v2.3.0

## Bosqich 4 — Collection Runner v2
- [ ] Runner sozlamalari, batch integratsiyasi, real-time SSE, SQLite, eksport (JSON/HTML/JUnit), solishtirish
- [ ] **Runner (dizayn maketidan qolganlari)**: parallel so'rovlar, "o'zgaruvchi qiymatlarini saqlash", "javoblarni saqlash", natijalar jadvalida **Testlar** ustuni (Bosqich 3 test natijalariga bog'liq), run raqami/tarixi sarlavhasi (`run #14`), "avvalgi run bilan solishtirish" va "Eksport" tugmalari Runner sahifasida

## Bosqich 4b — Kundalik qulayliklar (Bosqich 4 dan keyin bajariladi)
- [ ] Muhit o'zgaruvchilarida **Initial / Current** qiymatlar (eksportga faqat Initial ketadi); headerdagi "ko'z" quick-look (faol muhit + global qiymatlarni tez ko'rish va tahrirlash)
- [ ] **`{{` avtoto'ldirish** (URL, params, headers, body, auth maydonlarida; scope va qiymat ko'rsatiladi) va belgilangan matndan o'zgaruvchi yaratish ("Set as variable")
- [ ] **Example'lar ro'yxati** daraxtda so'rov ostida; ochish va tahrirlash (status, header, body)
- [ ] **Docs paneli**: Markdown tavsif so'rov o'ng tomonida (collection/papka/so'rov)
- [ ] **Trash**: o'chirilganlarni 30 kun saqlash va tiklash
- [ ] **Workspace bo'ylab Find & Replace** (oldindan ko'rish va avtomatik zaxira bilan)
- [ ] **So'rov javoblari tarixi** va ikki javobni solishtirish (diff)
- [ ] **"Send and Download"** (javobni faylga saqlab yuborish)
- [ ] Auth: **JWT RS\*/ES\*** (`cryptography` bilan), **NTLM**, **Hawk**

## Bosqich 5 — Import/Export
- [ ] Postman v2.0/2.1, env/globals, OpenAPI/Swagger, Insomnia, HAR, cURL; export; round-trip testlar

## Bosqich 6 — Boshqa protokollar
- [ ] GraphQL, WebSocket, SSE, Socket.IO (ixtiyoriy), gRPC (ixtiyoriy)

## Bosqich 7 — Kengaytirilgan imkoniyatlar
- [ ] CLI, mock server, hujjatlar generatsiyasi, paketlash
- [ ] **Rejalashtirilgan run'lar (monitor)**: collection'ni jadval bo'yicha avtomatik ishga tushirish, natijalar tarixi va xato haqida ogohlantirish
- [ ] **Proxy capture**: lokal proxy orqali o'tgan trafikni so'rov sifatida yozib olish va collection'ga saqlash
- [x] Cmd+K qidiruv palitrasi (v2.2.1)
- [ ] **Workspace almashtirgich** (header'dagi "Shaxsiy workspace" hozir oddiy matn; bir nechta workspace yaratish/almashtirish)

## Dizayn va yorliqlar (v2.2.1–2.2.2)
- [x] Yangi dizayn tizimi (`docs/design/*.dc.html` maketlari, tokenlar, lokal shriftlar, ⌘K, bosh sahifa, Runner maketi)
- [x] Import va Runner — ⌘K palitrasida (maketdagi ⌘O/⌘R, shuningdek ⌘⇧O/⌘⇧R Chrome'da "fayl ochish", "hard reload" va "bookmark manager" bilan to'qnashgani uchun yorliq berilmadi; v2.2.3)
- [x] Favikon (SVG + ICO 16/32/48 + apple-touch-icon + 192/512 + manifest), tab sarlavhasida holat (v2.2.3)

## Bosqich 8 — Sayqal va sifat
- [ ] Ishlash tezligi, UX, hujjatlar

## Ma'lumotlar xavfsizligi (doimiy qoida, v2.1.6)
- [x] Testlar faqat tmp (APIRUNNER_TESTING himoyasi) · [x] avtomatik zaxira (20 ta) · [x] schemaVersion + idempotent migratsiya + sonlar tekshiruvi + rollback · [x] atomik yozuv · [x] SQLite WAL · [x] qulf va rev (409) · [x] localStorage o'chirilmaydi, dublikatsiz import · [x] tiklash (UI + CLI) · [x] anonimlashtirilgan fixture testi
