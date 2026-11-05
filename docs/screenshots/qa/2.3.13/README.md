# QA skrinshotlari v2.3.13

Ssenariylar `tests/e2e/test_qa_scenarios.py` (QA_SHOT_DIR bilan qayta yaratiladi). Oynalar: 1440×900 va 1920×1080, light/dark.

| Ssenariy | 1440x900-dark | 1440x900-light | 1920x1080-dark | 1920x1080-light |
|---|---|---|---|---|
| 01a-json-body-60-lines: POST, 60+ qatorli JSON body (birinchi qator ko'rinadi, muharrir panelni to'ldiradi) | [png](1440x900-dark/01a-json-body-60-lines.png) | [png](1440x900-light/01a-json-body-60-lines.png) | [png](1920x1080-dark/01a-json-body-60-lines.png) | [png](1920x1080-light/01a-json-body-60-lines.png) |
| 01b-after-send-400: javob 400 — xato matni darhol ko'rinadi | [png](1440x900-dark/01b-after-send-400.png) | [png](1440x900-light/01b-after-send-400.png) | [png](1920x1080-dark/01b-after-send-400.png) | [png](1920x1080-light/01b-after-send-400.png) |
| 01c-after-reload: sahifa yangilangandan keyin: body ham, javob ham to'liq | [png](1440x900-dark/01c-after-reload.png) | [png](1440x900-light/01c-after-reload.png) | [png](1920x1080-dark/01c-after-reload.png) | [png](1920x1080-light/01c-after-reload.png) |
| 02a-json-2mb: 2 MB JSON javob | [png](1440x900-dark/02a-json-2mb.png) | [png](1440x900-light/02a-json-2mb.png) | [png](1920x1080-dark/02a-json-2mb.png) | [png](1920x1080-light/02a-json-2mb.png) |
| 02b-json-2mb-after-reload: 2 MB javob, sahifa yangilangandan keyin | [png](1440x900-dark/02b-json-2mb-after-reload.png) | [png](1440x900-light/02b-json-2mb-after-reload.png) | [png](1920x1080-dark/02b-json-2mb-after-reload.png) | [png](1920x1080-light/02b-json-2mb-after-reload.png) |
| 03-image: rasm javob (Preview) | [png](1440x900-dark/03-image.png) | [png](1440x900-light/03-image.png) | [png](1920x1080-dark/03-image.png) | [png](1920x1080-light/03-image.png) |
| 04-empty-204: bo'sh javob (204) | [png](1440x900-dark/04-empty-204.png) | [png](1440x900-light/04-empty-204.png) | [png](1920x1080-dark/04-empty-204.png) | [png](1920x1080-light/04-empty-204.png) |
| 05a-response-bigger: resizer: javob kattalashtirildi | [png](1440x900-dark/05a-response-bigger.png) | [png](1440x900-light/05a-response-bigger.png) | [png](1920x1080-dark/05a-response-bigger.png) | [png](1920x1080-light/05a-response-bigger.png) |
| 05b-response-smaller: resizer: javob kichraytirildi | [png](1440x900-dark/05b-response-smaller.png) | [png](1440x900-light/05b-response-smaller.png) | [png](1920x1080-dark/05b-response-smaller.png) | [png](1920x1080-light/05b-response-smaller.png) |
| 06a-side-by-side: yonma-yon rejim | [png](1440x900-dark/06a-side-by-side.png) | [png](1440x900-light/06a-side-by-side.png) | [png](1920x1080-dark/06a-side-by-side.png) | [png](1920x1080-light/06a-side-by-side.png) |
| 06b-side-response-wider: yonma-yon: javob kengaytirildi | [png](1440x900-dark/06b-side-response-wider.png) | [png](1440x900-light/06b-side-response-wider.png) | [png](1920x1080-dark/06b-side-response-wider.png) | [png](1920x1080-light/06b-side-response-wider.png) |
| 06c-side-response-narrower: yonma-yon: javob toraytirildi | [png](1440x900-dark/06c-side-response-narrower.png) | [png](1440x900-light/06c-side-response-narrower.png) | [png](1920x1080-dark/06c-side-response-narrower.png) | [png](1920x1080-light/06c-side-response-narrower.png) |

## Topilgan va tuzatilgan kamchiliklar
- **Qisqa javob ostida bo'sh oq maydon** (javob matni qutisi kontentga qisqarardi): endi javob qutisi panelni to'ldiradi, uzun bo'lsa panel scroll qiladi.
- **Rasm javob ko'rinmasdi** (test rasmi 1×1 piksel edi) — test rasmi 240×150; Preview rasmni to'g'ri chiqarishi tasdiqlandi.
- **Yonma-yon rejimda so'rov paneli juda tor** (bo'limlar qatori 2 qatorga o'ralar, "Cookie'lar" kesilar edi): yonma-yonda so'rov paneli ≥380px, javob ≥280px; ustma-ustda so'rov ≥240px (muharrir ≥~120px qoladi); bo'limlar qatori o'ralmaydi, torda scroll.
- Takror elementlar (Content-Type, o'lik bo'sh joy), kesilgan kontent (JSON boshi) — topilmadi.
