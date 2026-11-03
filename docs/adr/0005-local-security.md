# ADR 0005 — Lokal xavfsizlik

**Holat:** Qabul qilingan (Bosqich 1)

Muammo: server so'rov yuborish va fayl o'qish qila oladi; brauzerdagi har qanday sahifa `127.0.0.1:5050` ga murojaat qilishi yoki DNS rebinding qilishi mumkin.

## Qarorlar
1. **Host**: faqat `127.0.0.1`, `localhost`, `::1` (port ixtiyoriy) — aks holda 403. DNS rebinding'ni to'xtatadi.
2. **Origin**: bor bo'lsa, shu ro'yxatda bo'lishi shart.
3. **Sessiya tokeni**: ishga tushganda `secrets.token_urlsafe(32)`; `/` va `/static/*` dan tashqari hamma yo'l `X-Session-Token` (yoki `?token=`, faqat EventSource uchun) talab qiladi; `hmac.compare_digest`. Token `/` javobiga inject qilinadi (`Cache-Control: no-store`). Eski UI o'zgarmasligi uchun inject qilingan skript `fetch` va `EventSource` ni o'raydi; yangi frontend tokenni to'g'ridan-to'g'ri ishlatadi.
4. **Fayl siyosati**: fayl parametri faqat `.tmp_uploads/` (UI 📎 shu yerga yuklaydi), workspace yoki `ExecContext.allowed_files` (foydalanuvchi aniq tanlagan) ichidan o'qiydi; `realpath` bilan (symlink orqali qochib bo'lmaydi). Aks holda natija `ERROR: Fayl yo'liga ruxsat yo'q`, retry qilinmaydi.

## Cheklovlar
Token HTML ichida — bir foydalanuvchi sessiyasidagi boshqa lokal jarayonlar `/` ni o'qib olishi mumkin (lokal himoya modeli: begona sayt/tarmoq, boshqa lokal foydalanuvchi emas). `python3 api_runner.py` hali `127.0.0.1` ga bog'lanadi.
Ilgari qo'lda yozilgan mutlaq fayl yo'li ishlardi; endi 📎 orqali yuklash kerak.
