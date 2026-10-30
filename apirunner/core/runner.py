"""Batch runner: bitta so'rov shabloni × data qatorlari, concurrency / retry / delay / stop."""
import concurrent.futures
import threading
import time

from .engine import ExecContext, execute


def run_batch(config, emit, stop_event, allowed_file_roots=(), allowed_files=frozenset()):
    """`config` — /run tanasi. `emit(type, data)` — "result" va yakunda "done" hodisalari."""
    rows = config.get("rows") or [{}]
    delay = float(config.get("delay", 0) or 0)
    concurrency = max(1, min(10, int(config.get("concurrency", 1) or 1)))
    retry_count = max(0, min(5, int(config.get("retry_count", 0) or 0)))
    env_vars = config.get("env_vars") or {}
    rows = [{**env_vars, **row} for row in rows]
    total = len(rows)

    lock = threading.Lock()
    counts = {"successful": 0, "failed": 0, "completed": 0}
    times = []

    def one(row, index):
        if stop_event.is_set():
            return None
        ctx = ExecContext(variables=row, retry_count=retry_count, stop=stop_event.is_set,
                          allowed_file_roots=allowed_file_roots, allowed_files=allowed_files)
        res = execute(config, ctx)
        with lock:
            counts["failed" if res["error"] else "successful"] += 1
            counts["completed"] += 1
            res.update(index=index, total=total,
                       successful=counts["successful"], failed=counts["failed"])
            times.append(res["time"])
        return res

    if concurrency > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(one, row, i) for i, row in enumerate(rows, start=1)]
            for fut in concurrent.futures.as_completed(futures):
                res = fut.result()
                if res is not None:
                    emit("result", res)
    else:
        for i, row in enumerate(rows, start=1):
            if stop_event.is_set():
                break
            res = one(row, i)
            if res is None:
                break
            emit("result", res)
            if i < total and delay > 0:
                end = time.monotonic() + delay
                while time.monotonic() < end and not stop_event.is_set():
                    time.sleep(min(0.1, max(0.0, end - time.monotonic())))

    emit("done", {
        "total": total, "completed": counts["completed"],
        "successful": counts["successful"], "failed": counts["failed"],
        "min_time": min(times) if times else 0,
        "max_time": max(times) if times else 0,
        "avg_time": sum(times) / len(times) if times else 0,
        "stopped": stop_event.is_set(),
    })
