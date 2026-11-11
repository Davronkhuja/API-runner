"""Run engine (Collection Runner v2): reja (so'rovlar + data qatorlari + sozlamalar) server tomonida bajariladi, har qadam SSE hodisasi va SQLite yozuvi bo'ladi.

Postman Runner semantikasi (core/flow.py bilan bir xil): tartib bilan bajarish, iteratsiyalar, `setNextRequest(nom|null)`, skriptlar, "birinchi xatoda to'xtash".
Parallel > 1 bo'lsa so'rovlar bir vaqtda bajariladi va `setNextRequest` e'tiborga olinmaydi (hodisa orqali xabar qilinadi).
"""
import concurrent.futures
import json
import threading
import time

from .scripted import Services, run_item

MAX_STEPS = 1000
EVENT_BODY_LIMIT = 64 * 1024


def _is_ok(res):
    return isinstance(res.get("status"), int) and res["status"] < 400


def _tests_of(res):
    s = res.get("scripts") or {}
    return [{"name": t.get("name", ""), "passed": bool(t.get("passed")), "skipped": bool(t.get("skipped")), **({"error": (t.get("error") or {}).get("message", "")} if t.get("error") else {})}
            for t in s.get("tests") or []]


def _text(v):
    if v is None:
        return ""
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, indent=2)


def _failed_step(res):
    """CLI `--bail`: so'rov xatosi (tarmoq) yoki yiqilgan test."""
    return res.get("status") == "ERROR" or any(not t["passed"] for t in _tests_of(res))


class Run:
    def __init__(self, run_id, number, plan, services, store, db):
        self.id, self.number, self.plan, self.services, self.store, self.db = run_id, number, plan, services, store, db
        self.events = []
        self.cond = threading.Condition()
        self.stop = threading.Event()
        self.status = "running"
        self.thread = None

    # ── hodisalar ──
    def emit(self, kind, data):
        with self.cond:
            self.events.append({"type": kind, "data": data})
            self.cond.notify_all()

    def stream(self, start=0):
        """Generator: (kind, data); tugagach (done) to'xtaydi."""
        i = start
        while True:
            with self.cond:
                while i >= len(self.events):
                    self.cond.wait(timeout=15)
                    if i >= len(self.events):
                        yield ("ping", {})
                ev = self.events[i]
            i += 1
            yield (ev["type"], ev["data"])
            if ev["type"] == "done":
                return

    # ── bajarish ──
    def start(self):
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    def _snapshot(self):
        ws = self.services.ws
        if ws is None:
            return None
        snap = {"globals": ws.get_globals()}
        env_id = ws.meta().get("active_environment_id")
        if env_id:
            try:
                snap["env"] = ws.get_environment(env_id)
            except Exception:  # noqa: BLE001
                pass
        cid = (self.plan.get("scope") or "").split(":")[0]
        if cid:
            try:
                snap["col"] = ws.get_collection(cid)
            except Exception:  # noqa: BLE001
                pass
        return json.loads(json.dumps(snap))

    def _restore(self, snap):
        """"O'zgaruvchi qiymatlarini saqlash" o'chiq: skriptlar o'zgartirgan env/globals/collection o'zgaruvchilari run oldingi holatga qaytariladi."""
        ws = self.services.ws
        if not snap or ws is None:
            return
        with ws.lock:
            g = ws.get_globals()
            if g.get("values") != snap["globals"].get("values"):
                g["values"] = snap["globals"].get("values")
                ws.save_globals(g)
            if "env" in snap:
                e = ws.get_environment(snap["env"]["id"])
                if e.get("values") != snap["env"].get("values"):
                    e["values"] = snap["env"].get("values")
                    ws.save_environment(e)
            if "col" in snap:
                cid = (self.plan.get("scope") or "").split(":")[0]
                c = ws.get_collection(cid)
                if c.get("variable") != snap["col"].get("variable"):
                    c["variable"] = snap["col"].get("variable")
                    ws.save_collection(c)

    def _step(self, it_no, total_iter, item, row, seq, st):
        spec = dict(item["spec"])
        spec["timeout"] = st.get("timeout") or spec.get("timeout") or 30
        if st.get("ssl") is False:
            spec["ssl_verify"] = False
        res = run_item(spec, self.services, scripts=item.get("scripts"), ref=item.get("ref"), row=row,
                       info={"iteration": it_no - 1, "iterationCount": total_iter, "requestName": item["name"], "requestId": item["id"]},
                       ctx_kwargs={"retry_count": int(st.get("retry") or 0), "stop": self.stop.is_set, "keep_raw": False})
        return res

    def _record(self, it_no, seq, item, res, st, counters):
        status = res.get("status")
        ok = _is_ok(res)
        skipped = status == "SKIPPED"
        tests = _tests_of(res)
        body = _text(res.get("response"))
        ev = {"run_id": self.id, "iter": it_no, "seq": seq, "id": item["id"], "name": item["name"], "method": item["method"], "ref": item.get("ref"),
              "url": res.get("url") or "", "status": "ERR" if status == "ERROR" else status, "time": round(res.get("time") or 0, 4), "size": res.get("size") or 0,
              "error": (not ok) and not skipped, "tests": tests, "test_pass": sum(1 for t in tests if t["passed"] and not t["skipped"]), "test_fail": sum(1 for t in tests if not t["passed"]),
              "retries": res.get("retries") or 0, "scripts": res.get("scripts"), "resp_headers": res.get("resp_headers")}
        if st.get("include_response", True) or st.get("save_responses"):
            ev["response"] = body[:EVENT_BODY_LIMIT]
        with self.cond:
            counters["completed"] += 1
            counters["successful" if ok else ("skipped" if skipped else "failed")] += 1
            counters["tests_passed"] += ev["test_pass"]
            counters["tests_failed"] += ev["test_fail"]
            counters["times"].append(ev["time"])
            counters["index"] += 1
            ev["index"] = counters["index"]
            ev["total"] = counters["planned"]
            ev["successful"], ev["failed"] = counters["successful"], counters["failed"]
        stored = dict(ev, body=body if st.get("save_responses", True) else None)
        if not st.get("save_responses", True):
            stored["resp_headers"] = None
        try:
            self.store.add_result(self.id, stored)
        except Exception:  # noqa: BLE001 — saqlash xatosi run'ni to'xtatmasin
            pass
        self.emit("step", ev)
        return ok, skipped, res

    def _sleep(self, ms):
        end = time.monotonic() + ms / 1000.0
        while time.monotonic() < end and not self.stop.is_set():
            time.sleep(min(0.1, max(0.0, end - time.monotonic())))

    def _work(self):
        plan = self.plan
        st = plan.get("settings") or {}
        items = plan["items"]
        max_steps = max(1, min(100000, int(st.get("max_steps") or MAX_STEPS)))
        rows = plan.get("rows") or [{}]
        total_iter = max(1, int(plan.get("iterations") or len(rows) or 1))
        parallel = max(1, min(10, int(st.get("parallel") or 1)))
        delay = max(0, int(st.get("delay_ms") or 0))
        planned = total_iter * len(items)
        counters = {"completed": 0, "successful": 0, "failed": 0, "skipped": 0, "tests_passed": 0, "tests_failed": 0, "times": [], "index": 0, "planned": planned}
        snap = None if st.get("save_vars", True) else self._snapshot()
        status, error = "done", None
        self.emit("start", {"run_id": self.id, "number": self.number, "planned": planned, "iterations": total_iter, "items": len(items), "parallel": parallel})
        try:
            if parallel > 1:
                if any((it.get("scripts") or {}).get("prerequest") or (it.get("scripts") or {}).get("test") for it in items):
                    self.emit("note", {"message": "Parallel > 1: setNextRequest e'tiborga olinmaydi va skriptlar bir vaqtda ishlaydi"})
                jobs = [(n, it, i) for n in range(1, total_iter + 1) for i, it in enumerate(items)]
                with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
                    def one(job):
                        n, it, i = job
                        if self.stop.is_set():
                            return None
                        res = self._step(n, total_iter, it, rows[(n - 1) % len(rows)], i + 1, st)
                        return self._record(n, i + 1, it, res, st, counters)
                    futs = [pool.submit(one, j) for j in jobs]
                    for f in concurrent.futures.as_completed(futs):
                        r = f.result()
                        if r and ((st.get("stop_on_error") and not r[0] and not r[1]) or (st.get("bail") and _failed_step(r[2]))):
                            self.stop.set()
            else:
                names = {}
                for idx, it in enumerate(items):
                    names.setdefault(it["name"], idx)
                steps = 0
                done = False
                for n in range(1, total_iter + 1):
                    row = rows[(n - 1) % len(rows)]
                    i = 0
                    while i < len(items):
                        if self.stop.is_set():
                            done = True
                            break
                        steps += 1
                        if steps > max_steps:
                            error = f"setNextRequest tsikli {max_steps} qadamdan oshdi — run to'xtatildi (cheksiz tsikl himoyasi)"
                            done = True
                            break
                        it = items[i]
                        res = self._step(n, total_iter, it, row, i + 1, st)
                        ok, skipped, res = self._record(n, i + 1, it, res, st, counters)
                        if (st.get("stop_on_error") and not ok and not skipped) or (st.get("bail") and _failed_step(res)):
                            done = True
                            break
                        if delay:
                            self._sleep(delay)
                        s = res.get("scripts") or {}
                        if s.get("next_set"):
                            nxt = s.get("next_request")
                            if nxt is None:
                                done = True
                                break
                            if nxt not in names:
                                error = f"setNextRequest: «{nxt}» nomli (tanlangan) so'rov topilmadi — run to'xtatildi"
                                done = True
                                break
                            i = names[nxt]
                            continue
                        i += 1
                    if done:
                        break
        except Exception as exc:  # noqa: BLE001
            status, error = "error", str(exc)
        finally:
            try:
                self._restore(snap)
            except Exception as exc:  # noqa: BLE001
                error = (error or "") + f" [o'zgaruvchilarni tiklab bo'lmadi: {exc}]"
        times = counters["times"]
        if self.stop.is_set() and status == "done":
            status = "stopped"
        if error and status == "done":
            status = "error"
        summary = {"planned": planned, "completed": counters["completed"], "successful": counters["successful"], "failed": counters["failed"], "skipped": counters["skipped"],
                   "tests_passed": counters["tests_passed"], "tests_failed": counters["tests_failed"], "min_time": min(times) if times else 0, "max_time": max(times) if times else 0,
                   "avg_time": sum(times) / len(times) if times else 0, "stopped": status == "stopped", "error": error}
        self.status = status
        try:
            self.store.finish(self.id, status, summary)
        except Exception:  # noqa: BLE001
            pass
        self.emit("done", {"run_id": self.id, "number": self.number, "status": status, **summary, "total": planned})


class RunManager:
    def __init__(self, store, db, workspace, cookies, allowed_file_roots):
        self.store, self.db, self.workspace, self.cookies, self.roots = store, db, workspace, cookies, tuple(allowed_file_roots)
        self.runs = {}
        self.lock = threading.Lock()

    def start(self, plan):
        scope = plan.get("scope") or ""
        items = plan.get("items") or []
        if not items:
            raise ValueError("Run uchun so'rov tanlanmagan")
        rows = plan.get("rows") or [{}]
        iterations = max(1, int(plan.get("iterations") or len(rows) or 1))
        cfg = {"settings": plan.get("settings") or {}, "items": [{"id": i["id"], "name": i["name"], "method": i["method"]} for i in items], "data_rows": len(rows)}
        rid, number = self.store.create(scope, plan.get("scope_name", ""), plan.get("kind", "runner"), plan.get("env_name", ""), iterations, cfg)
        services = Services(ws=self.workspace, cookies=self.cookies, allowed_file_roots=self.roots)
        run = Run(rid, number, plan, services, self.store, self.db)
        with self.lock:
            self.runs[rid] = run
            for old in [k for k in self.runs if k < rid - 20 and self.runs[k].status != "running"]:
                self.runs.pop(old, None)
        run.start()
        return run

    def get(self, rid):
        with self.lock:
            return self.runs.get(rid)

    def active(self):
        with self.lock:
            return [r for r in self.runs.values() if r.status == "running"]
