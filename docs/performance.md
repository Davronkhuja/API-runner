# Ishlash o'lchovlari (Bosqich 8)

Qayta ishlab chiqarish: `python3 tools/perf_bench.py --out perf.json [--only collection,bigjson,csv,tabs,cold]`
(tmp workspace, lokal echo server, headless Chromium; asosiy oqim bloklanishi — `longtask` kuzatuvchisi, kadr vaqti — `requestAnimationFrame`, xotira — CDP/`performance.memory`).

Muhit: Apple M1, 16 GB, macOS, Python 3.14, Chromium (Playwright). Raqamlar bitta mashinadagi bir necha yurishning tipik qiymati; mutlaq qiymatdan ko'ra **oldin/keyin** nisbati muhim.

## Natijalar

| Senariy | O'lchov | Oldin | Keyin |
|---|---|---|---|
| **1200 so'rovli collection** (40 papka × 30) | sahifa ochilishidan daraxtgacha | 230–300 ms | 230–420 ms (o'zgarmadi) |
| | 1241 qator DOM'da, aylantirish | 0 long task, kadr p95 16.7 ms | o'zgarmadi |
| | sidebar filtri («resource-17-0» yozish → natija) | ~170–200 ms | o'zgarmadi |
| | ⌘K qidiruv (yozish → natija) | 27–41 ms | o'zgarmadi |
| | DnD (so'rovni qo'shni qatorga, serverga saqlanguncha) | 166 ms, 0 long task | o'zgarmadi |
| | JS heap (1200 so'rov) | ~11 MB | o'zgarmadi |
| **8.9 MB JSON javob** (1.3 mln qator, Pretty) | yuborishdan ko'rinishgacha | 1865 ms | **~820 ms** |
| | eng uzun bloklanish (UI qotishi) | **1348 ms** | **~100 ms** |
| | JS heap | 222 MB | **61–66 MB** |
| | virtual scroll (40 qadam) | 0 long task | 0 long task, kadr p95 16.7 ms |
| **Runner, 10 000 qatorli CSV** | birinchi natija qatori | 90–130 ms | o'zgarmadi |
| | butun run (10 000 so'rov, lokal echo) | ~10.5 s | ~10.4 s |
| | UI: long task / kadr p95 | 0 / 16.8 ms | o'zgarmadi |
| | JS heap: boshida → eng yuqori → oxirida | 5–10 → 9.5 → 11 MB | o'zgarmadi (barqaror) |
| | DOM'dagi natija qatorlari | 1000 (qolgani xotirada emas, serverda) | o'zgarmadi |
| **50 ochiq tab** | sahifa ochilishidan hamma tab chiqquncha | 170–270 ms | o'zgarmadi |
| | tabni almashtirish | 32–92 ms | o'zgarmadi |
| | JS heap | 6–12 MB | o'zgarmadi |
| **Sovuq ishga tushish** (jarayon → birinchi javob) | `import` + `create_app` + `GET /` | 230–380 ms (import ~140–290, create_app ~25, birinchi so'rov ~5–9) | o'zgarmadi |

## Topilgan va tuzatilgan to'siq: katta JSON'da UI qotishi

10 MB'ga yaqin JSON javobda Pretty ko'rinish ~1.3 s asosiy oqimni bloklardi va 220 MB heap ishlatardi.
CDP profilerida vaqtning ~750 ms i Vue `track()` da ketayotgani ko'rindi: `ResponsePanel.vue` javobni **reaktiv proxy** orqali `JSON.stringify` qilardi, shu sababli 1.3 mln elementning har biri uchun bog'liqlik kuzatuvi (`track`) chaqirilardi. Tuzatish: `JSON.stringify(toRaw(v), …)` va JSONPath'ga `toRaw` — ko'rinish va xatti-harakat o'zgarmaydi. Natija: eng uzun bloklanish 1348 → ~100 ms, heap 222 → ~65 MB, yuborishdan ko'rinishgacha 1.9 → 0.8 s.

## Cheklovlar va kuzatuvlar
- Daraxt 1200 so'rovda virtualizatsiyasiz (1241 qator DOM'da) ham silliq; 10 000+ so'rovli collection uchun virtualizatsiya kerak bo'lishi mumkin (hozircha o'lchanmagan).
- Runner natijalari UI'da 1000 qatorgacha ko'rsatiladi; to'liq natijalar serverda (SQLite) va eksportda.
- Headless Chromium GPU'siz: kadr vaqtlari haqiqiy brauzerdan yomonroq bo'lishi mumkin.
