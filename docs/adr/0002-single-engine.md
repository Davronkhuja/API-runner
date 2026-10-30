# ADR 0002 — Yagona request engine

**Holat:** Qabul qilingan (Bosqich 1)

## Qaror
`apirunner.core.engine.execute(spec, ctx) -> result` — bitta so'rov, batch (`core/runner.py`), `/run_one`, keyin collection runner va CLI — hammasi shundan o'tadi. `execute` hech qachon exception tashlamaydi; xato `status: "ERROR"`, `error: true` bilan qaytadi. Retry, `{{var}}`, multipart, fayl parametrlari, javobni parse qilish shu yerda.

## Xatti-harakat o'zgarishlari (ataylab, testlar bilan qotirilgan)
| Eski nuqson | Yangi |
|---|---|
| `/run_one` `{{ var }}` (bo'sh joy bilan) ni almashtirmasdi | `/run` bilan bir xil |
| `/run_one` multipart / fayl parametrini yubormasdi | yuboradi |
| `/run` yaroqsiz JSON body'da xato berardi, `/run_one` xom yuborardi | ikkalasi xom yuboradi (Postman kabi) |
| JSON body `json.loads` → qayta serializatsiya (bo'shliqlar o'zgarardi) | body baytma-bayt yuboriladi, `Content-Type: application/json` o'rnatiladi |
| To'xtatilganda `completed` bittaga ortiq; concurrency'da `max(index)` | `completed` = haqiqiy natijalar soni (lock ostida hisoblagich) |
| To'xtatilganda concurrency navbatidagi so'rovlar baribir yuborilardi | navbatdagilar boshlanmaydi |
| Fayl parametri diskdagi istalgan yo'lni o'qirdi | ADR 0005 |

Hali saqlangan: `form` body xom satr sifatida ketadi (jadval — Bosqich 2), `resp.json()` yoki 500 KB da kesilgan matn (virtual scroll — Bosqich 2).
