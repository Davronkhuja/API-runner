# ADR 0001 — Monolitni paketga bo'lish

**Holat:** Qabul qilingan (Bosqich 1) · **Sana:** 2026-10-30

## Kontekst
`api_runner.py` ~5360 qator: ~4770 qatori HTML/JS, ~590 qatori Flask + ishchi mantiq. Mantiq `job_worker` va `run_one` da takrorlangan, test yozib bo'lmaydi (modul importida side-effect).

## Qaror
```
api_runner.py            # faqat kirish nuqtasi (python3 api_runner.py, run.command ishlayveradi)
apirunner/
  app.py                 # create_app(workspace_dir, saved_file, upload_dir, session_token), main()
  core/                  # variables, engine (execute), runner (batch), jobs (SSE job'lar)
  storage/               # model, workspace (JSON fayllar), db (SQLite), migrate
  api/                   # Flask blueprint'lar: legacy (eski UI bilan 1:1), workspace_api (/api/*), security
  static/index.html      # hozirgi UI (mazmuni o'zgarmagan); yangi frontend build'i shu yerga tushadi
tests/                   # pytest + Playwright
```
`create_app()` fabrikasi — global holat yo'q, testlar har safar izolyatsiyalangan nusxa oladi.

## Oqibatlar
+ Engine, storage, API alohida test qilinadi. + CLI (Bosqich 7) `core/` ni Flask'siz import qiladi.
− `apirunner/` papkasi qo'shildi; `api_runner.py` ichida endi `HTML` o'zgaruvchisi yo'q (hech kim import qilmaydi).
