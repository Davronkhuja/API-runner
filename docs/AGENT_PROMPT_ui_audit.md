# Vazifa: UI sifat auditi va barcha "elementar" xatolarni bir yo'la tuzatish

Foydalanuvchi har kuni ilovada ishlaganda oddiy, lekin ishlashga xalaqit beradigan xatolarga duch kelyapti: kesilgan muharrir, sig'magan dialog, saqlanmagan javob, ishlamaydigan resizer va hokazo. Testlar yashil bo'lsa ham, bu xatolar o'tib ketgan. Sababi: testlar funksiyani tekshiradi, ko'rinishni emas. Bu vazifaning maqsadi — xatolarni birma-bir tuzatish emas, butun interfeysni tizimli tekshirib, hammasini bitta tsiklda yopish va keyin qayta paydo bo'lmasligini kafolatlash.

Bosqich 4 ni bu vazifa tugamaguncha boshlama.

---

## 1-qadam. To'liq audit (avval topish, keyin tuzatish)

Kodga tegishdan oldin `docs/ui-audit.md` faylini yarat. Ilovani Playwright bilan quyidagi matritsa bo'yicha aylanib chiq va har bir ekran/holat uchun skrinshot ol:

- **Oynalar:** 1280×800, 1440×900, 1920×1080, shuningdek 1440×900 da brauzer masshtabi 80% va 125%.
- **Temalar:** light, dark.
- **Layout'lar:** ustma-ust, yonma-yon, zich rejim.
- **Kontent:** bo'sh, oddiy, ekstremal. Ekstremal deganda: 300 qatorli JSON body, 2 MB javob, 40 ta header, 120 belgili URL, 30 ta ochiq tab, 80 ta so'rovli papka, juda uzun so'rov nomi.

Har bir komponent uchun holatlar: default, hover, focus (klaviatura), active, disabled, loading, empty, error.

Har topilgan muammo uchun `ui-audit.md` ga bitta qator yoz:
`ID | ekran | holat | nima noto'g'ri | og'irlik (bloklaydi / xalaqit beradi / kosmetik) | skrinshot`.

Faqat shundan keyin tuzatishga o't.

## 2-qadam. Allaqachon aniqlangan muammolar

Bular foydalanuvchi va reviewer tomonidan Chrome'da haqiqiy ma'lumotlar bilan tasdiqlangan. Hammasi `ui-audit.md` ga kirsin va yopilsin.

### A. Dialoglar va overlay'lar (umumiy komponent darajasida tuzat)
1. **"</> Kod" dialogi:** uzun body bo'lsa, `<pre>` cheklanmasdan o'sadi. Dialog ekrandan oshib ketadi, sarlavha, til tanlash, "Nusxa" va × tugmalari ko'rinmay qoladi.
   - Sabab: `.dialog` da `max-height` yo'q, `.overlay` esa `align-items: center`.
   - Tuzat: YAGONA `Dialog` komponenti yarat: sarlavha va pastki tugmalar doim ko'rinadi, faqat tana scroll bo'ladi (`max-height: calc(100vh - 64px)`).
   - Barcha dialoglarni shu komponentga o'tkaz: Kod, Saqlash, Ko'chirish, BulkAuth, RunGuard, tasdiqlar, Import.
   - Esc, tashqariga bosish, fokus tuzog'i, ochilganda birinchi elementga va yopilganda trigger'ga fokus qaytishi.
2. **Kod dialogi kengligi:** 640px kod uchun tor. Uni `min(960px, 92vw)` qil, CodeMirror read-only bilan ko'rsat (qator raqamlari va ranglash bilan), "Nusxa" bosilganda toast chiqsin.
3. **Import:** tugma faqat OS fayl tanlash oynasini ochadi. Postman'dagidek Import dialogi bo'lsin:
   - fayl yoki papkani sudrab tashlash;
   - matnni joylashtirish (cURL, Postman JSON, OpenAPI);
   - URL'dan import;
   - natijani oldindan ko'rish ("3 papka, 27 so'rov, 1 muhit") va tasdiqlash.
4. **Muhit "ko'z" tugmasi:** to'liq Globals tabini ochadi. Postman'dagidek popover bo'lsin: faol muhit va Globals o'zgaruvchilari, joriy qiymatlari bilan, joyida tahrirlash va "Hammasini ochish" havolasi.

### B. Muharrirlar
5. **Body/GraphQL/Skript muharrirlari** panelning qolgan balandligini to'ldirsin, qat'iy 220px bo'lmasin. Ochilganda birinchi qator ko'rinsin, ostida o'lik bo'sh joy qolmasin.
6. **Qator raqamlari, fold, qavs moslashtirish, ⌘F qidiruv** — body, skript va javob muharrirlarining barchasida. Hozir body'da qator raqamlari yo'q.
7. **JSON xatosi:** noto'g'ri JSON bo'lsa, xato qatori qizil chiziq bilan belgilansin va Beautify xabarida qator raqami ko'rsatilsin.
8. **Skriptlar tabi:**
   - muharrir bir qator balandlikda, o'ngdagi snippetlar ro'yxati juda mayda;
   - muharrir balandlikni to'ldirsin, snippetlar paneli 220–260px kenglikda, o'qiladigan shriftda bo'lsin;
   - snippet bosilganda kod kursor joyiga qo'yilsin.
9. **Content-Type takrori:** "application/json" ham input'da, ham matnda ko'rsatilgan. Bitta qolsin.

### C. Javob paneli
10. **Javob saqlanishi.** Oxirgi javob (status, sarlavhalar, tana) SQLite'da 5 MB gacha saqlansin va sahifa yangilanganda, server qayta ishga tushganda tiklansin. 5 MB dan katta bo'lsa — aniq xabar va "Faylga saqlash".
11. **Body/Headers/Cookies/Testlar tablari** bir xil toolbar joylashuvida bo'lsin, ular orasida o'tganda kontent sakramasin.
12. **Headers tabi:**
    - qidiruv;
    - nusxa olish (bitta header va hammasi);
    - Postman kabi kalit ustuni o'zgarmas kenglikda;
    - uzun qiymatlar qatorga o'ralsin.
13. **Pretty/Raw/Preview tugmalari** faqat Body tabida ko'rinsin.

### D. Formalar va layout
14. **Batch/Runner formasi:** input'lar 1/3 kenglikka cho'zilgan, RUN tugmasi o'ng chetda yolg'iz turibdi. Ixcham forma qil: label ustida, input'lar mazmuniga mos kenglikda (raqamlar 80–120px), amallar bitta qatorda chapda.
15. **Sozlamalar sahifasi:**
    - har bo'limda alohida "Saqlash" o'rniga avtosaqlash va "Saqlandi" belgisi;
    - chap tomonda bo'limlar navigatsiyasi (Ko'rinish, So'rov, Skriptlar, Fayllar, Ma'lumotlar, Zaxiralar);
    - matn ustuni max 720px.
16. **Resizer ushlash zonasi:** sichqoncha ustiga kelganda chiziq 3px gacha qalinlashib, accent rangda ko'rinsin. Hozir birinchi urinishda ilinmay qoladi.
17. **Tablar:** tablar ko'p bo'lganda horizontal scroll va "∨" ro'yxati ishlasin; faol tab ko'rinadigan joyga scroll qilinsin.
18. **Sidebar Tarix paneli:** hali ham to'liq URL'lar ro'yxati — status, vaqt va guruhlash yo'q. Maket: `docs/design/History.dc.html` (host va path alohida, status pill, vaqt, kunlar bo'yicha guruh, ×N). Sidebar va Tarix tabi bir xil komponentdan foydalansin.
19. **Nomlar:** to'liq URL bo'lib qolgan so'rov nomlari (masalan "https://api.online-mahalla.uz/api/v1/hm/projects") uchun bir martalik "Nomlarni tozalash" taklifi chiqsin: oldindan ko'rish va zaxira bilan.

### E. Izchillik
20. Ikonka-tugmalar o'lchami (28/32px), radiuslar, bo'shliqlar (4/8 shkala), shrift o'lchamlari (11/12/13/14/16/20) — `tokens.css` ga yig'ilsin. Qolgan qat'iy qiymatlarni shu tokenlarga o'tkaz.
21. Hamma joyda bir xil holat naqshlari: bo'sh holat, xato holati (qizil ramka + matn) va yuklanish (skeleton yoki spinner).
22. Dark rejimda barcha jadvallar, dialoglar va popover'lar tekshirilsin: oq fon qolib ketmasin, kontrast ≥ 4.5:1.

## 3-qadam. Qayta paydo bo'lmasligi uchun himoya

- **Vizual regressiya testlari:** Playwright `toHaveScreenshot` 12–15 ta asosiy ekran uchun (light/dark, 1440×900), `docs/screenshots/baseline/` da. CI'da ham ishlasin.
- **Layout testlari:**
  - hech qanday dialog viewport'dan oshmasligi;
  - muharrir panelni to'ldirishi (pastda 24px dan ortiq bo'sh joy qolmasligi);
  - matn kesilmasligi (`scrollWidth > clientWidth` faqat ruxsat etilgan joylarda);
  - hech bir interaktiv element 24px dan kichik bo'lmasligi.
- **Lint:** web/src'da yangi qat'iy `height: NNNpx` kontent konteynerlari uchun taqiqlansin. Kichik skript `tools/check_fixed_heights.py`, ruxsat etilganlar ro'yxati bilan.
- **Accessibility:** `@axe-core/playwright` bilan asosiy ekranlarda 0 ta "serious/critical".

## 4-qadam. Topshirish

- Bitta branch: `fix/ui-audit` (master'dan, PR #3 merge qilingandan keyin). Tuzatishlar mantiqiy guruhlar bo'yicha commit qilinsin. Versiya: MINOR (v2.4.0).
- `ui-audit.md` dagi har bir qator yopilgan bo'lsin: commit hash va "oldin/keyin" skrinshot bilan. Yopilmaganlari sababi bilan alohida bo'limda.
- To'liq test majmuasi (pytest + e2e + vitest + vizual + axe) bir butun holda yashil.
- Hisobotda: topilgan muammolar soni (og'irlik bo'yicha), yopilganlari va eng muhim 6 ta "oldin/keyin" skrinshot.
- Foydalanuvchining haqiqiy ma'lumotlari bilan ishlamang: testlar faqat tmp workspace'da. Ma'lumotlar xavfsizligi qoidalari amal qiladi.
