# ADR 0008 — Import / Export (Bosqich 5)

**Holat:** Qabul qilingan

## Qaror
- **Yagona oqim:** manba (matn/zip) → `importers.registry.parse_source` (format aniqlanadi: Postman collection/environment/globals, OpenAPI 3.x/Swagger 2.0 JSON+YAML, Insomnia v4, HAR, cURL, workspace zip) → ichki model (Postman v2.1 superseti) → `storage.import_apply` (nom to'qnashuvi bo'yicha amal) → workspace.
- **Ko'rib chiqish → tasdiq:** `POST /api/import/preview` hech narsa yozmaydi (format, statistika, ogohlantirishlar, to'qnashuv va "birlashtirish" natijasi oldindan hisoblanadi); `POST /api/import/apply` har element uchun amal oladi: `import | copy | replace | merge | skip`. Eski `POST /api/import` (bitta manba, `dry_run`) o'zgarishsiz ishlaydi.
- **Konflikt (bir xil nom, katta-kichik harfga e'tiborsiz):** *Yangi nusxa* — `Nom (2)`; *Almashtirish* — id saqlanadi, eskisi **Savatga** (muhit ham; globals uchun avval zaxira); *Birlashtirish* — mos kelmaganlar qo'shiladi, mos kelganlar (papka: nom; so'rov: nom+metod+URL) o'zgarmaydi, o'zgaruvchilar to'ldiriladi; *O'tkazib yuborish*. Hech narsa jimgina yo'qolmaydi.
- **Ichki model:** description Postman'da turli joyda — import `x-apirunner.description`ga ko'chiradi (UI shu yerdan o'qiydi), eksport qaytaradi. `url.raw` — yagona manba: eksport `protocol/host/port/path/query` ni raw'dan qayta hisoblaydi (eskirgan qismlar chiqmaydi).
- **Eksport:** Postman v2.1 (ichki kalitlar yo'q; fayl havolalari faqat fayl nomi; secret o'zgaruvchi qiymati bo'sh, `?secrets=1` bilan ochiladi), Postman environment/globals (**faqat Initial**, Current ketmaydi, secret bo'sh), OpenAPI 3.0.3 (yo'llar `:id`/`{{var}}` → `{param}`, JSON body → sxema, Example → response, auth → securitySchemes), workspace zip: **sukut bo'yicha maxfiy/Current/auth qiymatlarsiz va bazasiz**; ixtiyoriy (qizil ogohlantirish bilan) maxfiylar va `state.db` snapshot qo'shiladi, parol berilsa AES-256-GCM (scrypt) bilan shifrlanadi (`APRZENC1` formati). Avtomatik zaxiralar (`backups/`) bundan mustasno — lokal va to'liq (v2.7.1).
- **OpenAPI importi:** server → `{{baseUrl}}` o'zgaruvchisi; lokal `$ref`; misol bo'lmasa sxemadan generatsiya (chuqurlik ≤ 6); tag → papka; xavfsizlik → auth.
- **Round-trip kafolati (testlar):** har manba uchun `import → Postman v2.1 → import` kanonik ko'rinishi bir xil (id/hosila maydonlarsiz); OpenAPI uchun `import → OpenAPI → import` mazmuniy shakli (papka, nom, metod, yo'l, query/header kalitlari, body turi, javob kodlari) bir xil; zip uchun to'liq tiklanadi.

## Oqibatlar
- `PyYAML` va `cryptography` — `requirements.txt` da.
- Insomnia v5 (YAML) qo'llab-quvvatlanmaydi — foydalanuvchiga v4 eksport qilish tavsiya etiladi (aniq xabar).
- OpenAPI eksportida bir xil metod+yo'l takrorlansa (OpenAPI taqiqlaydi) takror so'rovlar `x-skipped` ga yoziladi.
