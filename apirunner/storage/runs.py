"""Run natijalari (SQLite): `runs` (sarlavha + yakun) va `run_results` (har so'rov natijasi), oxirgi natijalar (`last_results`)."""
import json
import time

from .db import RUN_BODY_LIMIT, RUN_KEEP, connect


class RunStore:
    def __init__(self, db):
        self.db = db            # StateDB (path va lock)

    def _c(self):
        return connect(self.db.path)

    def create(self, scope, scope_name, kind, env_name, iterations, config):
        with self.db._lock:
            c = self._c()
            try:
                with c:
                    n = c.execute("SELECT COALESCE(MAX(number),0)+1 FROM runs WHERE scope=?", (scope,)).fetchone()[0]
                    cur = c.execute("INSERT INTO runs(scope, scope_name, number, kind, started, env_name, iterations, config) VALUES (?,?,?,?,?,?,?,?)",
                                    (scope, scope_name, n, kind, time.time(), env_name, iterations, json.dumps(config, ensure_ascii=False)))
                    rid = cur.lastrowid
                    ids = [r[0] for r in c.execute("SELECT id FROM runs ORDER BY id DESC LIMIT -1 OFFSET ?", (RUN_KEEP,))]
                    for old in ids:
                        c.execute("DELETE FROM run_results WHERE run_id=?", (old,))
                        c.execute("DELETE FROM runs WHERE id=?", (old,))
                    return rid, n
            finally:
                c.close()

    def add_result(self, run_id, r):
        body = r.get("body")
        trunc = 0
        if isinstance(body, str) and len(body) > RUN_BODY_LIMIT:
            body, trunc = body[:RUN_BODY_LIMIT], 1
        with self.db._lock:
            c = self._c()
            try:
                with c:
                    c.execute("INSERT INTO run_results(run_id, iter, seq, item_id, name, method, url, status, time, size, error, tests, resp_headers, body, body_truncated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (run_id, r["iter"], r["seq"], r.get("id", ""), r.get("name", ""), r.get("method", ""), r.get("url", ""), str(r.get("status")), r.get("time") or 0, r.get("size") or 0,
                               1 if r.get("error") else 0, json.dumps(r.get("tests") or [], ensure_ascii=False), json.dumps(r["resp_headers"], ensure_ascii=False) if r.get("resp_headers") is not None else None, body, trunc))
                    if r.get("ref") and r.get("status") not in (None, "SKIPPED"):
                        c.execute("INSERT OR REPLACE INTO last_results(ref, status, time, ts) VALUES (?,?,?,?)", (r["ref"], str(r["status"]), r.get("time") or 0, time.time()))
            finally:
                c.close()

    def finish(self, run_id, status, summary):
        with self.db._lock:
            c = self._c()
            try:
                with c:
                    c.execute("UPDATE runs SET finished=?, status=?, summary=? WHERE id=?", (time.time(), status, json.dumps(summary, ensure_ascii=False), run_id))
            finally:
                c.close()

    @staticmethod
    def _run(r):
        return {"id": r["id"], "scope": r["scope"], "scope_name": r["scope_name"], "number": r["number"], "kind": r["kind"], "started": r["started"], "finished": r["finished"],
                "status": r["status"], "env_name": r["env_name"], "iterations": r["iterations"], "summary": json.loads(r["summary"] or "{}")}

    def list(self, scope=None, limit=50):
        q, a = "SELECT * FROM runs", []
        if scope:
            q += " WHERE scope=?"
            a.append(scope)
        q += " ORDER BY id DESC LIMIT ?"
        a.append(limit)
        with self.db._lock:
            c = self._c()
            try:
                return [self._run(r) for r in c.execute(q, a)]
            finally:
                c.close()

    def get(self, run_id, with_body=False):
        with self.db._lock:
            c = self._c()
            try:
                r = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
                if not r:
                    return None
                run = self._run(r)
                run["config"] = json.loads(r["config"] or "{}")
                cols = "id, iter, seq, item_id, name, method, url, status, time, size, error, tests, body_truncated" + (", resp_headers, body" if with_body else "")
                run["results"] = [{**{k: row[k] for k in row.keys()}, "tests": json.loads(row["tests"] or "[]"), "error": bool(row["error"])}
                                  for row in c.execute(f"SELECT {cols} FROM run_results WHERE run_id=? ORDER BY id", (run_id,))]
                if with_body:
                    for x in run["results"]:
                        x["resp_headers"] = json.loads(x["resp_headers"]) if x["resp_headers"] else None
                return run
            finally:
                c.close()

    def result(self, result_id):
        with self.db._lock:
            c = self._c()
            try:
                row = c.execute("SELECT * FROM run_results WHERE id=?", (result_id,)).fetchone()
                if not row:
                    return None
                d = {k: row[k] for k in row.keys()}
                d["tests"] = json.loads(d["tests"] or "[]")
                d["resp_headers"] = json.loads(d["resp_headers"]) if d["resp_headers"] else None
                d["error"] = bool(d["error"])
                return d
            finally:
                c.close()

    def delete(self, run_id):
        with self.db._lock:
            c = self._c()
            try:
                with c:
                    c.execute("DELETE FROM run_results WHERE run_id=?", (run_id,))
                    return c.execute("DELETE FROM runs WHERE id=?", (run_id,)).rowcount > 0
            finally:
                c.close()

    def last_results(self, refs):
        """{ref: {status, time, ts}} — berilgan `cid:itemId` havolalari uchun oxirgi natija."""
        if not refs:
            return {}
        with self.db._lock:
            c = self._c()
            try:
                out = {}
                for i in range(0, len(refs), 500):
                    chunk = refs[i:i + 500]
                    for r in c.execute(f"SELECT ref, status, time, ts FROM last_results WHERE ref IN ({','.join('?' * len(chunk))})", chunk):
                        out[r["ref"]] = {"status": r["status"], "time": r["time"], "ts": r["ts"]}
                return out
            finally:
                c.close()

    def record_last(self, ref, status, t):
        with self.db._lock:
            c = self._c()
            try:
                with c:
                    c.execute("INSERT OR REPLACE INTO last_results(ref, status, time, ts) VALUES (?,?,?,?)", (ref, str(status), t or 0, time.time()))
            finally:
                c.close()
