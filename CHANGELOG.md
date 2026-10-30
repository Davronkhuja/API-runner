# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/). Versiyalash: SemVer (bosqich tugashi = MINOR, bosqich ichidagi funksiya/tuzatish = PATCH). Yagona manba: `apirunner/__init__.py`.

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
