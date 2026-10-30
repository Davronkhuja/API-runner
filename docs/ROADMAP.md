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

## Bosqich 2 — Asosiy so'rov imkoniyatlari
### Multi-tab (majburiy) — e2e: `tests/e2e/test_multitab_spec.py`
- [ ] 30 ta band (spetsifikatsiya faylida to'liq ro'yxat)
### Sidebar va drag&drop (majburiy) — e2e: `tests/e2e/test_dnd_spec.py`
- [ ] 27 ta band (spetsifikatsiya faylida to'liq ro'yxat)
### Qolganlari
- [ ] Collection/folder darajasidagi Auth, Variables, Scripts, Description (meros)
- [ ] Variable scope'lar, path variables, dinamik o'zgaruvchilar, secret
- [ ] Auth turlari (API Key, Digest, OAuth 2.0, AWS SigV4, JWT)
- [ ] Body turlari (form-data, urlencoded jadval, binary, GraphQL)
- [ ] Qator checkbox/tavsif/bulk edit
- [ ] Sozlamalar (redirect, HTTP/2, proxy, client cert, CA)
- [ ] Cookie jar + Cookie Manager
- [ ] Response paneli (Pretty/Raw/Preview, qidiruv, JSONPath, virtual scroll, Save as Example)
- [ ] Code snippet generatori
- [ ] Server tomonda tarix

## Bosqich 3 — Skriptlar va testlar
- [ ] Pre-request / Tests skriptlari (meros tartibida), `pm.*` API, kutubxonalar
- [ ] Avtoto'ldirish, snippet'lar, Console paneli, Postman skriptlari o'zgarishsiz

## Bosqich 4 — Collection Runner v2
- [ ] Runner sozlamalari, batch integratsiyasi, real-time SSE, SQLite, eksport (JSON/HTML/JUnit), solishtirish

## Bosqich 5 — Import/Export
- [ ] Postman v2.0/2.1, env/globals, OpenAPI/Swagger, Insomnia, HAR, cURL; export; round-trip testlar

## Bosqich 6 — Boshqa protokollar
- [ ] GraphQL, WebSocket, SSE, Socket.IO (ixtiyoriy), gRPC (ixtiyoriy)

## Bosqich 7 — Kengaytirilgan imkoniyatlar
- [ ] CLI, mock server, hujjatlar generatsiyasi, Cmd+K, paketlash

## Bosqich 8 — Sayqal va sifat
- [ ] Ishlash tezligi, UX, hujjatlar
