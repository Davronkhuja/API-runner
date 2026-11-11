# Paketlash (macOS .app)

```bash
packaging/build_macos_app.sh          # dist/API Runner.app
packaging/build_macos_app.sh --smoke  # + oynasiz selftest (server ishga tushadi va javob beradi)
```
- Alohida oyna (pywebview, WKWebView), Dock ikonkasi (`apirunner/static/app/icon-512.png` dan `.icns`).
- Ma'lumot **ilova ichida emas**: `~/Library/Application Support/API Runner/{workspace,backups,saved_requests.json}` (`APIRUNNER_HOME` bilan almashtiriladi). Mavjud `workspace/` ni ko'chirish uchun uni shu papkaga nusxalang.
- Server faqat `127.0.0.1` da, tasodifiy port; sessiya tokeni har ishga tushishda yangi.
- Ilova imzolanmagan: birinchi ochishda Finder'da o'ng tugma → «Ochish». Imzolash/notarizatsiya (Apple Developer ID) — alohida qadam.
- Ishlab chiqish: `python -m apirunner.desktop` (pywebview o'rnatilgan bo'lsa) — paketlashsiz oyna.
