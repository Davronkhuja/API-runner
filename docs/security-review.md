# Xavfsizlik ko'rigi (Bosqich 8)

Ko'rik sanasi: 2026-11-11 (v2.9.0 → v3.0.0). Model: ilova **lokal, bir foydalanuvchi**; tahdid manbalari — brauzerdagi begona sahifalar (CSRF, DNS rebinding), shu kompyuterdagi boshqa lokal servislar, begona manbadan olingan fayllar (collection/zip/Markdown) va skriptlar.
Testlar: `tests/test_security.py`, `tests/test_security_review.py`.

## Topilmalar va tuzatishlar

| # | Topilma | Og'irlik | Holat |
|---|---|---|---|
| S1 | **Origin** faqat *hostname* bo'yicha tekshirilardi: boshqa lokal servis (masalan `http://localhost:3000`) yoki `Origin: null` sahifa (sandbox iframe) tekshiruvdan o'tardi (token hali talab qilinardi, lekin himoya qatlami zaif edi) | o'rta | **Tuzatildi:** Origin aynan shu server (`host:port`) bo'lishi shart; `null` rad etiladi |
| S2 | Xavfsizlik sarlavhalari yo'q edi (clickjacking: UI'ni begona sahifa `<iframe>` ichiga olishi mumkin edi) | o'rta | **Tuzatildi:** `X-Frame-Options: DENY`, CSP `frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` |
| S3 | Sessiya tokeni EventSource uchun URL'da (`?token=`) yuboriladi va werkzeug kirish jurnaliga tushardi | past | **Tuzatildi:** jurnal filtri `token=***` ga almashtiradi (EventSource header qo'ya olmaydi — URL'da qoladi) |
| S4 | Fayl siyosatida ruxsat etilgan ildiz butun **workspace papkasi** edi: import qilingan collection'dagi `src: "<workspace>/state.db"` bilan so'rov ishga tushirilsa, baza/JSON faylini begona serverga yuborish mumkin edi | yuqori | **Tuzatildi:** ruxsat etilgan ildizlar — yuklash papkasi va `workspace/files/` (fayl ombori) |
| S5 | Markdown'da NUL (`\0`) belgisi ichki o'rinbosar bilan to'qnashardi (Python hujjat generatorida `IndexError` — hujjat yaratish yiqilardi) | past | **Tuzatildi** (kirishdan NUL olib tashlanadi; Python va TS) |
| S6 | `apirunner serve/mock --host 0.0.0.0` jimgina tarmoqqa ochardi | past | **Tuzatildi:** ogohlantirish chiqadi (sukut `127.0.0.1`; UI/API'dagi mock va proxy host qabul qilmaydi) |
| S7 | `*.localhost` (Caddy: `api-runner.localhost`) Host tekshiruvidan o'tmasdi | funksional | **Tuzatildi:** `*.localhost` ruxsat (RFC 6761: brauzer doim loopback'ga hal qiladi; DNS rebinding mumkin emas); lookalike nomlar rad etiladi |

## Tekshirildi — muammo topilmadi
- **Host/DNS rebinding:** begona `Host` (`evil.com`, `127.0.0.1.evil.com`, `localhost.evil.com`) har qanday yo'lda 403.
- **Token:** `hmac.compare_digest`, har ilova ishga tushishida tasodifiy (`secrets.token_urlsafe(32)`); `/`, `/legacy`, ikonlar va `/oauth/callback` dan boshqa hamma yo'l tokenli.
- **Mock va proxy:** faqat `127.0.0.1` ga bog'lanadi (testda tekshiriladi); proxy nisbiy yo'lni (`/etc/passwd`) rad etadi (400); HTTPS faqat ko'r tunnel — trafik ichi o'qilmaydi, MITM sertifikat o'rnatilmaydi.
- **Skript sandbox (quickjs):** `require/process/fetch/Buffer/std/os/…` yo'q, `constructor`/`Function`/`eval`/`import()` orqali chiqish yo'q, `fs`/`child_process` topilmaydi, vaqt/xotira/so'rov chegaralari (`tests/test_scripting.py`).
- **Fayl yo'llari:** fayl ombori content-addressed (`files/<sha256>/…`, nom `safe_name`), `files/adopt` faqat yuklash papkasidan, `_resolve_file` `realpath` bilan (symlink orqali chiqib ketmaydi), workspace/collection ID'larida `..` rad etiladi.
- **Zip import:** `..` ichida bo'lgan yozuvlar tashlab yuboriladi, fayllar nomi bilan emas **xesh** bo'yicha yoziladi, ochilgan hajm ≤ 500 MB, shifrlangan zip (AES-256-GCM) paroli tekshiriladi; traversal nomlari bilan zip hech narsani tashqariga yozmaydi (test).
- **XSS:** Markdown (UI va statik hujjat) avval hamma narsani escape qiladi, faqat `http(s)/mailto` havolalar; 12 ta hujum matni bilan test; javob HTML ko'rinishi `sandbox=""` iframe'da; `v-html` faqat escape qilingan/ranglangan matnda; OAuth callback `postMessage`ni faqat `location.origin` ga yuboradi.
- **Maxfiy qiymatlar:** eksportda sukut bo'yicha chiqmaydi, workspace zip ixtiyoriy shifrlanadi (v2.7.1).

## Qolgan xavflar (qabul qilingan)
- Token `GET /` javobida beriladi: shu kompyuterda loopback'ga ulana oladigan **boshqa jarayon** uni o'qiy oladi (bir foydalanuvchi modeli; OS darajasidagi himoya doirasida).
- Proxy capture har qanday URL'ga yo'naltiradi (faqat loopback'dan kirish mumkin).
- Foydalanuvchi skripti `pm.sendRequest` bilan lokal tarmoqqa so'rov yubora oladi (Postman bilan bir xil, mo'ljallangan xatti-harakat).
