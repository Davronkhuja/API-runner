# ADR 0006 — Frontend stack

**Holat:** Taklif — **TASDIQ KUTILMOQDA** (Bosqich 1 hisobotida so'raladi)

## Taklif
Vite + Vue 3 + TypeScript + Pinia, muharrir — CodeMirror 6. Manba `web/`, build natijasi `apirunner/static/` ga **commit qilinadi** (`run.command` Node'siz ishlaydi).

## Sabab
Multi-tab (har tabning mustaqil holati), ichma-ich daraxt + drag&drop, scope'li o'zgaruvchilar, Console/Runner panellari — bular holat-markazli UI; ~4800 qatorlik global-o'zgaruvchili vanilla JS'da qo'llab-quvvatlash qiyin. Pinia tab/workspace holatini testlanadigan qiladi, CodeMirror 6 `pm.*` avtoto'ldirish va katta javoblar uchun kerak.

## Muqobil: vanilla JS'da qolish
Build zanjiri yo'q, kod hajmi kichik. Lekin Bosqich 2–4 hajmi (taxminan 3× UI) uchun tuzilmasiz qoladi. Tavsiya etilmaydi.

## Bosqich 1 holati
Hozirgi UI `apirunner/static/index.html` ga ko'chirildi (mazmuni o'zgarmagan, faqat ⇪ import tugmasi qo'shildi). Vue skeleti **tasdiqdan keyin** boshlanadi, chunki rad etilsa ish bekor ketadi. Migratsiya tartibi: avval 1:1 paritet (har ekran uchun e2e), keyin yangi funksiyalar.
