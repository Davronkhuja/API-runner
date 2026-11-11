# API Runner — foydalanuvchi qo'llanmasi

Lokal API klient (Postman'ga o'xshash): hamma ma'lumot faqat sizning kompyuteringizda. Interfeys o'zbekcha.

**Mundarija:** [1. Ishga tushirish](#1-ishga-tushirish) · [2. Interfeys](#2-interfeys-bilan-tanishuv) · [3. So'rov yuborish](#3-sorov-yuborish) · [4. Muhitlar](#4-ozgaruvchilar-va-muhitlar) · [5. Collection](#5-collection-papka-example-hujjat) · [6. Runner](#6-collection-runner-csv-bilan) · [7. Import/Eksport](#7-import-va-eksport) · [8. WebSocket, SSE, GraphQL](#8-websocket-sse-va-graphql) · [9. Skriptlar](#9-skriptlar-va-console) · [10. Savat va Find&Replace](#10-savat-va-find--replace) · [11. Workspace'lar](#11-bir-nechta-workspace) · [12. Mock](#12-mock-server) · [13. Hujjat](#13-hujjat-generatsiyasi) · [14. Monitor](#14-monitor-rejalashtirilgan-runlar) · [15. Proxy](#15-proxy-capture) · [16. CLI](#16-cli-apirunner-run) · [17. Yorliqlar](#17-klaviatura-yorliqlari) · [18. Xavfsizlik](#18-xavfsizlik-va-malumotlar) · [19. Muammolar](#19-muammolarni-hal-qilish)

---

## 1. Ishga tushirish
- **macOS:** `./run.command` (Finder'da ikki marta bosish) — `.venv` yaratadi, bog'liqliklarni o'rnatadi, `http://127.0.0.1:5050` ni brauzerda ochadi.
- **Doimiy (PM2):** `pm2 start ecosystem.config.js` (nom `api-runner`). Yangilangach ilovaning pastki qatoridagi **«Qayta ishga tushirish»** tugmasi yoki `pm2 restart api-runner`.
- **Alohida oyna (.app):** `packaging/build_macos_app.sh` — Dock ikonkali macOS ilovasi (pywebview); batafsil `packaging/README.md`.
- **Buyruq qatori:** `pipx install .` → `apirunner` ([16-bo'lim](#16-cli-apirunner-run)).

Birinchi ochilishda qisqa **tanishtiruv** chiqadi (3 qadam, «O'tkazib yuborish» mumkin). Qayta ko'rish: brauzer manzilining oxiriga `?onboarding=1` qo'shing.

## 2. Interfeys bilan tanishuv
![Bosh sahifa](img/welcome.png)

- **Yuqori qator:** workspace almashtirgich, qidiruv (⌘K), Import, muhit tanlagich, «ko'z» (o'zgaruvchilarni tez ko'rish), tema, sozlamalar.
- **Chap panel:** Kolleksiya · Muhitlar · Tarix · Runner. Sarlavhadagi asosiy tugmalar — yangi so'rov va yangi collection; **«⋯»** menyusida Savat, Find & Replace, klaviatura yorliqlari.
![Sidebar menyusi](img/sidebar-more.png)
- **Tablar:** har bir so'rov/muhit/sozlama alohida tab. ⌘T — yangi, ⌘W — yopish, ⌘⇧T — yopilganini qaytarish. Tablar qayta ochilganda saqlanadi.
- **Pastki qator:** server holati, Console, Monitor, Proxy, Cookie'lar, versiya.
- **⌘K** — so'rov, muhit va amallar bo'yicha tezkor qidiruv:
![⌘K](img/cmdk.png)

## 3. So'rov yuborish
«Yangi so'rov» (⌘T) → metod, URL → **Yuborish** (⌘↵). cURL buyrug'ini URL maydoniga joylashtirsangiz, parametrlar avtomatik to'ldiriladi.

![So'rov va javob](img/editor-simple-response.png)

Bo'limlar: **Params**, **Headers**, **Auth** (Bearer, Basic, API Key, JWT, Digest, OAuth 2.0, Hawk, AWS SigV4, NTLM va boshqalar; collection/papkadan meros), **Body** (JSON, matn, form-data, urlencoded, binary, GraphQL), **Scripts**, **Settings** (timeout, redirect, SSL va h.k.).

![Params](img/heavy-params.png)
![Auth](img/heavy-auth.png)

**Javob:** status, vaqt, hajm; Pretty/Raw/Preview; qidiruv; JSONPath filtri; Headers, Cookies, Tests tablari; 10 MB gacha JSON qotmasdan ko'rsatiladi (virtual scroll). Javobni faylga saqlash, **Example** sifatida saqlash mumkin.

Yozuvchi so'rovlar (POST/PUT/DELETE) **Prod** muhitda yuborilganda tasdiq so'raladi (muhit turi «prod» bo'lsa).

## 4. O'zgaruvchilar va muhitlar
`{{nom}}` — URL, header, body va auth'da. Yozishni `{{` bilan boshlasangiz, avtoto'ldirish chiqadi. Doira (scope): global → collection → muhit → lokal. Muhit o'zgaruvchisida **Initial** va **Current** qiymat bor (eksportga faqat Initial ketadi; Secret turidagilar yashiriladi).

![Muhit](img/env-tab.png)
![Quick look](img/env-eye.png)

Matnni belgilab **«Set as variable»** bilan o'zgaruvchi yarating. Dinamik: `{{$guid}}`, `{{$timestamp}}`, `{{$randomInt}}` va boshqalar.

## 5. Collection, papka, Example, hujjat
- Daraxtda sudrab ko'chirish (DnD), nomini o'zgartirish (F2/ikki marta bosish), nusxa, ko'chirish, ko'p tanlash.
- **Papka/Collection Overview:** statistika, meros auth, tavsif (Markdown), **Runner** va **Mock server**, **Hujjat yaratish** tugmalari.
![Overview](img/folder-overview-80.png)
- **Example** — saqlangan javob namunasi; daraxtda so'rov ostida ko'rinadi, alohida tabda tahrirlanadi (status, header, body). Mock server shulardan ishlaydi.
![Example'lar](img/tree-examples.png)
- **Docs paneli:** so'rov/papka/collection tavsifi Markdown'da (xavfsiz render: xom HTML o'tmaydi).
![Docs](img/docs-panel.png)
- **Tarix:** har yuborilgan so'rov; kengaytirilgan tarixda javoblarni solishtirish (diff).
![Tarix](img/history-drawer.png)

## 6. Collection Runner (CSV bilan)
Collection yoki papka menyusi → **Runner**: iteratsiyalar soni, **CSV/JSON ma'lumot fayli** (har qator — bitta iteratsiya, ustun nomi = o'zgaruvchi), kechikish, qayta urinish, xatoda to'xtash. 10 000 qatorli CSV bilan ham UI barqaror ishlaydi.

![Runner natijalari](img/runner-results.png)

Har run «run #N» sifatida saqlanadi; ikki runni **solishtirish**, JSON/HTML/JUnit **eksport**:
![Solishtirish](img/runner-compare.png)

## 7. Import va eksport
**Import** (header → Import, yoki faylni oynaga tashlang): Postman collection/muhit/globals, OpenAPI 3 / Swagger 2 (JSON/YAML), Insomnia, HAR, cURL, workspace zip. Natija oldindan ko'rsatiladi, nom to'qnashuvida «nusxa / birlashtirish / almashtirish (eskisi Savatga) / o'tkazib yuborish» tanlanadi.
![Import](img/import-multi.png)

**Eksport:** collection — Postman v2.1 yoki OpenAPI; muhit; butun workspace — zip (sukut bo'yicha maxfiylarsiz, ixtiyoriy parol bilan AES-256 shifrlash).
![Eksport](img/export-dialog.png)

## 8. WebSocket, SSE va GraphQL
Metod tanlagichidan **WS** yoki **SSE** ni tanlang: ulanish serverning o'zida ochiladi (header/auth/subprotokol), xabarlar oqimi filtr va qidiruv bilan, avtomatik qayta ulanish.

![WebSocket](img/ws-session.png)
![SSE](img/sse-session.png)

**GraphQL:** Body → GraphQL; **Introspection** (sxema diskda keshlanadi), schema explorer, sxemaga asoslangan avtoto'ldirish va xatolarni tekshirish.
![GraphQL](img/graphql-explorer.png)

## 9. Skriptlar va Console
Pre-request va Tests skriptlari (Postman `pm.*` API: `pm.test`, `pm.expect`, `pm.environment`, `pm.sendRequest`, `setNextRequest` va h.k.) xavfsiz sandbox (quickjs) ichida ishlaydi — fayl/tarmoq/jarayonga kirish yo'q; vaqt va xotira chegaralari Sozlamalar → Skriptlar da.

![Skriptlar](img/heavy-scripts.png)

**Console** (pastki qator): `console.log`, skript xatolari, qo'llab-quvvatlanmaydigan API ogohlantirishlari.
![Console](img/console.png)

## 10. Savat va Find & Replace
Hech narsa to'g'ridan-to'g'ri o'chirilmaydi: so'rov, papka, collection, muhit va workspace **Savat**ga tushadi va **30 kun** saqlanadi (sidebar «⋯» → Savat; tiklash yoki butunlay o'chirish).
![Savat](img/trash-dialog.png)

**Find & Replace** workspace bo'ylab (URL, header, body, o'zgaruvchi): oldindan ko'rish va avtomatik zaxira bilan.
![Find & Replace](img/find-replace.png)

## 11. Bir nechta workspace
Yuqori chapdagi nom → **workspace almashtirgich**: yangi yaratish, nomini o'zgartirish, almashtirish, o'chirish (Savatga). Har biri alohida papka va alohida tarix bazasiga ega. Faol run/mock/ulanish bo'lsa, almashtirishdan oldin tasdiq so'raladi.
![Workspace menyusi](img/ws-menu.png)

## 12. Mock server
Collection menyusi (yoki Overview) → **Mock server…**: Example'lar asosida metod + yo'l (`:id`, `{{var}}`) + ixtiyoriy query/header bo'yicha moslab javob qaytaradi. Port tanlanadi (bo'sh — avtomatik), qo'shimcha kechikish; Example sarlavhasidagi `X-Mock-Delay` — alohida kechikish. So'rovlar jurnali real vaqtda.
![Mock](img/mock-dialog.png)

## 13. Hujjat generatsiyasi
Collection/papka Overview → **«Hujjat yaratish»**: tavsiflar va Example'lardan bitta o'z-o'zidan yetarli HTML fayl. CLI: `apirunner docs collection.json -o docs.html`.

## 14. Monitor (rejalashtirilgan run'lar)
Pastki qator → **Monitor**: collection/papka/muhit va **cron** ifoda (`*/5 * * * *` — har 5 daqiqa; `0 9 * * mon-fri` — ish kunlari 09:00). Xatoda macOS bildirishnomasi; natijalar Runner tarixida `monitor` turi bilan. «Hozir» — darhol yurgizish. Ilova (PM2) ishlab turganda ishlaydi.
![Monitor](img/monitor-dialog.png)

## 15. Proxy capture
Pastki qator → **Proxy**: lokal HTTP proxy ishga tushadi; ilova/brauzerni `http://127.0.0.1:<port>` proxy'ga yo'naltiring, o'tgan **HTTP** so'rovlar ro'yxatda ko'rinadi; tanlanganlarni collection'ga (javob namunasi bilan) saqlang. HTTPS faqat tunnel qilinadi (ichi ko'rinmaydi).
![Proxy](img/proxy-dialog.png)

## 16. CLI (`apirunner run`)
```bash
apirunner run collection.json -e dev.postman_environment.json -d data.csv -n 3 \
  --reporters cli,json,junit,html --export-dir reports --bail --delay 200
apirunner run "Mening collection" --folder Shartnomalar -e Dev     # workspace'dagi collection
apirunner mock collection.json --port 3000
apirunner docs collection.json -o docs.html
```
Xatoda **exit code 1** (CI uchun); `--fail-on-http-errors` — 4xx/5xx ham xato. CI misoli — README'da.

## 17. Klaviatura yorliqlari
**?** tugmasi (yoki sidebar «⋯» → Klaviatura yorliqlari) ro'yxatni ochadi:
![Yorliqlar](img/shortcuts-dialog.png)

| Amal | Yorliq |
|---|---|
| Yangi so'rov / yopish / qaytarish | ⌘T / ⌘W / ⌘⇧T |
| Yuborish / saqlash | ⌘↵ / ⌘S |
| Qidiruv va buyruqlar | ⌘K |
| Keyingi tab | ⌃Tab |
| Yorliqlar | ? |
| Dialog/menyuni yopish | Esc |

## 18. Xavfsizlik va ma'lumotlar
- Server faqat `127.0.0.1` da; har ishga tushishda tasodifiy sessiya tokeni; Host/Origin tekshiriladi ([docs/security-review.md](security-review.md)).
- Ma'lumot `workspace/` papkasida (JSON, Postman v2.1 superseti) va `state.db` (tarix, run natijalari). **Avtomatik zaxira** (`backups/`, oxirgi 20 ta), atomik yozuv, migratsiyada rollback. Sozlamalar → Zaxira orqali tiklash.
- Maxfiy qiymatlar (Secret, Current, token) eksport va jurnalga sukut bo'yicha chiqmaydi.
- Hech narsa qaytarib bo'lmas tarzda o'chirilmaydi — Savat (30 kun).

## 19. Muammolarni hal qilish
| Holat | Yechim |
|---|---|
| Sahifa ochilmayapti | `pm2 ls` / `./run.command`; port 5050 band bo'lsa `APIRUNNER_PORT` bilan boshqa port |
| «Server eskirgan» chizig'i | Pastki qatordagi «Qayta ishga tushirish» |
| Skript ishlamayapti («quickjs-ng yo'q») | `.venv/bin/pip install quickjs-ng` (yoki `pipx install ".[scripts]"`) |
| Monitor ishlamayapti | Ilova ochiq/PM2 ishlab turishi kerak; cron ifodani tekshiring |
| Mock porti band | Boshqa port tanlang |
| Tasodifan o'chirdim | Sidebar «⋯» → Savat → Tiklash |
| Eski holatga qaytish | Sozlamalar → Zaxira nusxalar → Tiklash |
