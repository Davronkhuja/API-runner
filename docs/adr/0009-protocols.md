# ADR 0009 — WebSocket, SSE va GraphQL (Bosqich 6)

**Holat:** Qabul qilingan

## Qaror
- **Ulanishni brauzer emas, SERVER ochadi** (`core/protocols.py`): brauzer WebSocket'da custom header/auth/TLS sozlamasini qo'ya olmaydi. Sessiya xotirada, hodisalar jurnali (≤5000) bilan; UI `GET /api/protocols/<id>/stream?from=` (SSE) orqali oqim oladi, yuborish — `POST /send`, yopish — `POST /close`. Flask dev-serveri WebSocket'ni qo'llamaydi, shuning uchun UI↔server aloqasi SSE + POST.
- **So'rov tabi sifatida saqlanadi:** `draft.protocol = http|ws|sse`; collection'da oddiy Postman so'rovi (`method GET`, `ws://…`) + `x-apirunner.protocol/proto` (subprotokollar, xabar shablonlari, qayta ulanish, SSE metodi). Postman'ga eksportda oddiy so'rov bo'lib chiqadi. Daraxtda `WS`/`SSE` badge; Runner/Batch ularni o'tkazib yuboradi.
- **O'zgaruvchilar/auth/skriptlar:** `specFor` + `_build_kwargs` (HTTP bilan bir xil), xabarlardagi `{{o'zgaruvchi}}`/`{{$guid}}` server tomonida; pre-request skriptlari ulanishdan oldin (`run_prerequest`) header/o'zgaruvchini o'zgartirishi mumkin. Digest/NTLM WebSocket handshake'ida qo'llab-quvvatlanmaydi (aniq xabar).
- **Qayta ulanish:** eksponensial kechikish (≤30 s), `max_attempts` (0 = cheksiz), 2 s dan uzoq turgan ulanish hisobni yangilaydi; SSE — `Last-Event-ID` va server `retry:`; foydalanuvchi yopsa qayta ulanmaydi.
- **GraphQL — HTTP so'rov bo'lib qoladi** (body rejimi `graphql`; skriptlar, tarix, auth to'liq ishlaydi). Qo'shildi: `/run_one` orqali introspection, `graphql-js` bilan sxema, schema explorer, `graphql-language-service` avtoto'ldirishi va `validate()` lint, variables tekshiruvi. Sxema keshi — xotirada (sahifa yangilansa qayta yuklanadi).
- Socket.IO va gRPC — ixtiyoriy, bajarilmadi (ROADMAP'da qoldi).
