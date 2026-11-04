"""Yuklangan fayllar ombori: workspace/files/<sha256> (content-addressed, o'zgarmas).

So'rovlar faylga *havola* (ref) bilan murojaat qiladi: ``files/<sha256>/<asl nom>``. Bir xil mazmun bir marta saqlanadi.
Havola ``files/`` bilan boshlanmasa — tashqi (eski UI'dan qolgan) mutlaq yo'l; u engine fayl siyosati bo'yicha tekshiriladi.
Hech kim ishlatmayotgan fayllarni tozalash — faqat foydalanuvchi buyrug'i bilan (Sozlamalar → Fayllar).
"""
import hashlib
import json
import os
import re
import tempfile
import time
from urllib.parse import quote, unquote

DIR = "files"
REF_RE = re.compile(r"^files/([0-9a-f]{64})(?:/(.*))?$")
FIND_RE = re.compile(r"files/([0-9a-f]{64})")
GRACE = 3600          # yangi yuklangan fayl (hali qoralamada saqlanmagan bo'lishi mumkin) kamida 1 soat tegilmaydi


def files_dir(ws_root):
    return os.path.join(ws_root, DIR)


def safe_name(name):
    base = os.path.basename((name or "").replace("\\", "/")) or "file"
    base = re.sub(r"[\x00-\x1f]", "", base).strip()[:120]
    return base or "file"


def make_ref(digest, name):
    return f"{DIR}/{digest}/{quote(safe_name(name), safe='')}"


def parse_ref(ref):
    """('managed', hash, name) | ('external', path, name) | None."""
    if not isinstance(ref, str) or not ref.strip():
        return None
    m = REF_RE.match(ref)
    if m:
        return "managed", m.group(1), unquote(m.group(2) or "") or "file"
    return "external", ref, os.path.basename(ref.split("::")[0])


def store(ws_root, stream, name):
    """Oqimni diskka yozadi (sha256 bilan) va havolani qaytaradi. Katta fayl xotiraga to'liq o'qilmaydi."""
    d = files_dir(ws_root)
    os.makedirs(d, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = stream.read(1 << 20)
                if not chunk:
                    break
                h.update(chunk)
                size += len(chunk)
                out.write(chunk)
        digest = h.hexdigest()
        final = os.path.join(d, digest)
        if os.path.exists(final):
            os.remove(tmp)
            os.utime(final, None)                     # qayta yuklandi — "yangi" deb hisoblanadi (tozalash chegarasi)
        else:
            os.replace(tmp, final)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return {"ref": make_ref(digest, name), "name": safe_name(name), "size": size, "hash": digest}


def resolve(ws_root, ref):
    """Havola -> haqiqiy yo'l (mavjudligi tekshirilmaydi). None — havola bo'sh."""
    p = parse_ref(ref)
    if not p:
        return None
    kind, key, _ = p
    return os.path.join(files_dir(ws_root), key) if kind == "managed" else key.split("::")[0].strip()


def info(ws_root, ref):
    p = parse_ref(ref)
    if not p:
        return {"exists": False, "size": 0, "name": "", "managed": False}
    path = resolve(ws_root, ref)
    ok = bool(path) and os.path.isfile(path)
    return {"exists": ok, "size": os.path.getsize(path) if ok else 0, "name": p[2], "managed": p[0] == "managed"}


def adopt(ws_root, path, name=None):
    """Mavjud mahalliy faylni omborga ko'chiradi (nusxa; asl joyida qoladi)."""
    with open(path, "rb") as f:
        return store(ws_root, f, name or os.path.basename(path))


# ── ishlatilish va tozalash ──
def _json_files(ws_root):
    for base, dirs, names in os.walk(ws_root):
        dirs[:] = [x for x in dirs if x not in (DIR, "backups")]
        for n in names:
            if n.endswith(".json"):
                yield os.path.join(base, n)


def referenced(ws_root):
    """Kollektsiyalar, muhitlar va ochiq tablar (saqlanmagan qoralamalar ham) havola qilgan xeshlar."""
    out = set()
    for p in _json_files(ws_root):
        try:
            with open(p, "r", encoding="utf-8") as f:
                out.update(FIND_RE.findall(f.read()))
        except (OSError, UnicodeDecodeError):
            continue
    return out


def listing(ws_root):
    d = files_dir(ws_root)
    out = []
    if os.path.isdir(d):
        for n in os.listdir(d):
            p = os.path.join(d, n)
            if re.fullmatch(r"[0-9a-f]{64}", n) and os.path.isfile(p):
                st = os.stat(p)
                out.append({"hash": n, "size": st.st_size, "mtime": st.st_mtime})
    return out


def usage(ws_root, now=None):
    now = time.time() if now is None else now
    used = referenced(ws_root)
    allf = listing(ws_root)
    unused = [f for f in allf if f["hash"] not in used and now - f["mtime"] >= GRACE]
    return {"count": len(allf), "size": sum(f["size"] for f in allf),
            "unused_count": len(unused), "unused_size": sum(f["size"] for f in unused)}


def cleanup(ws_root, now=None):
    now = time.time() if now is None else now
    used = referenced(ws_root)
    removed = freed = 0
    for f in listing(ws_root):
        if f["hash"] in used or now - f["mtime"] < GRACE:
            continue
        try:
            os.remove(os.path.join(files_dir(ws_root), f["hash"]))
            removed += 1
            freed += f["size"]
        except OSError:
            pass
    return {"removed": removed, "freed": freed}


def resolve_spec(spec, ws_root):
    """/run_one va /run uchun: spec ichidagi havolalarni haqiqiy yo'lga aylantiradi (engine faqat yo'l biladi)."""
    spec = dict(spec)
    fields = []
    for fld in spec.get("multipart_fields") or []:
        if fld.get("type") == "file":
            fld = dict(fld, files=[dict(f, path=resolve(ws_root, f.get("ref")) or "", name=f.get("name") or (parse_ref(f.get("ref")) or ("", "", ""))[2])
                                   for f in fld.get("files") or []])
        fields.append(fld)
    if fields:
        spec["multipart_fields"] = fields
    if spec.get("body_file"):
        spec["body_file"] = resolve(ws_root, spec["body_file"]) or spec["body_file"]
    return spec


def refs_in(obj):
    """Ixtiyoriy JSON ichidagi barcha 'files/<hash>' xeshlari (testlar/diagnostika uchun)."""
    return set(FIND_RE.findall(json.dumps(obj)))
