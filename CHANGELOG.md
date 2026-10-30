# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/). Versiyalash: SemVer (bosqich tugashi = MINOR, bosqich ichidagi funksiya/tuzatish = PATCH). Yagona manba: `apirunner/__init__.py`.

## [2.1.14] — 2026-10-30 — Bosqich 2 (1/5: sozlamalar va scope'lar)
### Added
- Collection va papka sozlamalari tabi (collection: ikki marta bosish; papka: kontekst menyu → "Sozlamalar"): Auth, Variables, Scripts (saqlanadi, bajarilishi Bosqich 3), Tavsif. Saqlash `PUT /api/collections` / `PATCH items`.
- Auth merosi: so'rov `Meros (Inherit)` (yangi so'rovlar uchun sukut, Postman kabi) → eng yaqin papka → collection; `Auth yo'q` (`noauth`) zanjirni to'xtatadi. `AuthEditor` komponenti, `lib/auth.ts`.
- Scope'li o'zgaruvchilar (past → yuqori): Globals < Collection < Papka(lar) < Environment (< Data < Local bajarilishda). Single send, Batch va Collection Runner shu zanjirdan foydalanadi (`lib/scope.ts`).
- O'zgaruvchi chiplari so'rov ostida: hoverda scope va qiymat, aniqlanmagani qizil, `{{$guid}}` dinamik; secret qiymat hoverda va jadvalda maskalanadi.
- Globals tahrirlash (Muhit → 🌐 Globals).
- Path variables jadvali (Params tabi): URL'dagi `:id` avtomatik topiladi, qiymat saqlanadi (`url.variable`).
- 10 e2e (`test_scopes.py`) va 5 unit test.
### Changed
- Yangi so'rovlar auth'i `inherit` (avval `none`); `noauth` Postman formatida aniq saqlanadi. Auth yo'q so'rovlar meros oladi.
- Postman elementida `query` yo'q, lekin URL'da `?` bo'lsa, parametrlar URL'dan olinadi.
- Dinamik o'zgaruvchilar, ichma-ich `{{}}` va path variables (v2.1.13 backend) endi UI bilan ishlaydi.

## [2.1.13] — 2026-10-30 — Bosqich 2 (1/5, backend)
### Added
- Dinamik o'zgaruvchilar: `{{$guid}}`, `{{$randomUUID}}`, `{{$timestamp}}`, `{{$isoTimestamp}}`, `{{$randomInt}}`, `{{$randomBoolean}}`, `{{$randomAlphaNumeric}}`, `{{$randomFirstName}}`, `{{$randomLastName}}`, `{{$randomEmail}}` (har chaqiruvda yangi; foydalanuvchi o'zgaruvchisi ustun).
- Path variables: `spec.path_variables` → URL yo'lidagi `:id` (query, port va sxema tegilmaydi).
### Changed
- Ichma-ich `{{a}}` → `{{b}}` yechiladi (5 o'tishgacha, aylanma bog'lanish tsiklga olib kelmaydi).

## [2.1.12] — 2026-10-30
### Added
- `ecosystem.config.js`: PM2 ilovasi `api-runner` (`.venv` interpreteri, `cwd`, `APIRUNNER_PORT`, `APIRUNNER_NO_BROWSER=1`). README'ga "PM2 bilan doimiy ishga tushirish" bo'limi.
### Changed
- `run.command` PM2 ostidagi `api-runner` ni taniydi: port shu jarayonda band bo'lsa to'xtatmaydi, `pm2 restart api-runner` ni taklif qiladi (TTY bo'lmasa faqat buyruqni chiqaradi). 2 yangi test (soxta `pm2`, pty).

## [2.1.11] — 2026-10-30
### Added
- Paritet: Body muharriri CodeMirror 6 ga ko'chdi (`CodeEditor.vue`): JSON sintaksis ranglash (tema o'zgaruvchilari — yorug/qorong'i), undo/redo, Tab = kursor o'rniga 2 probel (eski UI kabi), Shift+Tab chekinishni kamaytiradi, Cmd/Ctrl+B Beautify.
- 3 yangi e2e test (Tab, ranglash, tab almashganda qiymat saqlanishi).
### Changed
- Body maydoni endi `contenteditable`: mavjud e2e testlar `to_have_value` o'rniga matn bo'yicha tekshiradi. Bundle ~158 KB → ~464 KB (CodeMirror).
- `@codemirror/language`, `@lezer/highlight` aniq bog'liqlik sifatida qo'shildi.

## [2.1.10] — 2026-10-30
### Added
- Paritet: History drawer (🕘 sarlavhada) — so'rovlar tarixi o'ng tomondan ochiladi, yozuv bosilsa yangi tabda yuklanadi, Tozalash/o'chirish, backdrop va Esc bilan yopiladi. Sidebar tarixi bilan yagona `openFromHistory`.
- Natija kartalarini alohida yig'ish (▾/▸) va "hammasini yig'ish/yoyish" (⇅). Eski "collapse" xulq-atvori (kartalar) tiklandi.
- 2 yangi paritet e2e testi.

## [2.1.9] — 2026-10-30
### Added
- Paritet: JSON sintaksis ranglash (javob, natija kartalari, fullscreen), cURL drawer ranglash (`lib/highlight.ts`, escape + 200 KB chegara), metod rangi select'da, Content-Type avtomatik ko'rsatish (JSON/form/multipart), data fayl preview jadvali (`DataPreview`, dastlabki 5 qator) va drop zona (Batch va Runner), editor/javob vertikal ajratgichi.
- 7 yangi paritet e2e testi va `highlight` unit testlari.
### Fixed
- Esc fullscreen/solishtirish/cURL oynasini fokusdan qat'i nazar yopadi.
- Oynaga CSV tashlash Runner tabini ochadi va sarlavhali (ob'ektli) qatorlar bilan to'ldiradi; massiv JSON ham data fayl sifatida qabul qilinadi (Postman collection import saqlanadi).
### Changed
- CSV/JSON o'qish `lib/datafile.ts` ga birlashtirildi (Batch/Runner/App takrorlanishi olib tashlandi).

## [2.1.8] — 2026-10-30
### Changed
- `run.command` qayta yozildi: loyiha `.venv` (yo'q bo'lsa yaratiladi), pip xatolari ko'rinadi va oyna Enter'gacha yopilmaydi, `requirements.txt` o'zgarmagan bo'lsa pip o'tkazib yuboriladi (oflayn ishlaydi), `API RUNNER v2.x.y` chiqadi, port bandligi: o'z eski jarayonimiz to'xtatiladi, boshqa dastur o'ldirilmaydi.
- Server banneri versiyani ko'rsatadi. README o'rnatish bo'limi yangilandi.

## [2.1.7] — 2026-10-30
### Fixed
- Tab holati debounce tufayli yo'qolishi: o'zgarishdan keyin 0.3 s ichida sahifa yangilansa/yopilsa oxirgi o'zgarish yo'qolardi. Endi `pagehide`/`beforeunload`/`visibilitychange(hidden)` da kutilayotgan yozuv `fetch keepalive` bilan darhol yuboriladi; tab almashtirish/ochish/yopish/qayta tartiblash, Save va Run oldidan ham darhol flush.
- `PUT /api/ui-state` kalitlar bo'yicha birlashtiradi: tablar va daraxt holati bir-birining ustidan yozmaydi.
### Changed
- Testlarda barcha qat'iy `wait_for_timeout`/`sleep` shartli kutishga almashtirildi (`expect`, `expect_response`, `wait_for_function`, `eventually`); "darhol reload" testlari qo'shildi.
- `origin` URL: `API-runner`.

## [2.1.6] — 2026-10-30 — Ma'lumotlar xavfsizligi
### Added
- Avtomatik zaxira `backups/<sana-vaqt>_v<versiya>/` (saved_requests.json + workspace/ + SQLite — izchil `backup` API bilan). Oxirgi 20 tasi saqlanadi; eskilari faqat yangisi yaratilgandan keyin va faqat nom andozasiga mos kataloglar o'chiriladi.
- `schemaVersion` va idempotent migratsiya qadamlari (`1→2`: tarixga `hash` ustuni). Migratsiyadan oldin/keyin papka, so'rov, env sonlari solishtiriladi; nomuvofiqlik yoki xatoda zaxiradan avtomatik rollback va `/api/status` orqali ogohlantirish.
- Zaxiradan tiklash: `POST /api/backups/restore`, `GET/POST /api/backups`, CLI `python3 -m apirunner.restore <papka>`; tiklashdan oldin joriy holat `..._pre-restore` zaxirasiga olinadi. `saved_requests.json` tiklashda ham tegilmaydi.
- Jarayonlararo qulf (flock) va `rev` versiya tekshiruvi (collection/env/globals `PUT` eskirgan bo'lsa `409`).
- `tools/anonymize_saved.py` va anonimlashtirilgan fixture bilan migratsiya testi.
- UI: Sozlamalar → Zaxiralar (yaratish, ro'yxat, tiklash), migratsiya rollback ogohlantirishi (`/api/status`), birinchi ochilishda localStorage'ni avtomatik (idempotent, o'chirmasdan) ko'chirish va bir martalik xabar "Eski Default o'zgaruvchilar Globals'ga ko'chirildi", env saqlashda `409` (boshqa tab) xabari.
### Fixed
- Regressiya: Params ↔ URL ikki tomonlama sinxron qayta tiklandi (URL to'liq query bilan turadi, yuborishda jadval manba; o'chirilgan qatorlar saqlanadi).
### Changed
- Barcha JSON yozuvlari atomik (mkstemp → fsync → os.replace → katalog fsync). SQLite WAL rejimida.
- localStorage importi mazmun xeshi bo'yicha dublikatsiz; "Default" env va eski yagona o'zgaruvchilar Globals'ga ko'chadi (mavjud kalit ustidan yozilmaydi). localStorage'dan hech narsa o'chirilmaydi.
- id'siz eski yozuvlar tashlab yuborilmaydi — id beriladi.
- Testlar `APIRUNNER_TESTING=1` ostida faqat aniq (tmp) yo'llar bilan ishlaydi.

## [2.1.5] — 2026-10-30
### Added
- Yangi UI: Batch/Runner bo'limi (data fayl, rows mode, delay, timeout, parallel, retry, SSL, Run/Stop, SSE), natijalar paneli (progress, statistika, filtrlar, kartalar, fullscreen, grafik, JSON/CSV eksport, run'larni solishtirish), cURL export, Beautify, env tanlagich, sidebar yig'ish/kengligi, ⇪ import, ⤓ `saved_requests.json` eksport tugmasi, Postman/OpenAPI import tugmasi, duplicate.
- 40 paritet e2e testi (`tests/e2e/test_parity.py`).
### Changed
- cURL tokenizer POSIX qo'shni segmentlarni (`'it'\\''s'`) tushunadi.
### Fixed
- SSE javobidagi hop-by-hop `Connection: keep-alive` sarlavhasi olib tashlandi: brauzer yopilgan ulanishni qayta ishlatib, run tugagach keyingi so'rov osilib qolardi (eski UI'da ham bor edi).

## [2.1.4] — 2026-10-30
### Added
- Yangi frontend (Vite + Vue 3 + TS + Pinia), `/` da; eski UI `/legacy` da. Build `apirunner/static/app/` ga commit qilingan.
- Multi-tab: preview/doimiy tab, dirty ●, saqlash dialogi, kontekst menyu, tab DnD, "barcha tablar", server tomonda tiklash, Cmd/Ctrl+T/W/Tab/Shift+T, env/collection/runner tablari.
- Sidebar: ichma-ich daraxt, DnD (before/inside/after, avto-ochish, avto-scroll, Alt=nusxa, sikldan himoya, ko'p tanlash), "Ko'chirish…", qidiruv.
- Runner tabi (ro'yxat DnD tartibi, belgilash, ketma-ket ishga tushirish, data fayl), params/headers/form-data qatorlari DnD.
- Import: Postman v2.x (ichma-ich, skript, auth, example), OpenAPI/Swagger JSON, `POST /api/import`; fayl/cURL matnini oynaga tashlash.
- 57 ta spetsifikatsiya (multi-tab 31, DnD 27) haqiqiy e2e testlarga aylantirildi — hammasi yashil.

## [2.1.3] — 2026-10-30
### Added
- Daraxt API: `POST/PATCH/DELETE /api/collections/<id>/items`, `POST /api/items/move` (before/after/inside, ko'p tanlash, collection'lar orasida, `copy`, papkani o'z avlodiga ko'chirishdan himoya). Tartib `item[]` massivida saqlanadi → eksportda ham.
- `GET/PUT /api/ui-state` (ochiq tablar server qayta ishga tushganda tiklanishi uchun), `PUT /api/workspace/meta` (faol env), `POST/DELETE /api/history`.

## [2.1.2] — 2026-10-30
### Added
- Orqaga qaytish: `python3 -m apirunner.export_legacy` va `GET /api/export/legacy` (workspace → `saved_requests.json`).
- `/legacy` — eski UI paritet tugaguncha shu manzilda saqlanadi.
### Changed
- Rad etilgan fayl yo'li xabari: "… 📎 orqali faylni qayta tanlang" (`error_code: file_policy`).

## [2.1.1] — 2026-10-30
### Changed
- HTTP engine `requests` → `httpx` (ADR 0003). Redirect'lar avvalgidek kuzatiladi; URL query va `params` birlashtiriladi.
### Added
- Timing breakdown (`connect`, `tls`, `ttfb`, `total`) httpcore trace orqali; olinmagan qiymat `null` (UI: "—"). DNS httpcore'da alohida ko'rinmaydi, `connect` ichida.
- Ixtiyoriy HTTP/2 (`http2: true`), sukut bo'yicha HTTP/1.1; natijada `http_version`.

## [2.1.0] — 2026-10-30 — Bosqich 0–1 (refaktor va poydevor)
### Added
- `apirunner/{core,storage,api}` paketi, yagona `execute()` engine, `create_app()` fabrikasi.
- Workspace (Postman v2.1 superseti, JSON) + SQLite; `saved_requests.json` va localStorage (⇪ tugma) migratsiyasi.
- `/api/*` workspace API, ADR 0001–0007, `docs/ROADMAP.md`.
- pytest characterization va Playwright smoke/e2e testlar; Bosqich 2 uchun skip qilingan spetsifikatsiyalar.
- `GET /api/version`, UI pastki burchagida versiya.
### Changed
- `/run_one` `/run` bilan bir xil engine'da ishlaydi (`{{ var }}`, multipart, fayl); JSON body baytma-bayt yuboriladi.
### Fixed
- To'xtatilganda `completed` hisobi; concurrency'da navbatdagi so'rovlar to'xtatilganda yuborilmaydi.
- Axlat localStorage ma'lumotida import qulashi.
### Security
- Host/Origin tekshiruvi, sessiya tokeni, fayl parametrlari uchun yo'l siyosati.
