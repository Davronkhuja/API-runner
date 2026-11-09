# API Runner — doimiy ish qoidalari (har sessiyada o'qiladi)

## Loyiha
Lokal Postman-darajasidagi API klient. **Backend:** Flask + httpx (`apirunner/`), SQLite (`workspace/state.db`: tarix, javoblar, run natijalari), ma'lumot — `workspace/` ichida JSON (Postman v2.1 superseti). **Frontend:** Vue 3 + TypeScript + Pinia + Vite + CodeMirror 6 (`web/`), build natijasi `apirunner/static/app` ga tushadi va **git'ga commit qilinadi** (Node'siz ishlashi uchun). Skript sandbox: quickjs-ng. Interfeys va matnlar — **o'zbekcha**.

Papkalar: `apirunner/{core,storage,api,importers,exporters,static}` · `web/src/{components,lib,stores,styles}` · `tests/` (pytest, `tests/e2e` Playwright, `tests/fixtures`) · `tools/` (`ui_audit.py`, `check_fixed_heights.py`) · `docs/` · `workspace/`, `backups/`, `saved_requests.json` (**foydalanuvchi ma'lumoti — tegilmaydi**).

Ishga tushirish: `./run.command` (venv, bog'liqliklar, port 5050) yoki PM2: `pm2 start ecosystem.config.js` (nom `api-runner`; yangilangach UI'dagi "Qayta ishga tushirish" tugmasi yoki `pm2 restart api-runner`). Frontend: `cd web && npm run build` (typecheck + build). Python: `source .venv/bin/activate`.

Hujjatlar (ishdan oldin tegishlisini o'qi): `docs/AGENT_PROMPT_postman_level.md` (asosiy reja/talablar), `docs/AGENT_PROMPT_ui_audit.md` (UI sifat jarayoni), `docs/ROADMAP.md` (bosqichlar, belgilab bor), `docs/ui-audit.md` (audit hisoboti), `docs/adr/` (arxitektura qarorlari), `docs/design/*.dc.html` (maketlar), `CHANGELOG.md`, `README.md`.

## Git
- Har vazifa — **feature branch** (`feature/...`, `fix/...`), `master` dan. Kichik, mazmunli commit'lar (inglizcha xabar, oxirida `Co-Authored-By` qatori).
- **SemVer** (`apirunner/__init__.py` — yagona manba; `tests/test_workspace_api.py` dagi literal ham): bosqich tugashi = MINOR, funksiya/tuzatish ichida = PATCH. Har versiyada: veb qayta build, `CHANGELOG.md` yozuvi, `docs/ROADMAP.md` belgilari, README, versiya **tegi** (`vX.Y.Z`, versiya commit'iga).
- Push → `gh pr create` (**base doim `master`**; poydevor branch hali merge bo'lmagan bo'lsa — istisno, PR tavsifida aytiladi). PR tavsifi CHANGELOG'dan, birinchi qatorda **"Versiya: vX.Y.Z"**, oxirida Claude Code qatori.
- **Merge'ni faqat foydalanuvchi qiladi.** `git push --force`, `reset --hard` ulashilgan tarixda, `filter-branch`/rebase bilan tarixni qayta yozish **taqiqlangan** (faqat hali push qilinmagan o'z lokal commit'larida mumkin).

## Ma'lumot xavfsizligi (muqaddas)
- Haqiqiy `workspace/`, `saved_requests.json`, `backups/` ga testlar va tajribalar **tegmaydi**: testlar faqat tmp (`APIRUNNER_TESTING` himoyasi); qo'lda tajriba uchun alohida `APIRUNNER_WORKSPACE`.
- Migratsiya yoki ommaviy o'zgarishdan OLDIN avtomatik zaxira (`storage/backup.py`); idempotent, rollback bilan.
- **Hard delete yo'q:** so'rov/papka/collection/muhit faqat **Savat** orqali (`Workspace.delete_*`, 30 kun). Almashtirish/import ham eskisini Savatga (globals — zaxiraga) oladi. Yangi o'chirish yo'li qo'shsang — `tests/test_no_hard_delete.py` o'tishi shart.
- Maxfiy qiymatlar (secret, Current, token) eksport va logga sukut bo'yicha chiqmaydi; testda tashqi tarmoq yo'q (lokal echo server).
- Ommaviy/qaytarib bo'lmas amal oldidan foydalanuvchidan so'ra.

## "Tayyor" mezoni (hisobotdan oldin MAJBURIY)
Hisobot berishdan oldin **TO'LIQ majmua BIR BUTUN holda** yurgiziladi va yashil bo'ladi — **tuzatishdan KEYIN ham qayta**:
1. `cd web && npm run build && npx vitest run` (typecheck + vitest);
2. `python3 -m pytest tests -q` (pytest + e2e + vizual regressiya + layout + axe — hammasi, `-n 4` sukut);
3. `python3 tools/check_fixed_heights.py` (testda ham bor).
Qisman yurish ("faqat o'zgargan testlar") yakuniy dalil emas. Natija raqamlari hisobotda aytiladi.

**Beqaror test "boshqa yurishda o'tdi" deb qoldirilmaydi.** Sababi topiladi (yuklama ostida qayta ishlab chiqarish: bir nechta jarayonni parallel yurgiz; `-n 0 -k nom`) va tuzatiladi, regressiya testi yoziladi; faqat topib bo'lmasa — `@pytest.mark.skip(reason=...)`/quarantine **aniq izoh bilan** va hisobotda alohida ko'rsatiladi. Vizual baseline'lar faqat ataylab dizayn o'zgarganda yangilanadi (`UPDATE_BASELINE=1`), tasodifiy farq — xato.

## UI
- Hamma matn o'zbekcha; yagona `Dialog.vue`, dizayn tokenlari (`web/src/styles/tokens.css`), mavjud `data-testid` lar saqlanadi/yangilanadi.
- **Har yangi ekran/dialog uchun** `docs/AGENT_PROMPT_ui_audit.md` jarayoni: real ssenariy skrinshotlari (1440×900 va 1920×1080, light/dark, `python3 tools/ui_audit.py --out docs/screenshots/qa/<versiya> --screens ...`; gitignored), topilmalarni tuzatish, vizual baseline (`tests/e2e/test_visual_regression.py`), layout guard sahnasi (`tests/e2e/test_layout_guards.py` + `tools/ui_audit.py`), axe (0 serious/critical), qattiq balandliklar lint'i.
- e2e yozishda: CodeMirror avtoto'ldirishda `interactionDelay` (~75 ms) hisobga olinadi; takroriy testid'larga ehtiyot bo'l.
