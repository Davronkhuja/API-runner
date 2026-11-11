# ADR 0011 — Sayqal, xavfsizlik, paketlash (Bosqich 8, v3.0.0)

**Holat:** Qabul qilingan

## Qaror
- **Katta javob:** matnga aylantirishda reaktiv proxy'lar chetlab o'tiladi (`toRaw`); virtual scroll saqlanadi. Ishlash o'lchovlari qayta ishlab chiqariladi (`tools/perf_bench.py`).
- **Xavfsizlik:** Origin — qat'iy bir xil manba; sarlavhalar `after_request` da; fayl siyosati — eng kam ildizlar (yuklash + `workspace/files`); `*.localhost` ruxsat (RFC 6761).
- **UX:** sidebar sarlavhasida 2 asosiy tugma + «⋯» menyu; yagona `StateBlock` (loading/error/empty); `Dialog` Esc'ni modul darajasidagi stack orqali eng ustki dialogga yo'naltiradi; tanishtiruv `navigator.webdriver` da o'chiq (testlar uchun), `?onboarding=1` majburlaydi.
- **Paketlash:** `apirunner/desktop.py` (loopback + tasodifiy port + pywebview); ma'lumot foydalanuvchi papkasida (`APIRUNNER_HOME`); PyInstaller `.app` (imzosiz). Windows/Linux — ochiq.
