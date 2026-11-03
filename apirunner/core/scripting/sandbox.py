"""Skript sandbox (ADR 0007): quickjs-ng kontekstida `pm.*` skriptlarini bajarish.

Xavfsizlik chegarasi: kontekstda host ob'ekti, fayl, tarmoq, modul yuklovchi, hatto Python callable ham YO'Q (quickjs vaqt limiti
bilan JS'dan Python'ni chaqirishga ruxsat bermaydi). Host bilan aloqa — JS tomonidagi so'rov navbati: pm.sendRequest va cookie jar
so'rovlarini Python event loop bajaradi va Promise'ni hal qiladi. Har bajarish (thread) o'z `quickjs.Context` ini yaratadi va tugagach
tashlaydi — kontekstlar thread'lar orasida bo'lishilmaydi.
"""
import importlib.metadata
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

try:                                    # ixtiyoriy bog'liqlik (requirements-scripts.txt): o'rnatilmagan bo'lsa skriptlar o'chiq
    import quickjs
except ImportError:                     # pragma: no cover - muhitga bog'liq
    quickjs = None

HERE = Path(__file__).resolve().parent
LIB_FILES = {"chai": "chai.js", "lodash": "lodash.min.js", "crypto-js": "crypto-js.js", "dayjs": "dayjs.min.js", "moment": "moment.min.js"}
INSTALL_HINT = "pip install quickjs-ng   (yoki: .venv/bin/python -m pip install -r requirements-scripts.txt)"
_cache = {}
_cache_lock = threading.Lock()


def _libs_json():
    return json.dumps({name: _read(name) for name in LIB_FILES})


def available():
    return quickjs is not None


def version():
    try:
        return importlib.metadata.version("quickjs-ng")
    except importlib.metadata.PackageNotFoundError:
        return None


def _read(name):
    with _cache_lock:
        if name not in _cache:
            path = HERE / ("prelude.js" if name == "__prelude__" else "libs/" + LIB_FILES[name])
            _cache[name] = path.read_text(encoding="utf-8")
        return _cache[name]


@dataclass
class Limits:
    timeout_ms: int = 10000        # skriptning umumiy devor vaqti (async, taymer va pm.sendRequest bilan)
    memory_mb: int = 64
    max_requests: int = 10         # bitta bajarishdagi pm.sendRequest soni
    max_depth: int = 5             # callback ichidan callback ... chuqurligi
    stack_kb: int = 512

    RANGES = {"timeout_ms": (100, 300000), "memory_mb": (8, 1024), "max_requests": (0, 200)}

    @classmethod
    def from_meta(cls, meta):
        raw = (meta or {}).get("script_limits") or {}
        out = cls()
        for k, (lo, hi) in cls.RANGES.items():
            try:
                v = int(raw.get(k, getattr(out, k)))
            except (TypeError, ValueError):
                continue
            setattr(out, k, max(lo, min(hi, v)))
        return out

    def as_dict(self):
        return {"timeout_ms": self.timeout_ms, "memory_mb": self.memory_mb, "max_requests": self.max_requests}


DEFAULT_LIMITS = Limits().as_dict()


@dataclass
class ScriptSource:
    source: str
    kind: str                       # prerequest | test
    scope: str = "request"          # collection | folder | request
    name: str = ""
    id: str = ""

    def origin(self):
        return {"kind": self.kind, "scope": self.scope, "name": self.name, "id": self.id}


class ScriptTimeout(Exception):
    pass


def parse_error(text):
    """quickjs istisno matnidan {name, message, stack, line}."""
    text = str(text)
    first = text.strip().splitlines()[0] if text.strip() else "Error"
    name, _, msg = first.partition(": ")
    if not msg:
        name, msg = "Error", first
    m = re.search(r"<input>:(\d+)", text)
    return {"name": name.strip(), "message": msg.strip(), "stack": text.strip(), "line": int(m.group(1)) if m else None}


@dataclass
class Report:
    scopes: dict = field(default_factory=dict)
    changed: dict = field(default_factory=dict)
    tests: list = field(default_factory=list)
    logs: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    next_set: bool = False
    next_request: object = None
    skip: bool = False
    request: dict = None
    orig_request: dict = None
    aborted: bool = False


class ScriptSession:
    """Bitta so'rov bajarilishi (pre + test skriptlari) uchun bitta kontekst. Faqat yaratgan thread'ida ishlating."""

    def __init__(self, scopes, request, info, limits, host, active_env=True, env_name=None, cookies=None):
        if quickjs is None:
            raise RuntimeError("quickjs-ng o'rnatilmagan")
        self.limits, self.host = limits, host
        self.deadline = time.monotonic() + limits.timeout_ms / 1000.0
        self.sent = 0
        self.aborted = False
        self.errors = []
        self.ctx = quickjs.Context()
        self.ctx.set_memory_limit(limits.memory_mb * 1024 * 1024)
        self.ctx.set_max_stack_size(limits.stack_kb * 1024)
        self._eval("globalThis.__LIBS=" + _libs_json())            # matn sifatida (baholanmaydi): JS tomonida lazy eval
        self._eval("globalThis.__POOL=" + json.dumps(list(os.urandom(8192))))   # crypto.getRandomValues uchun
        self._eval(_read("__prelude__"))
        self._eval("__init(%s)" % json.dumps(json.dumps({
            "scopes": scopes, "request": request, "info": info, "activeEnv": active_env, "envName": env_name, "cookies": cookies or []})))

    # ── host navbati ──
    def _serve(self, item):
        """Bitta host so'rovi (send | cookie) → JSON javob. Istisno JS ga chiqmaydi — xato obyekti qaytadi."""
        try:
            data = item["payload"]
            if item["kind"] == "send":
                if self.sent >= self.limits.max_requests:
                    return {"error": {"message": "pm.sendRequest soni chegarasi (%d) oshdi — Sozlamalar → Skriptlar" % self.limits.max_requests}}
                if data.get("depth", 1) > self.limits.max_depth:
                    return {"error": {"message": "pm.sendRequest ichma-ich chuqurligi chegarasi (%d) oshdi" % self.limits.max_depth}}
                self.sent += 1
                return self.host.send(data["req"])
            return self.host.cookie(data)
        except Exception as exc:        # noqa: BLE001
            return {"error": {"message": str(exc)}} if item["kind"] == "send" else {"error": str(exc)}

    # ── bajarish ──
    def _remaining(self):
        return self.deadline - time.monotonic()

    def _eval(self, code):
        rem = self._remaining()
        if rem <= 0:
            raise ScriptTimeout()
        self.ctx.set_time_limit(rem)
        return self.ctx.eval(code)

    def _classify(self, err):
        """JS ichida ushlangan InternalError'larni ham aniq nomlaymiz (xotira)."""
        if err["name"] == "InternalError" and "out of memory" in err["message"]:
            err.update(name="MemoryError", message="Skript xotira chegarasidan oshdi (%d MB) — Sozlamalar → Skriptlar" % self.limits.memory_mb)
        return err

    def _fail(self, exc, origin):
        text = str(exc)
        if "interrupted" in text or isinstance(exc, ScriptTimeout):
            err = {"name": "TimeoutError", "message": "Skript vaqt chegarasidan oshdi (%d ms) — Sozlamalar → Skriptlar" % self.limits.timeout_ms, "stack": "", "line": None}
            self.aborted = True
        elif "out of memory" in text:
            err = {"name": "MemoryError", "message": "Skript xotira chegarasidan oshdi (%d MB) — Sozlamalar → Skriptlar" % self.limits.memory_mb, "stack": "", "line": None}
            self.aborted = True
        else:
            err = parse_error(text)
        err["origin"] = origin
        self.errors.append(err)

    def _drain(self, origin):
        """Event loop: pending job'lar va taymerlar tugaguncha (umumiy vaqt chegarasi bilan)."""
        ctx = self.ctx
        while True:
            while True:
                rem = self._remaining()
                if rem <= 0:
                    raise ScriptTimeout()
                ctx.set_time_limit(rem)
                if not ctx.execute_pending_job():
                    break
            q = ctx.eval("__takeHost()")
            if q:                                   # pm.sendRequest / cookie so'rovlari (blokirovka qiladi, vaqt chegarasi keyin tekshiriladi)
                for item in json.loads(q):
                    out = self._serve(item)
                    self._eval("__hostResolve(%d, %s)" % (item["id"], json.dumps(json.dumps(out))))
                continue
            delay = ctx.eval("__nextTimerDelay()")
            if delay is None or delay < 0:
                return
            rem = self._remaining()
            if delay / 1000.0 > rem:
                time.sleep(max(0.0, rem))
                raise ScriptTimeout()
            if delay > 0:
                time.sleep(delay / 1000.0)
            self._eval("__runDueTimers()")

    def set_response(self, response):
        self._eval("__setResponse(%s)" % json.dumps(json.dumps(response)))

    def run(self, script):
        self._seq = getattr(self, "_seq", 0) + 1
        origin = {**script.origin(), "idx": self._seq}
        if self.aborted:
            self.errors.append({"name": "Skipped", "message": "Oldingi skript vaqt/xotira chegarasidan oshgani uchun o'tkazib yuborildi", "stack": "", "line": None, "origin": origin})
            return
        try:
            self._eval("__begin(%s)" % json.dumps(json.dumps(origin)))
            self._eval("(async()=>{" + script.source + "\n})().catch(__onScriptError)")
            self._drain(origin)
            self._eval("__end()")
        except Exception as exc:        # noqa: BLE001 — sintaksis xato, vaqt/xotira chegarasi
            self._fail(exc, origin)

    def set_sent_request(self, view):
        """Test skriptlari uchun: pm.request — yuborilgan (o'zgaruvchilari yechilgan) so'rov."""
        self._eval("__setSent(%s)" % json.dumps(json.dumps(view)))

    def set_event(self, name):
        self._eval("__setEvent(%s)" % json.dumps(name))

    def collect_state(self):
        """Oraliq holat (pre-request tugagach): scope'lar, o'zgargan so'rov, skip. Kontekst tirik qoladi."""
        try:
            self.ctx.set_time_limit(5.0)
            d = json.loads(self.ctx.eval("__collect()"))
            return {"scopes": d["scopes"], "request": d.get("request"), "skip": bool(d["skip"])}
        except Exception as exc:        # noqa: BLE001
            self._fail(exc, {"kind": "collect", "scope": "", "name": "", "id": ""})
            return {"scopes": {k: {} for k in ("globals", "collection", "environment", "data", "local")}, "request": None, "skip": False}

    def collect(self):
        try:
            self.ctx.set_time_limit(5.0)        # umumiy vaqt tugagan bo'lsa ham natijani olish uchun alohida qisqa chegara
            self.ctx.eval("__finish()")
            d = json.loads(self.ctx.eval("__collect()"))
        except Exception as exc:        # noqa: BLE001
            self._fail(exc, {"kind": "collect", "scope": "", "name": "", "id": "", "idx": 10**6})
            return Report(errors=self.errors, aborted=True)
        return Report(
            scopes=d["scopes"], changed=d["changed"], tests=d["tests"], logs=d["logs"],
            errors=[self._classify(e) for e in sorted(self.errors + d["errors"], key=lambda e: (e.get("origin") or {}).get("idx", 0))],
            next_set=bool(d.get("nextSet")), next_request=d.get("next"), skip=bool(d["skip"]), request=d.get("request"),
            orig_request=json.loads(d["orig"]) if d.get("orig") else None, aborted=self.aborted)
