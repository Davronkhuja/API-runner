"""Rejalashtirilgan run'lar (monitor): cron ifoda bo'yicha collection/papkani yurgizadi, natijani run tarixiga (kind=monitor) yozadi,
xatoda macOS bildirishnomasi yuboradi. Ro'yxat — workspace/monitors.json (workspace'ga bog'liq)."""
import datetime as dt
import os
import subprocess
import sys
import threading
import time
import uuid

import json

from .storage.atomic import atomic_write_json

_FIELDS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
_NAMES = {3: {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())},
          4: {d: i for i, d in enumerate("sun mon tue wed thu fri sat".split())}}


class CronError(ValueError):
    pass


def _field(text, idx):
    lo, hi = _FIELDS[idx]
    out = set()
    for part in text.lower().split(","):
        step = 1
        if "/" in part:
            part, _, s = part.partition("/")
            if not s.isdigit() or int(s) < 1:
                raise CronError(f"Noto'g'ri qadam: {text}")
            step = int(s)

        def num(x):
            x = _NAMES.get(idx, {}).get(x, x)
            if isinstance(x, str) and not x.isdigit():
                raise CronError(f"Noto'g'ri qiymat: {x}")
            n = int(x)
            if idx == 4 and n == 7:
                n = 0
            if not lo <= n <= hi:
                raise CronError(f"Qiymat {lo}–{hi} oralig'ida bo'lsin: {x}")
            return n
        if part == "*":
            a, b = lo, hi
        elif "-" in part:
            x, _, y = part.partition("-")
            a, b = num(x), num(y)
            if idx == 4 and y == "7":
                b = 7
        else:
            a = num(part)
            b = hi if step > 1 else a
        if a > b:
            raise CronError(f"Noto'g'ri oraliq: {part}")
        out.update(v % 7 if idx == 4 else v for v in range(a, b + 1, step))
    return out


def parse_cron(expr):
    """5 maydonli cron: daqiqa soat kun oy hafta-kuni (`*`, `a-b`, `a,b`, `*/n`, oy/kun nomlari). Qaytaradi: (maydonlar, dom_cheklangan, dow_cheklangan)."""
    parts = (expr or "").split()
    if len(parts) != 5:
        raise CronError("Cron ifoda 5 maydondan iborat bo'lsin: daqiqa soat kun oy hafta-kuni")
    sets = [_field(p, i) for i, p in enumerate(parts)]
    return sets, parts[2] != "*", parts[4] != "*"


def matches(parsed, when):
    sets, dom_r, dow_r = parsed
    if when.minute not in sets[0] or when.hour not in sets[1] or when.month not in sets[3]:
        return False
    dom, dow = when.day in sets[2], ((when.weekday() + 1) % 7) in sets[4]
    return (dom or dow) if dom_r and dow_r else (dom and dow)


def next_run(expr, after=None, limit_days=366):
    parsed = parse_cron(expr)
    t = (after or dt.datetime.now()).replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    for _ in range(limit_days * 1440):
        if matches(parsed, t):
            return t
        t += dt.timedelta(minutes=1)
    return None


def notify(title, message):
    """macOS bildirishnomasi; boshqa tizimda jim o'tkazib yuboriladi."""
    if sys.platform != "darwin" or os.environ.get("APIRUNNER_TESTING"):
        return False
    esc = lambda s: str(s).replace("\\", "\\\\").replace('"', '\\"')
    try:
        subprocess.run(["osascript", "-e", f'display notification "{esc(message)}" with title "{esc(title)}"'], timeout=10, check=False, capture_output=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


class MonitorStore:
    def __init__(self, ws_root):
        self.path = os.path.join(ws_root, "monitors.json")
        self.lock = threading.RLock()

    def list(self):
        with self.lock:
            return read_json(self.path, {"monitors": []}).get("monitors", [])

    def _save(self, items):
        atomic_write_json(self.path, {"monitors": items})

    def get(self, mid):
        return next((m for m in self.list() if m["id"] == mid), None)

    def upsert(self, data, mid=None):
        parse_cron(data.get("cron"))
        if not data.get("collection_id"):
            raise ValueError("Collection tanlanmagan")
        with self.lock:
            items = self.list()
            cur = next((m for m in items if m["id"] == mid), None) if mid else None
            if mid and not cur:
                raise KeyError(mid)
            rec = {"id": cur["id"] if cur else uuid.uuid4().hex[:12], "name": (data.get("name") or "").strip() or "Monitor", "collection_id": data["collection_id"],
                   "folder": data.get("folder") or None, "env_name": data.get("env_name") or "", "cron": data["cron"].strip(), "enabled": bool(data.get("enabled", True)),
                   "notify": bool(data.get("notify", True)), "last": (cur or {}).get("last")}
            items = [rec if m["id"] == rec["id"] else m for m in items] if cur else items + [rec]
            self._save(items)
            return rec

    def set_last(self, mid, last):
        with self.lock:
            items = self.list()
            for m in items:
                if m["id"] == mid:
                    m["last"] = last
            self._save(items)

    def remove(self, mid):
        """Monitor — sozlama (foydalanuvchi ma'lumoti emas: so'rovlar/collectionlar Savatda); natijalar run tarixida qoladi."""
        with self.lock:
            items = self.list()
            self._save([m for m in items if m["id"] != mid])
            return len(items) != len(self.list())


def execute(app, mon, now=None):
    """Monitorni bir marta yurgizadi (bloklaydi). Qaytaradi: last-natija lug'ati."""
    from .core.planner import build_plan
    ext = app.extensions
    ws, mgr, runs = ext["workspace"], ext["run_manager"], ext["runs"]
    started = time.time()
    last = {"at": started, "run_id": None, "ok": False, "failures": 0, "total": 0, "error": None}
    try:
        col = ws.get_collection(mon["collection_id"])
        if not col:
            raise ValueError("Collection topilmadi")
        settings = {"delay_ms": 0, "parallel": 1, "retry": 0, "timeout": 30, "ssl": True, "stop_on_error": False, "bail": False,
                    "save_vars": False, "save_responses": False, "include_response": False}
        plan, _ = build_plan(col, mon.get("folder"), mon.get("env_name") or "", ws.root, settings, None, None, 30, False)
        plan["kind"] = "monitor"
        plan["scope_name"] = f"{mon['name']} · {plan['scope_name']}"
        run = mgr.start(plan)
        last["run_id"] = run.id
        for _ in run.stream(0):
            pass
        run.thread.join(timeout=5)
        from .cli import summarize
        full = runs.get(run.id)
        sm = summarize(full, False)
        last.update(failures=sm["failures"], total=sm["requests"], error=(full.get("summary") or {}).get("error"))
        last["ok"] = not sm["failures"] and not last["error"]
    except Exception as e:      # noqa: BLE001 — monitor hech qachon scheduler'ni yiqitmasin
        last["error"] = str(e) or e.__class__.__name__
    last["duration"] = round(time.time() - started, 2)
    ext["monitors"].set_last(mon["id"], last)
    if not last["ok"] and mon.get("notify", True):
        notify(f"API Runner: {mon['name']} xato", last["error"] or f"{last['failures']} ta so'rov muvaffaqiyatsiz")
    return last


class Scheduler:
    """Har ~15 s da joriy daqiqani tekshiradi; har monitor bir daqiqada bir martadan ko'p yurmaydi, yurayotgani qayta boshlanmaydi."""
    def __init__(self, app, interval=15):
        self.app, self.interval = app, interval
        self.stop_ev = threading.Event()
        self.fired = {}
        self.busy = set()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._loop, daemon=True, name="monitor-scheduler")
        self.thread.start()

    def stop(self):
        self.stop_ev.set()

    def _loop(self):
        while not self.stop_ev.wait(self.interval):
            self.tick()

    def tick(self, now=None):
        now = (now or dt.datetime.now()).replace(second=0, microsecond=0)
        store = self.app.extensions.get("monitors")
        if not store:
            return []
        started = []
        for mon in store.list():
            if not mon.get("enabled") or mon["id"] in self.busy or self.fired.get(mon["id"]) == now:
                continue
            try:
                if not matches(parse_cron(mon["cron"]), now):
                    continue
            except CronError:
                continue
            self.fired[mon["id"]] = now
            self.busy.add(mon["id"])
            started.append(mon["id"])
            threading.Thread(target=self._go, args=(mon,), daemon=True).start()
        return started

    def _go(self, mon):
        try:
            execute(self.app, mon)
        finally:
            self.busy.discard(mon["id"])
