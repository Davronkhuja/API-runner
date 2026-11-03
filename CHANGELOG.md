# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/). Versiyalash: SemVer (bosqich tugashi = MINOR, bosqich ichidagi funksiya/tuzatish = PATCH). Yagona manba: `apirunner/__init__.py`.

## [2.3.2] — 2026-11-04 — Fix: nomni o'zgartirish
### Fixed
- **Rename → Save nomni eskisiga qaytarardi** (paritet regressiyasi): sidebar'dagi rename faqat serverni va tab sarlavhasini yangilardi, ochiq tab qoralamasidagi `draft.name` eski qolardi va ⌘S qoralamani butunligicha yozib nomni bosib ketardi. Endi nom **bitta manbadan** (`lib/rename.ts → renameNode`) o'zgaradi: server, daraxt, barcha ochiq tablar (sarlavha va qoralama nomi) birdaniga; qoralamadagi boshqa saqlanmagan o'zgarishlar (method, URL, body) va dirty holati tegilmaydi. `saveTab` saqlangan so'rovda nom maydonini umuman yozmaydi.
### Added
- **Breadcrumb'dagi so'rov nomi** bosilganda (yoki Enter) inline input: Enter/blur — saqlash, Esc — bekor; saqlanmagan yangi so'rovda bosilsa "Saqlash" dialogi ochiladi. Papka va collection tabi sarlavhasida ham xuddi shunday.
- **Collection'ni qayta nomlash** (F2, kontekst menyu, tab sarlavhasi); Runner tabi sarlavhasi ham yangilanadi.
- Tab kontekst menyusida **"Nomini o'zgartirish"** (so'rov va collection/papka tablari).
- **Dublikat** qilingach yangi element darhol rename rejimida ("… Copy" belgilangan); nusxa nomlari takrorlanmaydi ("X Copy", "X Copy 2").
- Rename input'ga fokus va belgilash ishonchli (`nextTick` + `focus/select`, `autofocus` o'rniga); Enter/Esc dan keyingi blur ikkinchi marta ishlamaydi.
- Bo'sh nom va bir papkadagi takror nom uchun aniq xabar (Enter — tahrirda qoladi, blur — bekor qiladi); collection nomlari ham takrorlanmaydi.
- 11 yangi e2e (`test_rename.py`).

## [2.3.1] — 2026-11-04 — Papka/collection auth'ini topish va boshqarish
### Added
- **Papka/collection tabi Postman kabi**: daraxtda qator bosilsa preview tab ochiladi (ikki marta — doimiy); chevron faqat ochadi/yopadi; kontekst menyu saqlangan (Sozlamalar, Runner, …). Bo'limlar: **Overview** (so'rovlar/papkalar soni, auth xulosasi, o'zgaruvchilar, o'z auth'i bor so'rovlar soni, tavsif) | **Auth** | **Variables** | **Scripts** | **Run** (Runner'ni shu papka/collection doirasida ochadi — Runner endi `cid:papka` ref'ini qo'llab-quvvatlaydi).
- **Meros manbasi**: so'rovning Auth tabida "Meros" tanlanganda qaysi papka/collection auth'i ishlatilishi (tur, nom) va "Papkaga/Collection'ga o'tish" havolasi ko'rinadi; hech narsada auth bo'lmasa — aniq tushuntirish. Papka Auth tabida ham yuqoridagi manba ko'rsatiladi.
- **Ommaviy "Meros" taklifi**: papka/collection'ga auth qo'yilganda ichidagi o'z auth'i bor so'rovlar sanaladi (yaqinroq ota-papkasining o'z auth'i bilan to'silganlari hisobga olinmaydi). Dialog: har bir so'rov uchun tanlash, auth turi, **bir xil token/sozlamali so'rovlar ("ko'chirishdan qolgan") avtomatik aniqlanib oldindan tanlanadi**, "Auth yo'q" qilinganlar tanlanmaydi; Hammasini tanlash / Hech birini / O'zgarishsiz qoldirish (Esc). `POST /api/collections/<cid>/inherit-auth`: **o'zgartirishdan oldin avtomatik zaxira** (`…_pre-bulk-auth`), bitta atomik yozuv; ochiq tablardagi qoralamalar ham "Meros"ga o'tadi.
- **Daraxtda qulf belgisi** (🔒): o'z auth'i bor collection, papka va so'rovlarda (tur tooltip'da; meros va "Auth yo'q" belgilanmaydi).
- 12 yangi e2e (`test_node_tabs.py`) va 1 backend testi.
### Changed
- Papka bosilganda endi tab (preview) ham ochiladi; "tab ochiq emas" holatini tekshiruvchi bitta test yangilandi.
### ROADMAP
- Yangi **Bosqich 4b — Kundalik qulayliklar** (Initial/Current qiymatlar, `{{` avtoto'ldirish, Example'lar daraxtda, Docs paneli, Trash, Find & Replace, javoblar tarixi va diff, Send and Download, JWT RS*/ES*/NTLM/Hawk) va Bosqich 7 ga rejalashtirilgan run'lar (monitor) hamda proxy capture qo'shildi.

## [2.3.0] — 2026-11-04 — Bosqich 3 tugadi (skriptlar va testlar)
### Added (UI)
- **Skript muharriri** (CodeMirror 6, JavaScript): so'rov tabida **Scripts** bo'limi (Pre-request / Tests), shuningdek collection va papka sozlamalarida (meros: collection → papka → so'rov). `pm.*` / legacy avtoto'ldirish (≈130 nom, izoh bilan), tayyor **snippetlar paneli** (Status 200, javob vaqti, JSON qiymati, javobdan muhitga yozish, token olish, header, `setNextRequest`, HMAC … — pre/test bo'yicha ajratilgan), qator raqamlari, xato qatorlarini belgilash. Skriptlar Postman `event[]` formatida saqlanadi (import/eksport bilan mos); saqlanmagan skript tahriri sahifa yangilanganda tiklanadi.
- Javob panelida **Testlar** tabi: o'tdi/muvaffaqiyatsiz/o'tkazildi soni, har bir test (PASS/FAIL/SKIP, xabar, manba: Collection/Papka/So'rov), **skript xatolari** (nom, xabar, manba, stack trace) — har birida «qator N» havolasi: muharrirda (yoki collection/papka tabida) shu qatorga o'tadi va qator belgilanadi; muvaffaqiyatsiz test qatorlari ham belgilanadi. `skipRequest` / `setNextRequest` holati ko'rsatiladi.
- **Console paneli** (status bardagi Console): so'rov/javob loglari, `console.log/info/warn/error/debug`, skript xatolari (stack bilan), qo'llab-quvvatlanmaydigan API ogohlantirishlari; filtrlar, qidiruv, tozalash, o'zgarishi mumkin balandlik; yopiqda o'qilmagan xatolar badge'i; xato qatoriga o'tish.
- **Sozlamalar → Skriptlar**: holat (quickjs-ng versiyasi) va sozlanadigan chegaralar — skript vaqti, xotira, `pm.sendRequest` soni (sukutga qaytarish bilan).
- **quickjs-ng yo'q holat**: skript tablari ko'rinadi (matn saqlanadi), «Skriptlar o'chiq» tushuntirishi va o'rnatish buyrug'i (`pip install quickjs-ng`, nusxalash tugmasi) — Scripts bo'limida, Sozlamalarda, Testlar tabida va Console'da; so'rovlar odatdagidek yuboriladi.
- **Runner**: skriptlar har so'rovda ishlaydi; **`setNextRequest(nom|null)`** (Postman semantikasi), **`skipRequest`** (`SKIPPED`, xato hisoblanmaydi), iteratsiya data qatori `pm.iterationData`ga uzatiladi, o'zgaruvchilar so'rovlar orasida saqlanadi; cheksiz tsikldan himoya (1000 qadam). **Batch**: skriptlar har qatorda (concurrency bilan), natija kartalarida `tests p/t` va skript xatolari badge'i.
- ⌘K/Skript natijalari: muhit/global/collection o'zgaruvchilari skriptdan keyin UI'da avtomatik yangilanadi.
### Changed
- `ui-state` dan tiklangan eski qoralamalar `normalizeDraft` bilan yangi maydonlar (`scripts`, `settings`, `pathVars`, …) to'ldiriladi.
- Status bardagi Console tugmasi faol; `docs/ROADMAP.md` yangilandi (Console, Data/Local scope bajarildi).
### Bosqich 3 yakuni
Bajarildi: skript engine (v2.2.4) + UI (shu versiya). ADR 0007 ga ko'ra `quickjs-ng`; xavfsizlik chegarasi, thread-safety (concurrency=10 stress testlari), async semantika, `pm.sendRequest` engine orqali, `require`/legacy, aniq ogohlantirishlar, sozlanadigan limitlar va Postman'ning real ommaviy namunalari bilan muvofiqlik testlari. Ochiq qolganlari: `pm.visualizer`, `pm.vault`, `pm.cookies.jar` ning ba'zi metodlari, `tv4`/`ajv`/`cheerio`, Intl; Runner natijalarida **Testlar ustuni** va run tarixi — Bosqich 4.

## [2.2.4] — 2026-11-04 — Bosqich 3 (1/3: skript engine, backend)
### Added
- **Skript sandbox** (`apirunner/core/scripting/`, ADR 0007 — `quickjs-ng`): pre-request va test skriptlari collection → papka → so'rov tartibida. Kontekstda host ob'ekti, fayl, tarmoq, modul yuklovchi, hatto Python callable ham yo'q; host bilan aloqa JS tomonidagi navbat orqali (quickjs vaqt limiti bilan Python callable'ga ruxsat bermaydi). Har bajarish o'z kontekstini yaratadi — thread'lar orasida bo'lishilmaydi (concurrency=10 stress testi).
- **`pm.*`**: `environment` / `globals` / `collectionVariables` / `variables` / `iterationData` (`get/set/unset/has/clear/toObject/replaceIn`), `request` (o'qish va o'zgartirish: method, url + query, headers, body), `response` (`code`, `status`, `headers`, `json()`, `text()`, `responseTime`, `cookies`, `to.have.status/header/body/jsonBody`, `to.be.ok/success/error/…`), `test` (+ `skip`, async va `done` uslubi), `expect` (chai), `sendRequest` (callback va Promise), `execution.setNextRequest/skipRequest`, `info`, `cookies` (+ qisman `jar()`), `console.*`.
- **Event loop**: `await`, Promise, `setTimeout/setInterval` va `pm.sendRequest` tugaguncha skript tugamagan hisoblanadi; umumiy vaqt chegarasi (haqiqiy kutish bilan).
- **`pm.sendRequest` asosiy engine orqali**: auth (bearer/basic/apikey), global sozlamalar (proxy, SSL, redirect, CA, mTLS), cookie jar, `{{o'zgaruvchi}}`; so'rovlar soni va ichma-ich chuqurlik chegarasi.
- **`require`**: `lodash`, `crypto-js`, `moment`, `chai`, `dayjs`, `uuid`, `xml2js` (kichik), `atob`/`btoa`. Qo'llab-quvvatlanmagan modul/API (`cheerio`, `tv4`, `pm.visualizer`, `pm.vault`, noma'lum `pm.*` …) **jim o'tmaydi** — Console'da ogohlantirish.
- **Legacy**: `tests["…"] = bool`, `responseBody/Code/Time/Headers`, `postman.setEnvironmentVariable/get/clear…`, `setGlobalVariable…`, `setNextRequest`, `environment`/`globals`/`data`/`request` obyektlari, `xml2Json`, global `_`, `CryptoJS`, `moment`.
- **Xato izolyatsiyasi**: skript xatosi so'rovni to'xtatmaydi; xato `{name, message, stack, line, origin{scope,name,id,kind}}` bilan qaytadi (qator raqami skript matniga mos). Sintaksis xato, vaqt/xotira/stack chegarasi aniq xabarlar bilan; chegaradan oshgach qolgan skriptlar o'tkazib yuboriladi, natijalar saqlanadi.
- **Saqlash qoidasi**: skript workspace'ni faqat `pm.environment/globals/collectionVariables` orqali o'zgartiradi, yozuvni skript emas, server qiladi (qulf ostida, faqat o'zgargan kalitlar; qiymat o'zgarmasa diskka yozilmaydi). Faol muhit yo'q bo'lsa — o'zgarish faqat shu bajarish uchun (Console'da ogohlantirish).
- **Data/Local scope**: `pm.iterationData` (CSV/JSON qator), `pm.variables.set` (local) — saqlanmaydi. Ustuvorlik: Global < Collection < Environment < Data < Local.
- **Oqim** (`core/flow.py`): Postman Runner semantikasi — iteratsiyalar, `setNextRequest(nom|null)`, `skipRequest`; CLI (Bosqich 7) va muvofiqlik testlari uchun.
- API: `/run_one` va `/run` (batch) `scripts` + `ref` qabul qiladi va natijaga `scripts{tests, console, errors, next_request, skipped, changed}` qo'shadi; `GET /api/scripts/status`; `PUT /api/workspace/meta` → `script_limits` (timeout 100–300000 ms, xotira 8–1024 MB, `pm.sendRequest` soni 0–200).
- `requirements-scripts.txt` (`quickjs-ng`, ixtiyoriy): `run.command` o'rnatadi; o'rnatilmasa ogohlantiradi, ilova ishlayveradi — skriptlar o'chiq, so'rovlar odatdagidek.
- `THIRD_PARTY_LICENSES.md`: chai 4.5.0, lodash 4.18.1, crypto-js 4.2.0, dayjs 1.11.23, moment 2.31.0 (MIT) — versiya va litsenziya matnlari.
- **Muvofiqlik testlari** (Postman'ning real ommaviy namunalari, o'zgarishsiz): Sample Collection (collection/papka/so'rov skriptlari, `zyx()` xatosi, console, `sendRequest`, `setNextRequest("Done")`), nested `sendRequest` (`res.stream.toString()`), Twitter (legacy `tests[]`, `postman.setEnvironmentVariable`, `events` kaliti), helpers (`environment.x`), catURL (`responseHeaders.location`, `request.data`, redirect), shuningdek ularning naqshlari asosidagi murakkab oqim (pre-request'da token olish + `setNextRequest` tsikli + legacy `tests[]`).
- 75 yangi test: `test_scripting` (23), `test_scripts_integration` (18), `test_postman_compat` (9) va boshqalar.
### Fixed
- `x-www-form-urlencoded` tanasida `{{o'zgaruvchi}}` (brauzer `%7B%7B…%7D%7D` ga kodlagan) yechilmasdi; endi har maydon dekodlanib, yechilib, qayta kodlanadi (qiymatdagi `&`/`=` buzilmaydi).

## [2.2.3] — 2026-11-03
### Added
- **Favikon**: `web/public/favicon.svg` (indigo kvadrat ichida oq chaqmoq — dizayn logotipi), `favicon.ico` (16/32/48), `apple-touch-icon.png` (180, to'liq kvadrat), `icon-192.png`, `icon-512.png`, `manifest.webmanifest` (`tools/make_icons.py` bilan hosil qilinadi; fayllar commit qilingan — Node'siz ishga tushish buzilmaydi). Yangi UI va `/legacy` sahifasida `<link rel="icon">` (SVG + ICO fallback), `apple-touch-icon`, `manifest`, `theme-color`.
- Flask `/favicon.ico` va `/apple-touch-icon.png` ni haqiqiy fayl bilan, `Cache-Control: public, max-age=31536000, immutable` bilan qaytaradi (sessiya tokensiz — 404 yo'q).
- Brauzer tab sarlavhasida holat: so'rov yuborilayotganda `● Yuborilmoqda — API Runner`, Runner/Batch ishlayotganda `● Runner 12/18 — API Runner` (bir nechta bo'lsa `(+N)`), tugagach `API Runner`.
- 9 yangi e2e (`test_favicon.py`): ICO tuzilishi va cache, PNG o'lchamlari, brauzerda piksel tekshiruvi (rang, oq chaqmoq, shaffof/to'liq burchak), manifest, ikkala sahifadagi barcha `href` 200, tab sarlavhasi.
### Removed
- ⌘⇧O / ⌘⇧R yorliqlari (Chrome'da bookmark manager va hard reload bilan to'qnashadi). Import va Runner ⌘K palitrasida (`Import (Postman, OpenAPI)`, `Runner`); Bosh sahifa kartalari shunga ishora qiladi.

## [2.2.2] — 2026-11-03
### Added
- Yorliqlar: **⌘⇧O** — Import, **⌘⇧R** — Runner (brauzerning ⌘O/⌘R yorliqlari bilan to'qnashmaydi); Bosh sahifadagi kartalar va yorliqlar ro'yxatida ko'rsatilgan. 2 yangi e2e.
- `docs/design/` — dizayn maketlari (Main, Welcome, Runner) loyiha hujjati sifatida repoda.
### Changed
- `requirements-dev.txt`: `pytest-xdist`, `pytest-timeout`. `pytest.ini`: sukut bo'yicha `-n 4 --timeout=90` (parallel; ketma-ket: `-n 0`). README "Testlar" bo'limi yangilandi (buyruqlar, skrinshotlarni yangilash, frontend build).
- ROADMAP: dizayn maketidan qolganlar tegishli bosqichlarga yozildi — Console paneli → Bosqich 3; Runner'dagi parallel / o'zgaruvchilarni va javoblarni saqlash / Testlar ustuni → Bosqich 4; workspace almashtirgich → Bosqich 7.

## [2.2.1] — 2026-11-02 — Yangi dizayn (docs/design maketlari)
### Changed
- **Dizayn tizimi**: `web/src/styles/tokens.css` — `.th-light`/`.th-dark` tokenlari (ranglar, metod ranglari GET/POST/PUT/PATCH/DELETE, JSON ranglari, ok/err, o'zgaruvchi chiplari). Barcha komponentlar faqat shu o'zgaruvchilardan foydalanadi (tekshiruv testi: aniqlanmagan token yoki qattiq yozilgan rang yo'q). Eski `--fg/--bd/--ac…` o'zgaruvchilari olib tashlandi.
- **Tema**: headerdagi almashtirgich, tanlov `localStorage`da saqlanadi va sahifa chizilishidan oldin qo'llanadi (miltillashsiz); saqlanmagan bo'lsa tizim sozlamasi.
- **Shriftlar**: Inter (UI) va JetBrains Mono (kod, URL, metodlar) — lokal woff2 (`@fontsource-variable`, lotin / lotin-ext / kirill), CDN'ga bog'lanmaydi (oflayn ishlaydi).
- **Qobiq**: header (logo, workspace, ⌘K qidiruv, Import, muhit tanlash, muhit o'zgaruvchilari, tema, sozlamalar) → chap ikonka rail (Kolleksiya / Muhitlar / Tarix / Runner) → sidebar → tablar → breadcrumb + URL bar + so'rov tablari (hisoblagich badge'lari) → sudraladigan ajratgich → javob paneli → pastki status bar (server holati, Console, Cookie'lar, zaxira vaqti, versiya).
- **Mikro-detallar**: faol tabning yuqori chizig'i, saqlanmagan tabda nuqta, tabda metod yorlig'i, URL ichidagi `{{var}}` rangli chip (aniqlanmagan — qizil) va hover'da scope/qiymat tooltip'i, status pill (`200 OK` yashil, 4xx/5xx qizil), vaqt ustida timing tooltip'i, bo'sh holatlar (javob yo'q, tab yo'q → bosh sahifa).
- **Bosh sahifa** (tab ochiq emas): boshlash kartalari, ⌘V bilan cURL joylashtirish, import zonasi, oxirgi so'rovlar, yorliqlar.
- **Runner** maketga mos: sozlamalar paneli (so'rovlar tartibi + tanlash, iteratsiyalar, kechikish, ma'lumot fayli, birinchi xatoda to'xtash), progress, 4 ta statistika kartasi, filtrlangan natijalar jadvali, To'xtatish.
### Added
- **⌘K** qidiruv palitrasi (so'rov nom/URL/metod, muhit, amallar; ↑↓ Enter Esc).
- **Klaviatura**: daraxt (↑↓ ←→ Enter F2), tablar va so'rov bo'limlari (←→ Home End, Delete), sidebar/javob ajratgichi (strelkalar), global fokus halqasi.
- **A11y**: ikonka-tugmalarda `aria-label`, `role=tablist/tab/tree/dialog`, `aria-pressed/expanded/selected`, progress `role=progressbar`; matn kontrasti WCAG AA — ikkala temada tekshiriladi (light'da GET/POST rangi `hover`/`accent-weak` fonida 4.5:1 uchun sal quyuqlashtirildi).
- Har ekran uchun Playwright skrinshot testi (light + dark, 1440×900); `docs/screenshots/{before,after}/…` va oldin/keyin jadvali (`docs/screenshots/README.md`, `tools/shots_readme.py`).
- 33 yangi e2e (`test_redesign.py`) va 9 token testi (`test_design_tokens.py`).
### Moved (funksiya yo'qolmadi)
- ⇪ localStorage import va ⤓ `saved_requests.json` eksport → Sozlamalar → "Ma'lumotlar"; 🕘 kengaytirilgan tarix → Tarix paneli sarlavhasi; 🍪 Cookie Manager → status bar.
### Eslatma
- Maketdagi Console va ⌘O/⌘R yorliqlari: Console faol emas (Bosqich 3 skriptlari bilan), brauzer yorliqlari bosib o'tilmadi.
- Testlar: ko'chgan elementlar uchun yo'l yangilandi; DnD testlari qatorlarni indeks emas, qator ichidagi birinchi maydon bo'yicha to'ldiradi.

## [2.2.0] — 2026-11-02 — Bosqich 2 tugadi
### Added
- **Code snippet generatori** (`</> Kod`): cURL, Python requests, JavaScript fetch, axios, Node.js http, Go net/http, PHP cURL, Java OkHttp, C# HttpClient. O'zgaruvchilar qiymat bilan almashtiriladi, meros auth/API Key kiradi (JWT/Digest/SigV4 haqida eslatma), multipart va xom tana qo'llab-quvvatlanadi; yaroqsiz URL sahifani buzmaydi. cURL, Python va Node snippetlari e2e testda **haqiqatan bajarilib** tekshiriladi. 9 til uchun 6 unit test.
- **Body**: *binary* (fayl xom baytlar bilan, fayl siyosati bo'yicha) va *GraphQL* (Query + Variables JSON → `{"query","variables"}`; noto'g'ri JSON aniq xato beradi); Postman `file`/`graphql` formatida saqlanadi.
- **Qator tavsifi** (Params/Headers/Form) va **Bulk Edit** (`kalit:qiymat`, `//` — o'chirilgan; tavsif va fayl turi kalit bo'yicha saqlanadi).
- 8 e2e (`test_body_rows.py`), 6 e2e (`test_snippets.py`), 1 engine testi.
### Bosqich 2 yakuni
Bosqich 2 ning barcha bandlari (collection/papka sozlamalari va meros, scope'li o'zgaruvchilar, Auth turlari + OAuth 2.0, Response paneli, cookie'lar va sozlamalar, snippetlar, body turlari, qator tavsifi/bulk edit, server tarixi) bajarildi. Ochiq qolganlari: JWT RS*/ES*, SOCKS proxy, cookie'larni sozlamalardan domen bo'yicha o'chirish, Data/Local scope (Bosqich 3 skriptlari bilan).

## [2.1.19] — 2026-11-02 — Bosqich 2 (4/5: cookie'lar va sozlamalar, frontend)
### Added
- **Cookie Manager** tabi (🍪): domenlar bo'yicha guruhlangan jar; qiymatni joyida tahrirlash, bittasini/domenni (tasdiq bilan)/hammasini o'chirish, qo'lda qo'shish, tekshiruv xabari.
- Response → **Cookies** tabi: `Set-Cookie` atributlari (domen, yo'l, muddat, HttpOnly/Secure/SameSite).
- **Sozlamalar**: so'rov tabida "Sozlamalar" bo'limi va ⚙ → global sozlamalar (redirect'larga ergashish, maks. redirect, HTTP/2, SSL tekshiruvi, cookie jar, proxy, CA fayli, mijoz sertifikati/kaliti). "Sukut" global qiymatni ko'rsatadi; so'rov sozlamasi globalni bosadi; so'rov bilan birga `x-apirunner.settings` ga saqlanadi; Batch va Runner ham ishlatadi.
- 9 yangi e2e (`test_cookies_ui.py`), 2 unit test.
### Fixed
- Cookie qo'shishda maydonlar so'rov javobini kutmasdan tozalanadi (keyingi yozuv oldingi so'rov tomonidan o'chib ketmasin); ro'yxat yuklash "oxirgisi g'olib" (eskirgan javob yangisini bosmaydi).

## [2.1.18] — 2026-10-30 — Bosqich 2 (4/5: cookie'lar va sozlamalar, backend)
### Added
- **Cookie jar** (SQLite `workspace/state.db`, `storage/cookies.py`): `Set-Cookie` avtomatik saqlanadi va keyingi so'rovlarga domen/yo'l/secure qoidalari bo'yicha yuboriladi (`http.cookiejar`); serverda o'chirilgan (muddati o'tgan) cookie bazadan ham ketadi; jarayon qayta ishga tushganda saqlanadi; Batch qatorlari bitta jar'ni ulashadi. `spec.use_cookies=false` — jar o'chiq. Natijada `set_cookies` (har bir Set-Cookie alohida) va `redirects`.
- Cookie Manager API: `GET/POST/DELETE /api/cookies` (bittasini, butun domenni yoki hammasini o'chirish; qo'lda qo'shish; muddati o'tganlar ko'rinmaydi).
- So'rov sozlamalari (`spec`): `follow_redirects`, `max_redirects`, `proxy` (http/https), `ca_bundle` (maxsus CA), `cert` + `cert_key` (+`cert_passphrase`) mijoz sertifikati (mTLS), `ssl_verify=false` sertifikat bilan birga; fayl topilmasa tushunarli xato. Global sozlamalar `workspace.json` → `settings` (`PUT /api/workspace/meta`).
- 11 yangi test (`test_cookies_settings.py`: proxy serveri, `openssl` bilan CA/server/mijoz sertifikatlari va mTLS serveri, redirect zanjiri).
### Changed
- `/run_one` javobiga `set_cookies` va `redirects` qo'shildi. `_send(..., spec, ctx)` imzosi kengaydi.
- Maxsus CA ishlatilganda `VERIFY_X509_STRICT` o'chiriladi (Python 3.13+ qat'iy rejimi AKI'siz xususiy CA sertifikatlarini rad etardi; requests/Postman kabi yumshoq).

## [2.1.17] — 2026-10-30 — Bosqich 2 (3/5: Response paneli)
### Added
- Response paneli (`ResponsePanel.vue`): **Body** (Pretty / Raw / Preview) va **Headers** tablari; Preview faqat HTML javobda va `sandbox=""` iframe'da (skriptlar bloklangan).
- Qidiruv: moslashuvlar soni, ↑/↓ (Enter / Shift+Enter) bilan aylanib o'tish, joriy moslashuv ajratiladi.
- **JSONPath** (`lib/jsonpath.ts`): `$ . .. [n] [-n] [a:b] [*] ['k']` va `[?(@.k OP qiymat)]`; natijalar soni, xato xabari; faqat JSON javobda.
- **Virtual scroll**: 1500 qatordan katta javob faqat ko'rinadigan oynani chizadi (5000 elementli massivda DOM < 200 qator); qidiruv va JSONPath virtual rejimda ham ishlaydi.
- **Save as Example**: javob so'rovga Postman namunasi sifatida (`response[]`: originalRequest, status/code, header, body) saqlanadi; "Namunalar (n)" ro'yxatidan panelga qayta yuklanadi. Saqlanmagan so'rovda tushunarli ogohlantirish.
- 9 yangi e2e (`test_response_panel.py`), 5 JSONPath unit testi.
### Changed
- Javob matni `RequestEditor`dan `ResponsePanel`ga ko'chirildi (`resp-body` test identifikatori saqlangan).

## [2.1.16] — 2026-10-30 — Bosqich 2 (2/5: Auth, frontend)
### Added
- Auth turlari formasi (so'rov, papka va collection darajasida; meros ishlaydi): **API Key**, **Digest**, **OAuth 2.0**, **AWS Signature V4**, **JWT Bearer** (+ mavjud Bearer/Basic/Custom). Postman formatida saqlanadi (`apikey`/`oauth2`/... massivlari).
- **OAuth 2.0** (`lib/oauth.ts`): Client Credentials, Password, Authorization Code, Authorization Code + **PKCE** (S256), Implicit. "Get New Access Token" (popup + `/oauth/callback`, `state` tekshiruvi), joriy token (maskalangan, muddati, refresh), tokenni o'chirish, tokenni header yoki query'ga qo'shish, header prefiksi.
- Yuborishdan oldin avtomatik: token yo'q bo'lsa (Client Credentials/Password) olinadi, muddati tugagan bo'lsa `refresh_token` bilan yoki qayta olinadi; kod oqimlarida token yo'q bo'lsa tushunarli xato. Single send, Batch va Collection Runner uchun.
- Tokenlar `sessionStorage`da (collection faylga yozilmaydi); kalit — grant/URL/clientId/scope/username.
- 11 yangi e2e (`test_auth_ui.py`, soxta authorize endpoint bilan popup oqimlari) va echo serverga `/oauth/authorize`.
### Eslatma
- JWT faqat HS256/384/512 (RS*/ES* uchun `cryptography` kerak — o'rnatilmagan; aniq xabar chiqadi).
- Digest/SigV4/JWT/API Key yagona so'rov va Batch'da engine orqali; "Copy as cURL" faqat Bearer/Basic/Custom auth'ni qo'shadi.

## [2.1.15] — 2026-10-30 — Bosqich 2 (2/5: Auth, backend)
### Added
- `spec.auth_config` (engine): **API Key** (header/query), **JWT** (HS256/384/512, payload JSON'da `{{}}` va `{{$timestamp}}`, header/query), **AWS Signature V4** (AWS test-suite vektori bilan tekshirilgan; session token, S3 payload xeshi), **Digest** (httpx `DigestAuth`). Xatolar (masalan RS256 — `cryptography` o'rnatilmagan) exception emas, natija xatosi sifatida qaytadi.
- `POST /api/oauth2/token`: Client Credentials, Password, Authorization Code (+PKCE `code_verifier`), Refresh Token; client autentifikatsiyasi header (Basic) yoki body; `{{}}` yechiladi; `expires_at` hisoblanadi; xatolar tushunarli (`error_description`). Server tomonida — CORS yo'q.
- `GET /oauth/callback`: Authorization Code/Implicit uchun redirect sahifasi (ochiq yo'l; faqat `postMessage` bilan o'z origin'iga uzatadi).
- 13 yangi test (`tests/test_auth_types.py`), echo serverga `/digest` va `/oauth/token`.

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
