import queue
import threading
import uuid

from .runner import run_batch


class JobManager:
    def __init__(self, allowed_file_roots=()):
        self._jobs = {}
        self._lock = threading.Lock()
        self.allowed_file_roots = tuple(allowed_file_roots)

    def start(self, config):
        job_id = str(uuid.uuid4())
        job = {"queue": queue.Queue(), "stop_event": threading.Event()}
        with self._lock:
            self._jobs[job_id] = job

        def emit(kind, data):
            job["queue"].put({"type": kind, "data": data})

        def work():
            try:
                run_batch(config, emit, job["stop_event"], self.allowed_file_roots)
            except Exception as exc:  # noqa: BLE001 — stream osilib qolmasin
                emit("done", {"total": 0, "completed": 0, "successful": 0, "failed": 0,
                              "min_time": 0, "max_time": 0, "avg_time": 0,
                              "stopped": False, "error": str(exc)})

        threading.Thread(target=work, daemon=True).start()
        return job_id

    def get(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    def discard(self, job_id):
        with self._lock:
            self._jobs.pop(job_id, None)
