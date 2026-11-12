"""Sozlamalarni yangilash (idempotent): v3.0.1 dagi yagona so'rov tasdig'i (`safety.host_confirm`, sukut YOQIQ) v3.0.2 da `single_confirm` (sukut O'CHIQ) bilan almashtirildi.
Mavjud foydalanuvchida eski belgi yoqilgan bo'lsa ham o'chiriladi (bezovta qiluvchi ogohlantirish)."""


def upgrade_safety_meta(ws):
    m = ws.meta()
    sf = m.get("safety")
    if not isinstance(sf, dict) or "host_confirm" not in sf:
        return False
    new = {k: v for k, v in sf.items() if k != "host_confirm"}
    new.setdefault("single_confirm", False)
    new.setdefault("prod_hosts", [])
    new.setdefault("skip_hosts", [])
    ws.update_meta(safety=new)
    return True
