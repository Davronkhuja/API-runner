# Postman ommaviy namunalari (muvofiqlik testlari uchun)

Asl nusxalar (o'zgartirilmagan), Apache-2.0:

| Fayl | Manba |
|---|---|
| `twitter.json`, `echo.json`, `helpers.json` | postmanlabs/postman-collection-transformer `examples/v2.1.0/` |
| `newman_nested_requests.json` | postmanlabs/newman `test/fixtures/run/nested-requests-report-test.json` |
| `newman_reporter_sample.json` | postmanlabs/newman-reporter-remote `test/fixtures/sample-collection.json` |
| `catURL.json` | postmanlabs/node-doc-kube `catURL.postman_collection.json` |

`compat_flow.postman_collection.json` — shu namunalardagi naqshlar (pre-request'da token olish, `setNextRequest` oqimi, legacy `tests[]`) asosida yozilgan murakkab collection.
Testlar so'rov hostlarini lokal echo serverga almashtiradi (tashqi tarmoq yo'q).
