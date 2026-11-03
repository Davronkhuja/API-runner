# ADR 0007 — Skript sandbox (`pm.*`)

**Holat:** Qabul qilindi (Bosqich 3 spike, 2026-11-03) — **`quickjs-ng`** (Python, jarayon ichida)

## Kontekst
Pre-request / Tests skriptlari foydalanuvchi (va import qilingan begona collection) kodi. Talablar: `pm.*`, chai (`pm.expect`), lodash, CryptoJS, dayjs/moment, `atob`/`btoa`; vaqt va xotira limiti; **fayl tizimi va tarmoqqa (faqat `pm.sendRequest` orqali tashqari) kira olmasligi**; haqiqiy workspace'ni faqat `pm.*` orqali o'zgartirishi; `run.command` Node'siz ishlashi (AGENT_PROMPT qoidasi 6).

## Variantlar va o'lchovlar
Mashina: macOS arm64, Python 3.14.6, Node 24.8. Skriptlar: `docs/adr/0007-spike/`. Kutubxonalar: chai 4.5 (360 KB), lodash 4.18 (73 KB min), crypto-js 4.2 (219 KB), dayjs 1.11 (7 KB).

| Mezon | `quickjs` 1.19.4 | **`quickjs-ng` 0.17.0.2** | Node 24 sidecar (`vm`) |
|---|---|---|---|
| O'rnatish (macOS arm64, Py 3.14) | **tayyor wheel yo'q** — faqat sdist, kompilyator (Xcode CLT) kerak, 14 s | **binary wheel** (`cp310-abi3`), kompilyatorsiz. Linux x86_64/aarch64, Windows ham wheel. **macOS Intel: wheel yo'q** (sdist) | Node o'rnatilgan bo'lishi shart (loyiha Node'siz ishlashi kerak — zid) |
| Qo'llab-quvvatlash | oxirgi release 2023-11 (QuickJS 2021) | faol (2026-10-22), QuickJS-NG | — |
| Kontekst yaratish | 0.11 ms | 0.07 ms | 0.25 ms (+ jarayon: **28 ms** ishga tushish; `--permission` 35 ms) |
| chai / lodash / CryptoJS / dayjs yuklash | 9 / 10 / 7.7 / 0.8 ms (hammasi 25 ms) | 6.9 / 6.5 / 7.4 / 0.6 ms (hammasi **23 ms**) | 0.8 / 3.5 / 1.7 / 0.3 ms (hammasi 4 ms) |
| Kutubxonalar ishlaydimi | chai ✓ lodash ✓ MD5/HMAC ✓ dayjs ✓; **AES ✗** (`crypto.getRandomValues` yo'q) | xuddi shunday; **polyfill bilan AES ✓** (random — Python `os.urandom` ko'prigi) | xuddi shunday (AES ✗ polyfillsiz) |
| `fib(27)` | 14.6 ms | 19.4 ms | 45 ms |
| 10⁷ tsikl (funksiya doirasida) | 150 ms | 144 ms | 13 ms (global doirada vm **8.4 s**!) |
| 1.2 MB JSON parse+stringify | 46 ms | **20 ms** | — |
| Xotira limiti | `set_memory_limit` — "out of memory" xatosi, jarayon tirik | xuddi shunday | **kontekst bo'yicha yo'q**; `--max-old-space-size` bilan butun jarayon **fatal OOM bilan qulaydi** |
| Vaqt limiti | `set_time_limit` — 0.30 s da to'xtadi, `try/catch` yutib yubora olmaydi | xuddi shunday | `vm timeout` ✓ (to'xtaydi, catch yutmaydi) |
| Stack limiti | `set_max_stack_size` ✓ | ✓ | "Maximum call stack size exceeded" ✓ |
| Fayl/tarmoq/`require`/`process`/`fetch` | **mavjud emas** (global yo'q); `import('os')` — rad etiladi | xuddi shunday | bo'sh sandbox'da yo'q, **LEKIN qochish oson**: `this.constructor.constructor('return process')()` → `fs.readdirSync`, `child_process.execSync('echo pwned')`, loopback `fetch` hammasi ishladi. `--permission` fs/child_process'ni to'sadi, **tarmoq qochishi baribir ishlaydi** (Node permission modeli tarmoqni cheklamaydi) |
| ES xususiyatlari | `async`, `?.`, `??`, BigInt ✓; `Array.at`, `Object.hasOwn`, `atob` **yo'q** | + `Array.at`, `findLast`, `Object.hasOwn`, `atob` ✓ | to'liq V8 |
| Python ↔ JS ko'prik | `add_callable`, 10 000 chaqiruv = 1.5 ms | 1.4 ms | stdin/stdout JSON-protokol (IPC) |

Ikkalasida ham yo'q: `console`, `setTimeout`, `structuredClone`, `TextEncoder`, `Intl`, `Buffer` (polyfill kerak; `console` bizning log kanalimiz bo'ladi).

## Qaror
**`quickjs-ng`** (Python paketi, modul nomi `quickjs`; `requirements.txt` ga qo'shiladi, `quickjs` bilan birga o'rnatilmaydi).

Sabablar:
1. **Xavfsizlik kafolati konstruksiya bo'yicha**: kontekstda host ob'ekti, fayl, tarmoq, modul yuklovchi yo'q — qochish vektori yo'q (Node `vm` `constructor.constructor` orqali bir qatorda qochib, fayl/jarayon/tarmoqqa chiqdi; `--permission` tarmoqni yopmaydi). Talab 4 (fayl tizimi va tarmoqqa kirmaslik) Node'da faqat OS darajasidagi izolyatsiya (alohida foydalanuvchi/sandbox-exec) bilan bajariladi — ortiqcha murakkablik.
2. **Limitlar kontekst bo'yicha** (vaqt, xotira, stack) va jarayon tirik qoladi; Node'da OOM butun sidecar'ni o'ldiradi.
3. **Node'siz ishga tushish saqlanadi** (`run.command` faqat pip). Jarayon-ichi: IPC, sidecar hayot sikli, port/pipe boshqaruvi yo'q; kontekst yaratish 0.07 ms.
4. **O'rnatish**: arm64 macOS uchun tayyor wheel. `quickjs` (asl) uchun wheel yo'q (kompilyator talab qiladi, 2023 dan beri yangilanmagan) — rad etildi.
5. Tezlik yetarli: kutubxonalar bilan to'liq kontekst ≈ 23 ms (har run'ga bir marta; kutubxona `require` qilinganda yuklanadi), skript ≈ 0.02–0.03 ms, 10⁷ tsikl 0.15 s. V8 tezroq (13 ms), lekin skriptlar kichik.

## Kamchiliklar va yumshatish
- **macOS Intel / noma'lum platforma**: wheel yo'q → pip sdist'dan quradi (kompilyator kerak). Agar o'rnatilmasa, **skriptlar o'chirilgan holda** ishlaydi: UI "Skriptlar o'chiq: `quickjs-ng` o'rnatilmagan" deydi, qolgan hamma narsa (so'rovlar, runner) avvalgidek (`run.command` pip xatosini ko'rsatadi, lekin ilovani to'xtatmaydi — skript paketi ixtiyoriy deb belgilanadi: `requirements-scripts.txt`).
- **Yo'q Web API'lar** (`atob` bor, `btoa`, `TextEncoder`, `structuredClone`, `Intl`, `setTimeout`, `crypto.getRandomValues`): prelude'da polyfill (`btoa`, `crypto.getRandomValues` → `os.urandom` ko'prigi, `setTimeout` → skript tugagach tartib bilan bajariladigan navbat, haqiqiy kutishsiz).
- **Async**: `pm.sendRequest` callback/Promise — ko'prik sinxron bajaradi va kontekstning `execute_pending_job()` navbatini skript oxirida bo'shatadi.
- Kontekst **ip-xavfsiz emas**: har bir bajarilish (har bir thread) o'z kontekstini yaratadi; kutubxona matnlari bir marta o'qilib xotirada saqlanadi.

## Dizayn (implementatsiya uchun)
- `apirunner/core/scripting/`: `sandbox.py` (kontekst, limitlar: vaqt 5 s, xotira 64 MB, stack 512 KB — sozlanadi), `prelude.js` (`pm`, `console`, polyfill'lar), `libs/` (chai, lodash, CryptoJS, dayjs — vendored, litsenziyalari bilan), `pm.py` (host ko'prigi).
- Host ko'prigi **yagona kanal**: skript faqat `pm.*` orqali `variables` (global/collection/environment/data/local lug'atlari — Python xotirasida nusxa), joriy so'rov/javob (JSON nusxa) va `pm.sendRequest` (engine'ning `execute()` si, fayl siyosati va timeout bilan) ga murojaat qiladi. Skript tugagach engine o'zgargan lug'atlarni oladi va **o'zi** workspace'ga yozadi (atomik yozuv, `rev` tekshiruvi) — skript hech qachon fayl yo'lini ko'rmaydi.
- `engine.execute` ga pre/post hook nuqtalari; meros tartibi: collection → papka → so'rov (pre-request), javobdan keyin xuddi shu tartibda (Postman kabi).
- Xavfsizlik testlari: `require/process/fetch/import` yo'q, `constructor` qochishi natija bermaydi, cheksiz tsikl/xotira bombasi/rekursiya to'xtatiladi, `pm.environment.set` dan tashqari yo'l bilan workspace o'zgarmaydi, `pm.sendRequest` dan boshqa tarmoq yo'q (echo server bilan), fayl siyosati `pm.sendRequest` ga ham qo'llanadi.

## Rad etilganlar
- Node sidecar (`vm`/`--permission`): xavfsizlik kafolati zaif, OOM jarayonni o'ldiradi, Node bog'liqligi.
- `isolated-vm`: native build, Node bog'liqligi saqlanadi.
- `py-mini-racer` (V8): Py 3.14 uchun wheel topilmadi; `pythonmonkey`: wheel bor, lekin katta bog'liqlik (SpiderMonkey) va Python ↔ JS ob'ekt bog'lanishi sandbox chegarasini xiralashtiradi — kerak emas.
