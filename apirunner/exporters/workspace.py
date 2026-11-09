"""Butun workspace zaxirasi (zip): collection'lar, muhitlar, globals, sozlamalar, biriktirilgan fayllar, (ixtiyoriy) tarix/javoblar bazasi.

Zip ichida `manifest.json` bor — import shu orqali tanib oladi. Muhit qiymatlari AYNAN saqlanganidek (Initial va Current, secret'lar bilan) ketadi:
bu zaxira, Postman eksporti emas; faylni begonalarga bermang.
"""
import copy
import io
import json
import os
import sqlite3
import tempfile
import time
import zipfile

from .. import __version__

KIND = "api-runner-workspace"


MAGIC = b"APRZENC1"
SENSITIVE_AUTH = {"token", "password", "secret", "value", "clientSecret", "accessToken", "refresh_token", "privateKey", "passphrase", "authKey", "secretKey", "sessionToken", "consumerSecret", "tokenSecret", "apiKey"}


class PasswordRequired(ValueError):
    pass


class BadPassword(ValueError):
    pass


def _kdf(password, salt):
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    return Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(password.encode("utf-8"))


def encrypt(data, password):
    """AES-256-GCM, kalit scrypt'dan: MAGIC | salt(16) | nonce(12) | shifrmatn+tag."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    salt, nonce = os.urandom(16), os.urandom(12)
    return MAGIC + salt + nonce + AESGCM(_kdf(password, salt)).encrypt(nonce, data, MAGIC)


def is_encrypted(data):
    return isinstance(data, (bytes, bytearray)) and data[:len(MAGIC)] == MAGIC


def decrypt(data, password):
    if not password:
        raise PasswordRequired("Zip parol bilan shifrlangan — parolni kiriting")
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    h = len(MAGIC)
    try:
        return AESGCM(_kdf(password, data[h:h + 16])).decrypt(data[h + 16:h + 28], data[h + 28:], MAGIC)
    except InvalidTag as e:
        raise BadPassword("Parol noto'g'ri (yoki fayl buzilgan)") from e


def _scrub_auth(a):
    if isinstance(a, dict):
        t = a.get("type")
        for r in a.get(t) or [] if isinstance(a.get(t), list) else []:
            if isinstance(r, dict) and r.get("key") in SENSITIVE_AUTH and isinstance(r.get("value"), str) and not (t == "apikey" and r.get("key") == "key"):
                r["value"] = ""


def _scrub_vars(rows):
    for v in rows or []:
        if isinstance(v, dict):
            v.pop("current", None)
            if v.get("type") == "secret":
                v["value"] = ""


def scrub_collection(col):
    """Maxfiy o'zgaruvchi qiymatlari, Current va auth hisob ma'lumotlari bo'shatiladi (nusxa ustida)."""
    col = copy.deepcopy(col)
    _scrub_auth(col.get("auth"))
    _scrub_vars(col.get("variable"))

    def walk(items):
        for it in items or []:
            _scrub_auth(it.get("auth"))
            _scrub_vars(it.get("variable"))
            if "item" in it:
                walk(it["item"])
            else:
                _scrub_auth((it.get("request") or {}).get("auth"))
    walk(col.get("item"))
    return col


def scrub_env(env):
    env = copy.deepcopy(env)
    _scrub_vars(env.get("values"))
    return env


def export_zip(ws, include_state=False, include_secrets=False, password=None):
    """Qaytaradi: (bytes, manifest). Sukut: maxfiy va Current qiymatlarsiz, tarix/javoblar bazasisiz. `password` — AES-256-GCM bilan shifrlash."""
    include_state = bool(include_state and include_secrets)             # tarix/javoblar/cookie'larda token bo'lishi mumkin
    buf = io.BytesIO()
    counts = {"collections": 0, "environments": 0, "files": 0}

    def put(z, arc, path, scrub=None):
        if scrub is None or include_secrets:
            z.write(path, arc)
        else:
            z.writestr(arc, json.dumps(scrub(ws._read(path)), indent=2, ensure_ascii=False))
    with ws.lock, zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(ws._p("collections"))):
            if fn.endswith(".json"):
                put(z, f"collections/{fn}", ws._p("collections", fn), scrub_collection)
                counts["collections"] += 1
        for fn in sorted(os.listdir(ws._p("environments"))):
            if fn.endswith(".json"):
                put(z, f"environments/{fn}", ws._p("environments", fn), scrub_env)
                counts["environments"] += 1
        if os.path.exists(ws._p("globals.json")):
            put(z, "globals.json", ws._p("globals.json"), scrub_env)
        if os.path.exists(ws._p("workspace.json")):
            z.write(ws._p("workspace.json"), "workspace.json")
        fdir = ws._p("files")
        if os.path.isdir(fdir):
            for root, _d, names in os.walk(fdir):
                for n in names:
                    if n.endswith(".part"):
                        continue
                    full = os.path.join(root, n)
                    z.write(full, os.path.relpath(full, ws.root).replace(os.sep, "/"))
                    counts["files"] += 1
        state = ws._p("state.db")
        if include_state and os.path.exists(state):
            with tempfile.TemporaryDirectory() as td:
                snap = os.path.join(td, "state.db")
                src, dst = sqlite3.connect(state), sqlite3.connect(snap)
                try:
                    src.backup(dst)                                    # izchil snapshot (WAL ham hisobga olinadi)
                finally:
                    dst.close(); src.close()
                z.write(snap, "state.db")
        manifest = {"kind": KIND, "app_version": __version__, "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "includes_state": include_state, "secrets_included": bool(include_secrets), "encrypted": bool(password), **counts}
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
    data = buf.getvalue()
    return (encrypt(data, password) if password else data), manifest


def read_zip(data, password=None):
    """zip bytes -> {manifest, collections[], environments[], globals, files{name: bytes}}. Noto'g'ri zip — ValueError; shifrlangan bo'lsa parol kerak."""
    if is_encrypted(data):
        data = decrypt(data, password)
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ValueError("Zip fayl buzuq") from e
    names = set(z.namelist())
    if "manifest.json" not in names:
        raise ValueError("Bu API Runner workspace zaxirasi emas (manifest.json yo'q)")
    try:
        manifest = json.loads(z.read("manifest.json"))
    except ValueError as e:
        raise ValueError("manifest.json buzuq") from e
    if manifest.get("kind") != KIND:
        raise ValueError("Bu API Runner workspace zaxirasi emas")
    total = sum(i.file_size for i in z.infolist())
    if total > 500 * 1024 * 1024:
        raise ValueError("Zip juda katta (500 MB dan ortiq ochilgan hajm)")

    def load(prefix):
        out = []
        for n in sorted(names):
            if n.startswith(prefix) and n.endswith(".json") and ".." not in n:
                out.append(json.loads(z.read(n)))
        return out
    g = json.loads(z.read("globals.json")) if "globals.json" in names else None
    files = {n: z.read(n) for n in names if n.startswith("files/") and not n.endswith("/") and ".." not in n}
    return {"manifest": manifest, "collections": load("collections/"), "environments": load("environments/"), "globals": g, "files": files}
