"""Bir workspace'ni bir vaqtda bir nechta API Runner nusxasi ochmasligi uchun «sessiya qulfi» (`.session.lock`).

Qulf jarayon umri davomida ushlab turiladi (fcntl.flock, bloklamaydigan). Ikkinchi nusxa ochilishi TO'XTATILMAYDI, lekin UI'da aniq ogohlantirish chiqadi:
ikkala nusxa ham yozsa, o'zgarishlar bir-biriga to'qnashadi (rev konflikti) yoki oxirgi yozuv ustun keladi. Ma'lumot egasi ma'lumot: pid, versiya, boshlangan vaqt.
Testlarda (APIRUNNER_TESTING) o'chiq — `APIRUNNER_INSTANCE_LOCK=1` bilan yoqiladi.
"""
import json
import os
import time

try:
    import fcntl
except ImportError:                      # Windows: tekshirilmaydi
    fcntl = None

NAME = ".session.lock"


def enabled():
    return fcntl is not None and (not os.environ.get("APIRUNNER_TESTING") or os.environ.get("APIRUNNER_INSTANCE_LOCK") == "1")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


class InstanceLock:
    def __init__(self, ws_root, version="", mode=""):
        self.path = os.path.join(ws_root, NAME)
        self.owned, self.holder, self._fd = True, {}, None
        if not enabled():
            return
        os.makedirs(ws_root, exist_ok=True)
        self._fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.owned = False
            self.holder = _read(self.path)
            os.close(self._fd)
            self._fd = None
            return
        info = {"pid": os.getpid(), "version": version, "mode": mode, "started": time.time()}
        os.ftruncate(self._fd, 0)
        os.write(self._fd, json.dumps(info).encode())

    def release(self):
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None

    def as_json(self):
        return {"conflict": not self.owned, "holder": self.holder if not self.owned else None, "path": os.path.dirname(self.path)}


def probe(ws_root):
    """Workspace hozir boshqa jarayonda ochiqmi? Qaytaradi: egasi haqida ma'lumot (dict) yoki None. Qulfni egallamaydi (darhol qo'yib yuboradi)."""
    if fcntl is None:
        return None
    path = os.path.join(ws_root, NAME)
    if not os.path.exists(path):
        return None
    fd = os.open(path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return None
    except OSError:
        return _read(path) or {"pid": None}
    finally:
        os.close(fd)
