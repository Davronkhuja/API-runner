# ADR 0003 — HTTP kutubxona: `requests` → `httpx`

**Holat:** Taklif (tasdiq kutilmoqda) · Bosqich 1 da `requests` saqlanadi

## Taqqoslash
| Talab | requests | httpx |
|---|---|---|
| HTTP/2 | yo'q | `http2=True` (h2 paketi) |
| Timing (DNS/connect/TLS/TTFB) | yo'q | transport/event hook + `httpcore` trace orqali mumkin |
| Cookie jar | ha (Session) | ha (Client) |
| Proxy, client sertifikat, CA | ha | ha |
| Redirect | sukut bo'yicha ergashadi | **sukut bo'yicha ergashmaydi** (aniq `follow_redirects`) |
| `files=(None, value)` multipart | ishlaydi (hozirgi kod shunga tayanadi) | boshqacha API |
| Async | yo'q | bor |

## Qaror
Bosqich 2 boshida `httpx` ga o'tamiz (HTTP/2 va timing talab qilinadi — `requests` bilan ikkalasi ham mumkin emas). Bosqich 1 da **o'tmaymiz**: refaktor va kutubxona almashtirish bir vaqtda xatti-harakat farqini yashirib qo'yadi. Almashtirish bitta joyda: `engine._send()` va `_build_kwargs()`. Characterization testlar (≈50 ta) almashtirishdagi regressiyani ushlaydi.

Xavf: `httpx` da sukut bo'yicha redirect yo'q va multipart API farqli — testlar bilan yopiladi.
