# ⚡ API Runner

> Postman Runner-ga o'xshash, lekin yengil va tez — CSV/JSON fayldan ma'lumot olib, har bir qatorni API ga donalab yuboradi va natijalarni real vaqtda ko'rsatadi.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0+-000000?style=flat-square&logo=flask&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)

---

## Imkoniyatlar

| | |
|---|---|
| **Batch yuborish** | CSV yoki JSON fayldan ma'lumot olib, har bir qatorni API ga donalab yuboradi |
| **`{{o'zgaruvchi}}`** | URL, header va body ichidagi o'zgaruvchilarni avtomatik almashtiradi |
| **Real-time natijalar** | Server-Sent Events (SSE) orqali har bir so'rov natijasi darhol ko'rinadi |
| **CURL parse** | URL maydoniga CURL buyrug'ini joylashtiring — barcha parametrlar avtomatik to'ldiriladi |
| **Fayl ixtiyoriy** | Faylsiz ham bitta so'rov yuborish mumkin |
| **Saqlangan so'rovlar** | So'rovlarni papkalar bilan tartiblab saqlash, qidirish imkoni |
| **Split-pane interfeys** | Natijalar o'ng panelda ochiladi, ajratuvchini sudrab o'lcham o'zgartirish mumkin |
| **RUN / STOP** | Istalgan vaqtda batch jarayonni to'xtatish imkoni |

---

## O'rnatish va ishga tushirish

```bash
git clone https://github.com/Davronkhuja/API-runner.git
cd API-runner
```

**macOS** — Finder da `run.command` faylini ikki marta bosing (yoki terminalda `./run.command`). U o'zi:

1. loyiha ichidagi `.venv` ni ishlatadi, yo'q bo'lsa `python3 -m venv .venv` bilan yaratadi;
2. `requirements.txt` o'zgargan bo'lsa `.venv/bin/python -m pip install -r requirements.txt` ni bajaradi (pip xabarlari yashirilmaydi; xato bo'lsa tushunarli xabar chiqadi va oyna **Enter** bosilguncha yopilmaydi);
3. port (sukut `5050`) bandligini tekshiradi: band qilgan jarayon **bizning eski API Runner** bo'lsa to'xtatadi; **boshqa dastur** bo'lsa uni o'ldirmasdan ogohlantiradi (`APIRUNNER_PORT=5051 ./run.command` bilan boshqa port tanlash mumkin);
4. `API RUNNER v2.x.y` deb versiyani chiqaradi va brauzerni ochadi (`http://127.0.0.1:5050`). Terminal oynasini yopsangiz — server to'xtaydi.

**Qo'lda (har qanday OS):**
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python api_runner.py
```

### PM2 bilan doimiy ishga tushirish

Repoda `ecosystem.config.js` bor: u `api-runner` nomli ilovani loyiha ichidagi `.venv/bin/python` bilan, `cwd` = loyiha papkasi, `APIRUNNER_PORT=5050` va `APIRUNNER_NO_BROWSER=1` (PM2 ostida brauzer ochilmaydi) bilan ishga tushiradi.

```bash
./run.command                       # bir marta: .venv va kutubxonalar tayyor bo'ladi (yoki qo'lda yuqoridagi buyruqlar)
pm2 start ecosystem.config.js       # ishga tushirish
pm2 save                            # qayta yuklashdan keyin tiklanishi uchun
pm2 restart api-runner              # yangi kod/versiyadan keyin (git pull / yangilashdan keyin MAJBURIY)
pm2 logs api-runner                 # jurnal
```

**Yangilashdan keyin restart kerak — endi UI'dan:** "Server eski" ogohlantirishidagi **Qayta ishga tushirish** tugmasi serverni xavfsiz to'xtatadi (faol run bo'lsa tasdiq so'raydi), PM2 uni yangi kod bilan ko'taradi va sahifa o'zi yangilanadi. PM2 ostida bo'lmasa (`run.command`) tugma o'rniga ko'rsatma chiqadi. Qo'lda: `pm2 restart api-runner`.

**Eski eslatma.** UI statik fayllari diskdan darhol yangilanadi, lekin Python serveri xotirada eski kodda qoladi. Status bar'da UI va server versiyalari farq qilsa "Server eski — pm2 restart api-runner" ogohlantirishi chiqadi.

Portni o'zgartirish: `ecosystem.config.js` dagi `APIRUNNER_PORT` ni tahrirlang, so'ng `pm2 restart api-runner --update-env`.

`run.command` PM2 ostidagi `api-runner` ni taniydi: port shu jarayon tomonidan band bo'lsa uni **to'xtatmaydi**, balki `pm2 restart api-runner` bajarilsinmi deb so'raydi (terminal bo'lmasa faqat buyruqni ko'rsatadi).

Skriptlar (pre-request / tests, `pm.*`) uchun ixtiyoriy `quickjs-ng` kerak (`requirements-scripts.txt`; `run.command` o'zi o'rnatadi, o'rnatilmasa skriptlar o'chiq bo'ladi): `.venv/bin/python -m pip install -r requirements-scripts.txt`.

Muhit o'zgaruvchilari: `APIRUNNER_PORT`, `APIRUNNER_WORKSPACE`, `APIRUNNER_NO_BROWSER=1`, `APIRUNNER_VENV_ARGS` (venv yaratishga qo'shimcha argument).
Node.js kerak emas — frontend build natijasi (`apirunner/static/app/`) repoga kiritilgan.

---

## Ishlatish

### Oddiy so'rov

1. Method (`GET`, `POST`, `PUT`...) va URL kiriting
2. Kerak bo'lsa **Params**, **Headers**, **Auth** yoki **Body** tablarini to'ldiring
3. **▶ RUN** tugmasini bosing

### Bosqich 8 (v3.0.0): sayqal va sifat
- **To'liq o'zbekcha qo'llanma:** [docs/user-guide.md](docs/user-guide.md) (skrinshotlar bilan).
- **Klaviatura yorliqlari:** `?` tugmasi; birinchi ishga tushirishda qisqa tanishtiruv.
- **Ishlash:** [docs/performance.md](docs/performance.md) — 1200 so'rovli collection, 9 MB JSON, 10 000 qatorli CSV, 50 tab.
- **Xavfsizlik:** [docs/security-review.md](docs/security-review.md).
- **macOS ilovasi (alohida oyna):** `packaging/build_macos_app.sh` → `dist/API Runner.app` ([packaging/README.md](packaging/README.md)).

### Bosqich 7 (v2.9.0): CLI, mock, hujjat, workspace'lar, monitor, proxy

**CLI (newman analogi).** O'rnatish: `pipx install .` (skriptlar uchun `pipx install ".[scripts]"`) — `apirunner` buyrug'i paydo bo'ladi.
```bash
apirunner run collection.json -e dev.postman_environment.json -d data.csv -n 3 \
  --reporters cli,json,junit,html --export-dir reports --bail --delay 200
apirunner run "Mening collection" --folder Shartnomalar -e Dev      # workspace'dagi collection (nom bo'yicha)
apirunner mock collection.json --port 3000                          # Example'lar asosida mock server
apirunner docs collection.json -o docs.html                         # statik HTML hujjat
```
Xato (test yiqilishi, so'rov xatosi) bo'lsa **exit code 1**, noto'g'ri argument — 2. `--fail-on-http-errors` — 4xx/5xx ham xato hisoblanadi.

**CI misoli (GitHub Actions):**
```yaml
jobs:
  api-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pipx install "git+https://github.com/Davronkhuja/API-runner.git#egg=apirunner[scripts]"
      - run: apirunner run tests/api.postman_collection.json -e tests/ci.postman_environment.json --reporters cli,junit --export-dir reports
      - uses: actions/upload-artifact@v4
        if: always()
        with: { name: api-reports, path: reports }
```

- **Mock server:** collection menyusi → «Mock server…» — Example'lar asosida metod + yo'l (`:id`) + ixtiyoriy query/header bo'yicha javob; port va kechikish; so'rovlar jurnali.
- **Hujjat:** Folder/Collection Overview → «Hujjat yaratish» — tavsiflar va Example'lardan bitta HTML fayl.
- **Workspace'lar:** header'dagi nom → almashtirish, yangi workspace, nomlash, o'chirish (Savatga). Har biri alohida papka.
- **Monitor:** status-bardagi «Monitor» → cron (`*/5 * * * *`, `0 9 * * mon-fri`), xatoda macOS bildirishnomasi; natijalar Run tarixida (`monitor`). Ilova (PM2) ishlab turganda ishlaydi.
- **Proxy capture:** status-bardagi «Proxy» → lokal proxy; ilovangizni `http://127.0.0.1:<port>` proxy'ga yo'naltiring, ushlangan HTTP so'rovlarni collection'ga saqlang (HTTPS — faqat tunnel).

### Boshqa protokollar (v2.8.0)
Metod tanlagichidan **WS** (WebSocket) yoki **SSE** ni tanlang: ulanish serverning o'zida ochiladi (headers, auth, subprotokol), xabarlar oqimi filtr/qidiruv bilan, xabar shablonlari, avtomatik qayta ulanish, collection'ga saqlash. **GraphQL** — Body → graphql: «Sxemani yuklash», schema explorer, avtoto'ldirish va validatsiya.

### Import / Eksport (v2.7.0)
- **Import** (header, Sozlamalar → Import / Eksport, ⌘K): Postman collection v2.0/v2.1, Postman environment/globals, OpenAPI 3.x / Swagger 2.0 (JSON/YAML, fayl yoki URL), Insomnia v4, HAR, cURL (bir nechta), workspace zip. Oldindan ko'rish va nom to'qnashuvi: **Yangi nusxa / Birlashtirish / Almashtirish (eskisi Savatga) / O'tkazib yuborish**.
- **Eksport:** collection (sidebar menyusi yoki Overview → Eksport) — Postman v2.1 yoki OpenAPI 3.0 (JSON/YAML); muhit/globals — Postman (faqat Initial, maxfiylar bo'sh); butun workspace — zip zaxira (Sozlamalar → Import / Eksport): sukut bo'yicha maxfiy va Current qiymatlarsiz; ularni qo'shsangiz parol bilan shifrlash (AES-256) taklif etiladi, import paytida parol so'raladi.
- O'chirilgan hamma narsa (collection ham) **Savat**ga tushadi — 30 kun saqlanadi.

### Kundalik qulayliklar (v2.6.0)
- **`{{`** yozsangiz o'zgaruvchilar ro'yxati chiqadi (URL, Params, Headers, Body, Auth); matn belgilasangiz **{{ }} O'zgaruvchi qilish** tugmasi paydo bo'ladi.
- **Example'lar** so'rov ostida (chevron); **Docs** tugmasi — Markdown tavsif paneli.
- **Savat** (sidebar yoki ⌘K): o'chirilganlar 30 kun saqlanadi. **Find & Replace** (sidebar yoki ⌘K): butun workspace bo'ylab, almashtirishdan oldin avtomatik zaxira.
- **Yuborish ▾ → Yuborish va yuklab olish**. Auth: JWT RS/PS/ES (PEM kalit), Hawk, NTLM (`cryptography` `requirements.txt` da).

### Runner v2 (v2.5.0)
Collection/papka kontekst menyusidan **Runner**: chapda yagona "Run sozlamalari" paneli (iteratsiyalar, kechikish, parallel, retry, timeout, muhit, CSV/JSON data fayl, "o'zgaruvchi qiymatlarini saqlash", "birinchi xatoda to'xtash", "javoblarni saqlash"), o'ngda real-time natijalar jadvali (Testlar ustuni), `run #N` tarixi, "Avvalgi run bilan solishtirish" va Eksport (JSON/HTML/JUnit). Hisoblash serverda, natijalar `workspace/state.db` (SQLite) da — sahifa yangilangach ham saqlanadi. So'rovdagi **Batch** shu panel va shu engine'dan foydalanadi.

### Batch yuborish (Runner rejimi)

1. CSV yoki JSON fayl yuklang
2. URL, header yoki body ichida `{{ustun_nomi}}` yozing
3. **▶ RUN** — har bir satr uchun alohida so'rov yuboriladi

**CSV misol:**
```csv
user_id,token
101,abc123
102,def456
```

**URL misol:**
```
https://api.example.com/users/{{user_id}}
```

**Body misol:**
```json
{
  "id": "{{user_id}}",
  "auth": "{{token}}"
}
```

### CURL paste

URL maydoniga to'liq CURL buyrug'ini joylashtiring — method, headerlar, body va auth avtomatik aniqlanadi:

```bash
curl -X POST 'https://api.example.com/data' \
  -H 'Authorization: Bearer mytoken' \
  -H 'Content-Type: application/json' \
  -d '{"key": "value"}'
```

### So'rovlarni saqlash

- Sidebar dagi **+ Yangi so'rov** orqali so'rovni saqlang
- **📁 Papka** tugmasi bilan papkalar yarating va so'rovlarni tartiblab joylashtiring
- Keyingi safar bir bosish bilan qayta yuklang

---

## Texnologiyalar

- **Backend:** Python 3 / Flask
- **Real-time:** Server-Sent Events (SSE)
- **Frontend:** Vanilla JS + CSS (framework yo'q, zero dependencies)
- **Saqlash:** `saved_requests.json` (lokal fayl)

---

## Fayl tuzilmasi

```
API-tester/
├── api_runner.py        # Asosiy fayl (backend + frontend)
├── requirements.txt     # Python kutubxonalari
├── saved_requests.json  # Saqlangan so'rovlar (gitignore'd)
└── README.md
```

## Tuzilma (v0.2, Bosqich 1)

```
api_runner.py      # kirish nuqtasi:  python3 api_runner.py  (yoki run.command)
apirunner/         # core (engine, runner) · storage (workspace, SQLite, migratsiya) · api · static (UI)
workspace/         # sizning ma'lumotingiz: collection/environment JSON + state.db (git'ga kirmaydi)
docs/adr/          # arxitektura qarorlari, docs/ROADMAP.md — reja
tests/             # pytest + Playwright
```

- Birinchi ishga tushishda `saved_requests.json` avtomatik `workspace/` ga ko'chiriladi; zaxira `saved_requests.json.bak`, asl fayl o'zgarmaydi.
- Brauzer (localStorage) ma'lumotlarini serverga ko'chirish: sarlavhadagi **⇪** tugmasi (bir martalik, qayta bosish xavfsiz).
- Server faqat `127.0.0.1`/`localhost` Host'larini qabul qiladi va har chaqiruvda sessiya tokenini tekshiradi.
- Fayl parametrlari (📎) faqat `.tmp_uploads/` va workspace ichidan o'qiladi.
- Env: `APIRUNNER_WORKSPACE` (workspace joyi), `APIRUNNER_PORT` (sukut 5050), `APIRUNNER_NO_BROWSER=1`.

### Testlar
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/playwright install chromium
.venv/bin/python -m pytest              # hammasi, 4 jarayonda parallel (~1 daqiqa); har bir test 90 s bilan cheklangan
.venv/bin/python -m pytest -n 0 -k nom  # bitta testni ketma-ket (debug)
.venv/bin/python -m pytest tests/e2e/test_redesign.py   # bitta fayl
(cd web && npm ci && npx vitest run)    # frontend unit testlar (Node.js faqat frontend ishlab chiqish uchun)
```
**UI sifat himoyasi (v2.4.0):** `tests/e2e/test_visual_regression.py` (15 ekran × light/dark `docs/screenshots/baseline/` bilan; ataylab dizayn o'zgargach `UPDATE_BASELINE=1 .venv/bin/python -m pytest tests/e2e/test_visual_regression.py`), `tests/e2e/test_layout_guards.py` (dialog viewport'dan oshmasligi, kesilgan matn, ≥24px nishon, axe serious/critical=0), `tools/check_fixed_heights.py` (kontent konteyneri uchun qat'iy `height:NNNpx` taqiqi; ruxsat — `tools/fixed_heights_allow.txt`). To'liq UI audit: `python3 tools/ui_audit.py --out /tmp/ui-audit` → `python3 tools/ui_audit_report.py /tmp/ui-audit > docs/ui-audit.md`.

Skrinshotlar (light + dark, 1440×900) odatda vaqtinchalik papkaga yoziladi; `docs/screenshots/` ni yangilash: `SHOT_UPDATE=1 .venv/bin/python -m pytest tests/e2e/test_screenshots.py && .venv/bin/python tools/shots_readme.py`.
Frontend o'zgargan bo'lsa build qiling (natija repoga kiritiladi): `cd web && npm run build`.
