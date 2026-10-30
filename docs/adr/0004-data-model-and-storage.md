# ADR 0004 — Ma'lumot modeli va saqlash

**Holat:** Qabul qilingan (Bosqich 1)

## Model
Workspace → Collection → ichma-ich Folder → Request (+ Examples), Environment, Globals. Collection = **Postman Collection v2.1 superseti**: `info`, `item[]` (folder = `item` bor, request = `request` bor), `auth`, `variable`, `event`, `response[]` (= Examples). Bizning qo'shimchalar faqat `x-apirunner` kaliti ostida (Postman e'tiborsiz qoldiradi) → import/export deyarli yo'qotishsiz. Environment/globals — Postman formati (`values[{key,value,enabled,type}]`).

## Saqlash
- Collection / environment / globals: `workspace/` ichida JSON (git-friendly, atomik yozuv: tmp + `os.replace`, id regex bilan tekshiriladi — path traversal yo'q).
- Tarix, (keyin) run natijalari, cookie'lar: SQLite `workspace/state.db`.
- localStorage faqat UI sozlamalari uchun qoladi (Bosqich 2 da).
- Workspace joyi: `APIRUNNER_WORKSPACE` yoki `<repo>/workspace/` (gitignore'da). `pipx` paketlashda (Bosqich 7) foydalanuvchi papkasiga o'tadi.

## Eski so'rovlar (`x-apirunner.legacy`) — o'tkinchi
Eski UI tekis formatda ishlaydi. Har so'rovning asl dict'i `x-apirunner.legacy` da aynan saqlanadi (yo'qotishsiz, noma'lum maydonlar ham), Postman maydonlari (`request.method/url/header/body/auth`) undan hosil qilinadi. Yangi UI (Bosqich 2) Postman maydonlarini to'g'ridan-to'g'ri tahrirlaganda `legacy` olib tashlanadi.
Eski `/saved/*` API shu daraxtdan tekis ko'rinish beradi. Cheklov: ro'yxat papkalar bo'yicha guruhlanadi (papka ichidagi va ildizdagi nisbiy tartib saqlanadi).

## Migratsiya
1. `saved_requests.json` → `workspace/collections/saved.json`: avval `saved_requests.json.bak` (bor bo'lsa vaqt tamg'ali), asl fayl **tegilmaydi/o'chirilmaydi**. `workspace.json: legacy_migrated` bilan bir marta. Buzuq fayl — tegilmaydi, keyingi ishga tushishda qayta uriniladi.
   Xavf: migratsiyadan keyin eski versiyaga qaytilsa, workspace'dagi yangi o'zgarishlar eski faylda ko'rinmaydi.
2. localStorage → `POST /api/import/localstorage` (UI'dagi ⇪ tugmasi): env'lar, faol env, eski yagona env o'zgaruvchilari (→ globals), 3 turdagi tarix (→ SQLite). Xom nusxa `workspace/imports/`. Idempotent. UI hali env/tarixni localStorage'dan o'qiydi — serverdan o'qish yangi frontend bilan.
