# Vazifa: API Runner'ni Postman darajasiga olib chiqish

Sen tajribali full-stack muhandissan. `API runner` loyihasini (shu repo) bosqichma-bosqich Postman darajasidagi, moslashuvchan va ko'p funksiyali API klientga aylantirishing kerak. Ishni o'zing rejalashtirasan, kod yozasan, test qilasan va har bosqichni commit qilasan. Quyida loyihaning hozirgi holati, maqsad, arxitektura bo'yicha qarorlar, bosqichlar va ish qoidalari berilgan.

---

## 1. Hozirgi holat (boshlashdan oldin o'zing ham tekshirib chiq)

- **Stack:** Python 3 + Flask + `requests`. Bitta fayl: `api_runner.py` (~5360 qator). Uning ~4770 qatori — `HTML = r"""..."""` ichidagi vanilla HTML/CSS/JS UI. Port: `127.0.0.1:5050`. `run.command` orqali ishga tushadi (portni bo'shatadi, `pip install`, brauzerni ochadi).
- **Backend endpointlari:**
  - `/run` + `/stream/<job_id>` (SSE) + `/stop/<job_id>`: CSV/JSON qatorlari bo'yicha batch yuborish; `concurrency` ≤10, `retry`, `delay`, `timeout`, `ssl_verify`, `{{var}}` almashtirish, multipart, fayl parametrlari.
  - `/run_one`: bitta so'rov. Mantiq `job_worker`dan **alohida nusxa** qilingan va soddalashgan (multipart/fayl/form qo'llab-quvvatlanmaydi, `{{var}}` boshqacha almashtiriladi).
  - `/saved/*`: `saved_requests.json` (`folders` + `requests`, papkalar faqat 1 daraja).
  - `/upload_temp`: `.tmp_uploads/` ga vaqtinchalik fayl.
- **Frontend imkoniyatlari:**
  - Tablar: Params (URL bilan ikki tomonlama sinxron), Auth (none/bearer/basic/custom), Headers, Body (none/raw/json/form/multipart).
  - cURL'ni import/export qilish, Postman collection import (flatten), collection runner (`/run_one` orqali ketma-ket), run'larni solishtirish, natijalarni JSON/CSV/TXT eksport qilish, response fullscreen, light/dark tema.
- **Ma'lumot saqlash:** environment'lar, tarix, URL tarixi va run tarixi brauzer `localStorage`'ida turadi (`apiRunnerEnvs`, `apiRunnerActiveEnvId`, `apiRunnerEnvVars`, `apiRunnerHistory`, `apiRunnerRunHistory`, `apiRunnerUrlHistory`, `apiRunnerTheme`). So'rovlar esa `saved_requests.json`'da.
- **Ma'lum muammolar:**
  - `job_worker` va `run_one` mantiqi takrorlangan.
  - Concurrency rejimida `completed` hisobi noto'g'ri bo'lishi mumkin (`index = max(...)`).
  - `form` body jadval sifatida emas, xom string sifatida yuboriladi.
  - Testlar umuman yo'q.
  - Variable scope'lar, skriptlar, cookie'lar, ichma-ich papkalar, bir nechta tab yo'q.
  - Fayl parametri diskdagi istalgan yo'lni o'qiy oladi.
  - Server Host/Origin tekshirmaydi (DNS rebinding / lokal SSRF xavfi).
- UI matnlari **o'zbek tilida** va shunday qolishi kerak.

## 2. Maqsad

Postman'ning foydalanuvchi har kuni ishlatadigan imkoniyatlarini to'liq qamrash, bunda tezlik va yengillikni saqlab qolish. Mavjud foydalanuvchi ma'lumotlari (`saved_requests.json` va localStorage) **yo'qolmasligi shart**.

## 3. Arxitektura bo'yicha qarorlar (Bosqich 1 da ADR sifatida yozib, asoslab ber)

1. **Monolitni bo'lish:**
   ```
   apirunner/
     core/        # HTTP engine, variable resolver, auth, scripting, runner
     storage/     # workspace, migratsiya
     api/         # Flask blueprints
     cli.py       # newman'ga o'xshash CLI
   web/           # frontend manba kodi
   apirunner/static/   # build qilingan frontend
   tests/
   ```
   `api_runner.py` faqat kirish nuqtasi bo'lib qoladi.
2. **Yagona request engine:** bitta so'rov, batch, collection runner va CLI — hammasi bitta `execute(request, context) -> result` funksiyasidan o'tadi.
3. **HTTP kutubxona:** `requests` o'rniga `httpx`'ni ko'rib chiq. U HTTP/2, proxy, client cert, cookie jar va event hook orqali timing beradi. Yakuniy qarorni asoslab ber.
4. **Ichki ma'lumot modeli:** Postman Collection **v2.1 formatining superseti**. Shunda import/export deyarli yo'qotishsiz bo'ladi.
5. **Saqlash:**
   - Collection, environment, globals: workspace papkasida JSON fayllar (git-friendly).
   - Tarix, run natijalari, cookie'lar: SQLite.
   - localStorage faqat UI sozlamalari uchun qoladi.
6. **Frontend:** Vite + Vue 3 + TypeScript + Pinia, muharrir uchun CodeMirror 6.
   - Build natijasi `apirunner/static/`'ga **commit qilinadi**, shunda `run.command` Node'siz ishlayveradi.
   - Agar vanilla JS'da qolishni asosliroq deb topsang, ADR'da tushuntir.
7. **Skript sandbox (`pm.*`):** testlar CLI va server runnerida ham ishlashi uchun skriptlar backendda bajarilishi kerak.
   - Ikki variantni spike qilib solishtir: Python `quickjs` va Node sidecar.
   - Sandbox'da fayl tizimi va tarmoqqa to'g'ridan-to'g'ri kirish bo'lmasin (faqat `pm.sendRequest`), vaqt va xotira limitlari bo'lsin.
   - `pm.expect` uchun chai bundle qilinadi.

## 4. Bosqichlar

Har bir bosqich: qisqa reja → implementatsiya → testlar → Playwright bilan qo'lda tekshirish → commit → `docs/ROADMAP.md` checklistini yangilash.

### Bosqich 0 — Xavfsiz boshlang'ich nuqta
- `feature/postman-level` branch'ini och.
- pytest'ni o'rnat. Hozirgi xatti-harakatni characterization testlar bilan qotir: `/run`, `/run_one`, `/saved/*`, `replace_variables`, cURL parse. Test serveri sifatida lokal echo server (masalan Flask fixture) ishlat.
- Playwright smoke test yoz: sahifa ochiladi, GET yuboriladi, natija ko'rinadi.
- `docs/ROADMAP.md` yarat (shu bosqichlar checklist sifatida).

### Bosqich 1 — Refaktor va poydevor ⛔ (tugagach TO'XTA va hisobot ber)
- Monolitni 3-bo'limdagi tuzilmaga ko'chir. Yagona engine yoz, `job_worker`/`run_one` dublikatini yo'qot, concurrency hisobini tuzat.
- Ma'lumot modelini kirit: Workspace → Collection → ichma-ich Folder → Request (+ Examples), Environment, Globals.
- Migratsiya:
  - `saved_requests.json`'dan avtomatik, eski fayldan `.bak` zaxira nusxa olib.
  - localStorage'dan bir martalik import (UI'da tugma, ma'lumot backendga POST qilinadi).
- Xavfsizlik:
  - Faqat `127.0.0.1` / `localhost` Host header'larini qabul qil.
  - Ishga tushganda tasodifiy session token yarat va har bir API chaqiruvida tekshir.
  - Fayl yuklashni workspace / `.tmp_uploads` yoki foydalanuvchi aniq tanlagan fayllar bilan cheklash siyosatini kirit.
- ADR'larni `docs/adr/` ga yoz.
- Frontendni yangi stackka ko'chirish shu bosqichda boshlanadi. Avval mavjud funksiyalar 1:1 qayta ishlashi kerak, keyin yangi funksiyalar qo'shiladi.

### Bosqich 2 — Asosiy so'rov imkoniyatlari
- **Multi-tab (majburiy):**
  - Bir vaqtda istalgan sonda so'rov tab'da ochiladi. Sidebar'da bir marta bosilsa — preview tab (kursiv, keyingi bosishda almashadi), ikki marta bosilsa yoki tahrirlansa — doimiy tab.
  - Har tabning holati (URL, params, body, auth, skriptlar, oxirgi javob, scroll) mustaqil saqlanadi. Tablar orasida o'tganda hech narsa yo'qolmaydi.
  - Dirty-indikator (●). Saqlanmagan tabni yopishda "Saqlash / Saqlamaslik / Bekor qilish" dialogi chiqadi.
  - Tab kontekst menyusi: Dublikat, Yopish, Boshqalarini yopish, O'ngdagilarni yopish, Hammasini yopish, Collection'da ko'rsatish.
  - Tablarni drag&drop bilan qayta tartiblash. Ko'p tab bo'lsa gorizontal scroll va "barcha tablar" dropdown'i.
  - Ochiq tablar va faol tab sahifa yangilanganda va server qayta ishga tushganda tiklanadi.
  - Yorliqlar: Cmd+T — yangi tab, Cmd+W — yopish, Ctrl+Tab / Ctrl+Shift+Tab — keyingi/oldingi, Cmd+Shift+T — yopilganini qayta ochish.
  - Bir xil so'rov ikkinchi marta ochilsa, yangi tab ochilmaydi, mavjudiga o'tiladi.
  - Environment, collection va runner ham tab sifatida ochiladi (Postman'dagidek).
- **Sidebar va drag&drop (majburiy):**
  - Ichma-ich papkalar (cheklanmagan chuqurlik), collapse/expand holati saqlanadi.
  - Drag&drop: so'rovni papkalar va collection'lar orasida ko'chirish, so'rov va papkalarni bir papka ichida qayta tartiblash, papkani boshqa papka ichiga ko'chirish.
  - Tushish joyi ko'rsatkichi (oldiga / ichiga / keyiniga), papka ustida biroz ushlab turilsa avtomatik ochiladi, uzun ro'yxatda chetga yaqinlashganda avtomatik scroll.
  - Papkani o'z ichidagi papkaga tashlash taqiqlanadi.
  - Alt/Option bilan sudralsa — ko'chirish o'rniga nusxa olinadi.
  - Tartib (`order`) backendda saqlanadi va export'da ham saqlanib qoladi.
  - Ko'p tanlash (Shift/Cmd + click) va bir nechta elementni birga sudrash.
  - Runner'dagi so'rovlar ro'yxati va params/headers/form-data qatorlari ham drag&drop bilan tartiblanadi.
  - Fayllarni (Postman collection, OpenAPI, CSV, cURL matni) oynaga sudrab tashlash orqali import qilish.
  - Klaviatura bilan ham ko'chirish mumkin bo'lsin (accessibility): masalan, kontekst menyudagi "Ko'chirish..." orqali.
  - Qidiruv (filtr) faol bo'lganda ham to'g'ri ishlasin.
- **Collection/folder darajasidagi sozlamalar:** Auth, Variables, Scripts, Description — meros bo'yicha ishlaydi.
- **Variable scope'lar** (Postman tartibida): Global → Collection → Environment → Data → Local.
  - `{{var}}` hamma joyda ishlasin: URL, path, params, headers, body, auth.
  - Hover qilganda qiymat va scope ko'rinsin, aniqlanmagan o'zgaruvchi qizil bo'lsin.
  - Path variables `:id`.
  - Dinamik o'zgaruvchilar: `{{$guid}}`, `{{$timestamp}}`, `{{$isoTimestamp}}`, `{{$randomInt}}`, `{{$randomEmail}}` va boshqalar.
  - Secret tipidagi o'zgaruvchilar maskalansin.
- **Auth:** No auth, Inherit, API Key (header/query), Bearer, Basic, Digest, OAuth 2.0, AWS SigV4, JWT generator.
  - OAuth 2.0 grant'lari: Client Credentials, Password, Authorization Code + PKCE, Implicit.
  - Token olish, saqlash va avtomatik yangilash bo'lsin.
- **Body:**
  - none, form-data (matn + fayl, har bir qator yoqiladi/o'chiriladi)
  - x-www-form-urlencoded jadval
  - raw (JSON/XML/Text/HTML/JS)
  - binary fayl
  - GraphQL (query + variables)
- **Har bir qatorda checkbox** (params, headers, form): yoqilgan/o'chirilgan holat, tavsif, bulk edit rejimi.
- **Sozlamalar** (global va har bir so'rov uchun): timeout, SSL verify, redirect'larga ergashish/maksimal soni, HTTP/2, proxy (system/custom), client sertifikatlari (domen bo'yicha), CA bundle.
- **Cookie'lar:** avtomatik cookie jar, domenlar bo'yicha Cookie Manager UI.
- **Response paneli:**
  - Pretty/Raw/Preview rejimlari: HTML sandboxed iframe'da, rasm, PDF.
  - Header'lar, cookie'lar, Test natijalari tabi.
  - Status, vaqt va hajm; timing breakdown (DNS/connect/TLS/TTFB) — imkon qadar.
  - Qidiruv, JSONPath/JMESPath filtr, katta javoblarni virtual scroll bilan ko'rsatish (500 KB'da kesish o'rniga).
  - Faylga saqlash, "Save as Example".
- **Code snippet generatori:** cURL, Python requests, JS fetch, axios, Node, Go, PHP, Java OkHttp, C# HttpClient.
- **Tarix:** server tomonda saqlanadi, sana bo'yicha guruhlanadi, qidiruv, tarixdan collection'ga saqlash.

### Bosqich 3 — Skriptlar va testlar
- Pre-request va Post-response (Tests) skriptlari: collection → folder → request darajalarida, meros tartibida bajariladi.
- `pm` API kichik to'plami:
  - `pm.environment` / `pm.collectionVariables` / `pm.globals` / `pm.variables` (`get`/`set`/`unset`/`has`)
  - `pm.request` (o'qish va o'zgartirish)
  - `pm.response` (`code`, `status`, `headers`, `json()`, `text()`, `responseTime`)
  - `pm.test`, `pm.expect` (chai), `pm.sendRequest`
  - `pm.execution.setNextRequest` / `skipRequest`, `pm.info`, `console.log`
- Mashhur kutubxonalar: `lodash`, `moment` yoki `dayjs`, `CryptoJS`, `atob`/`btoa`.
- UI:
  - CodeMirror'da `pm.*` avtoto'ldirish
  - tayyor snippet'lar paneli ("Status 200", "Set env from response" va h.k.)
  - Console paneli: so'rov/javob loglari va `console.log`
- Postman'dan import qilingan skriptlar o'zgarishsiz ishlashi kerak.

### Bosqich 4 — Collection Runner v2
- Collection yoki folder tanlanadi. So'rovlarni belgilash va tartibini o'zgartirish mumkin.
- Runner sozlamalari: iteratsiyalar soni, data fayl (CSV/JSON, oldindan ko'rish bilan), delay, environment, keep variable values, birinchi xatoda to'xtash, `setNextRequest` oqimi.
- Mavjud batch rejimi (bitta so'rov × CSV qatorlari, concurrency/retry) saqlansin va runnerga integratsiya qilinsin.
- Natijalar:
  - real-time SSE
  - har iteratsiya va har so'rov bo'yicha testlar
  - filtrlar
  - SQLite'da saqlash
  - eksport: JSON, HTML report, JUnit XML
  - run'larni solishtirish (mavjud funksiya kengaytiriladi)

### Bosqich 5 — Import/Export
- **Import:**
  - Postman Collection v2.0/v2.1 to'liq: ichma-ich papkalar, auth, skriptlar, o'zgaruvchilar, example'lar, description
  - Postman environment va globals
  - OpenAPI 3.x / Swagger 2.0 (JSON/YAML, fayl yoki URL)
  - Insomnia v4, HAR, cURL (bir nechta)
- **Export:** Postman v2.1 collection va environment, OpenAPI (asosiy), butun workspace zaxirasi.
- Har bir importer uchun real namunaviy fayllar bilan round-trip testlar yoz.

### Bosqich 6 — Boshqa protokollar
- **GraphQL:** schema introspection, avtoto'ldirish, schema explorer.
- **WebSocket:** ulanish, xabar yuborish va qabul qilish, saqlangan xabarlar.
- **SSE** (Server-Sent Events) klienti.
- **Socket.IO** (ixtiyoriy).
- **gRPC:** proto yuklash, unary chaqiruvlar (oxirgi navbatda, ixtiyoriy).

### Bosqich 7 — Kengaytirilgan imkoniyatlar
- **CLI (newman analogi):**
  ```
  apirunner run collection.json -e env.json -d data.csv -n 3 --reporters cli,json,junit,html
  ```
  Xatoda exit code 1 qaytarsin (CI uchun).
- **Mock server:** collection example'lari asosida, lokal port, URL va method bo'yicha mos javob qaytaradi.
- **Collection hujjatlari:** description'lar va example'lardan HTML docs generatsiyasi.
- **Global qidiruv** (Cmd+K) va klaviatura yorliqlari: Cmd+Enter — yuborish, Cmd+S — saqlash, Cmd+T — yangi tab, Cmd+W — tabni yopish.
- **Paketlash:** `pyproject.toml`, `pipx install` va `apirunner` buyrug'i. Ixtiyoriy: macOS `.app` (PyInstaller yoki pywebview).

### Bosqich 8 — Sayqal va sifat
- **Ishlash tezligi:** 1000+ so'rovli collection, 10 MB javob, 10 000 qatorli data fayl bilan UI qotmasligi kerak.
- **UX:** bo'sh holatlar, xato xabarlari, undo (o'chirishda), light/dark tema izchilligi, o'zbekcha matnlar.
- **Hujjatlar:** README'ni yangilash, `docs/` da foydalanuvchi qo'llanmasi va arxitektura sxemasi.

## 5. Ish qoidalari

1. **Mavjud funksiyani buzma.** Har bosqich oxirida barcha testlar yashil va smoke test o'tgan bo'lishi kerak.
2. **Foydalanuvchi ma'lumotlari muqaddas.** `saved_requests.json`'ni o'chirma va commit qilma (u `.gitignore`'da). Har qanday migratsiyadan oldin zaxira nusxa ol.
3. **Kichik va mantiqiy commit'lar** yoz. Xabarlari inglizcha, `feat:` / `fix:` / `refactor:` / `test:` / `docs:` prefikslari bilan.
4. **Tashqi tarmoqqa bog'liq testlar yozma.** Lokal echo/mock server fixture ishlat.
5. **Yangi bog'liqliklarni minimal tut.** Har biri `requirements.txt` / `pyproject.toml`'ga qo'shilsin. Frontend build natijasi commit qilinsin.
6. **`run.command` va `python3 api_runner.py` doim ishlashi kerak.**
7. **Noaniq qaror bo'lsa:** Postman qanday qilsa, shunday qil. Postmandan chetga chiqsang, ADR'da sababini yoz.
8. **Har bosqich oxirida qisqa hisobot ber:** nima qilindi, qanday testlar qo'shildi, ma'lum cheklovlar, keyingi bosqich rejasi.
9. **Bosqich 1 dan keyin to'xta va tasdiq kut** (arxitektura va frontend stack qarorlari). Keyingi bosqichlarni ketma-ket davom ettirish mumkin, lekin har biri oxirida hisobot berilsin.

## 6. "Tayyor" mezoni (Definition of Done)

- Postman'dan eksport qilingan real collection (ichma-ich papkalar, collection auth, pre-request va test skriptlari, environment bilan) import qilinadi. Uni UI runnerda ham, CLI'da ham Postman bilan bir xil natija va testlar bilan ishga tushirish mumkin.
- Mavjud batch rejimi (CSV × so'rov, concurrency, retry, stop) avvalgidek ishlaydi.
- Multi-tab va drag&drop 2-bosqichdagi barcha bandlari bo'yicha ishlaydi va Playwright e2e testlari bilan qoplangan (tab holati tiklanishi, dirty-dialog, papkalar orasida ko'chirish, tartibning saqlanishi).
- Eski `saved_requests.json` va localStorage'dagi environment hamda tarix yangi tizimga ko'chirilgan.
- `pytest` va Playwright e2e testlari yashil, `docs/ROADMAP.md`'dagi barcha bandlar belgilangan.
