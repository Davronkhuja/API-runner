"""Run API (/api/runs): boshlash, SSE oqimi, to'xtatish, tarix, eksport (JSON/HTML/JUnit), solishtirish, oxirgi natijalar."""
import html
import json
import time
import xml.etree.ElementTree as ET

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from ..storage import files

bp = Blueprint("runs_api", __name__, url_prefix="/api")


def _store():
    return current_app.extensions["runs"]


def _mgr():
    return current_app.extensions["run_manager"]


@bp.post("/runs")
def start_run():
    plan = request.get_json(silent=True) or {}
    plan["items"] = [dict(i, spec=files.resolve_spec(i.get("spec") or {}, current_app.extensions["workspace"].root)) for i in plan.get("items") or []]
    try:
        run = _mgr().start(plan)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"id": run.id, "number": run.number})


@bp.get("/runs/<int:rid>/stream")
def stream_run(rid):
    run = _mgr().get(rid)
    if not run:
        return jsonify({"error": "Run oqimi topilmadi (server qayta ishga tushgan bo'lishi mumkin) — natijalar tarixda"}), 404
    start = request.args.get("from", 0, type=int)

    def gen():
        for kind, data in run.stream(start):
            if kind == "ping":
                yield ": ping\n\n"
            else:
                yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    return Response(stream_with_context(gen()), content_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@bp.post("/runs/<int:rid>/stop")
def stop_run(rid):
    run = _mgr().get(rid)
    if not run:
        return jsonify({"error": "Run topilmadi"}), 404
    run.stop.set()
    return jsonify({"ok": True})


@bp.get("/runs")
def list_runs():
    return jsonify(_store().list(request.args.get("scope") or None, request.args.get("limit", 50, type=int)))


@bp.get("/runs/<int:rid>")
def get_run(rid):
    r = _store().get(rid)
    return (jsonify(r), 200) if r else (jsonify({"error": "Run topilmadi"}), 404)


@bp.get("/runs/results/<int:result_id>")
def get_result(result_id):
    r = _store().result(result_id)
    return (jsonify(r), 200) if r else (jsonify({"error": "Natija topilmadi"}), 404)


@bp.delete("/runs/<int:rid>")
def delete_run(rid):
    return jsonify({"ok": _store().delete(rid)})


@bp.get("/last-results")
def last_results():
    """`?refs=cid:id,cid:id2` -> {ref: {status,time,ts}}; `?scope=ref` -> oxirgi run (har so'rov uchun birinchi iteratsiya natijasi)."""
    refs = [r for r in (request.args.get("refs") or "").split(",") if r]
    out = {"results": _store().last_results(refs)}
    scope = request.args.get("scope")
    if scope:
        runs = _store().list(scope, 1)
        if runs:
            full = _store().get(runs[0]["id"])
            first = min((x["iter"] for x in full["results"]), default=1)
            out["run"] = {**runs[0], "items": [{"id": x["item_id"], "name": x["name"], "status": x["status"], "error": x["error"], "time": x["time"]} for x in full["results"] if x["iter"] == first]}
    return jsonify(out)


# ── solishtirish ──
@bp.get("/runs/<int:a>/compare/<int:b>")
def compare(a, b):
    ra, rb = _store().get(a), _store().get(b)
    if not ra or not rb:
        return jsonify({"error": "Run topilmadi"}), 404
    key = lambda x: (x["iter"], x["item_id"] or x["name"])  # noqa: E731
    ma, mb = {key(x): x for x in ra["results"]}, {key(x): x for x in rb["results"]}
    rows = []
    for k in list(dict.fromkeys([key(x) for x in ra["results"]] + [key(x) for x in rb["results"]])):
        x, y = ma.get(k), mb.get(k)
        rows.append({"iter": k[0], "name": (x or y)["name"], "method": (x or y)["method"], "a": x and {"status": x["status"], "time": x["time"], "tests_failed": sum(1 for t in x["tests"] if not t["passed"])},
                     "b": y and {"status": y["status"], "time": y["time"], "tests_failed": sum(1 for t in y["tests"] if not t["passed"])},
                     "changed": (x or {}).get("status") != (y or {}).get("status"), "delta": ((y["time"] - x["time"]) if x and y else None)})
    return jsonify({"a": {k: ra[k] for k in ("id", "number", "scope_name", "started", "summary")}, "b": {k: rb[k] for k in ("id", "number", "scope_name", "started", "summary")},
                    "rows": rows, "changed": sum(1 for r in rows if r["changed"])})


# ── eksport ──
def _junit(run):
    suites = ET.Element("testsuites", name=f"{run['scope_name']} — run #{run['number']}")
    by_iter = {}
    for x in run["results"]:
        by_iter.setdefault(x["iter"], []).append(x)
    for it, rs in sorted(by_iter.items()):
        tests = sum(1 + len(x["tests"]) for x in rs)
        fails = sum((1 if x["error"] else 0) + sum(1 for t in x["tests"] if not t["passed"]) for x in rs)
        ts = ET.SubElement(suites, "testsuite", name=f"iteratsiya {it}", tests=str(tests), failures=str(fails), time=f"{sum(x['time'] for x in rs):.3f}")
        for x in rs:
            tc = ET.SubElement(ts, "testcase", classname=run["scope_name"] or "run", name=f"{x['method']} {x['name']}", time=f"{x['time']:.3f}")
            if x["error"]:
                ET.SubElement(tc, "failure", message=f"HTTP {x['status']}").text = x["url"]
            for t in x["tests"]:
                c = ET.SubElement(ts, "testcase", classname=x["name"], name=t["name"], time="0")
                if t.get("skipped"):
                    ET.SubElement(c, "skipped")
                elif not t["passed"]:
                    ET.SubElement(c, "failure", message=t.get("error") or "test yiqildi")
    return ET.tostring(suites, encoding="unicode", xml_declaration=True)


def _html(run):
    s = run["summary"]
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(run["started"]))
    rows = "".join(
        f"<tr class='{'bad' if x['error'] else ''}'><td>{x['iter']}</td><td>{html.escape(x['method'])}</td><td>{html.escape(x['name'])}</td><td>{html.escape(str(x['status']))}</td><td>{x['time'] * 1000:.0f} ms</td>"
        f"<td>{sum(1 for t in x['tests'] if t['passed'] and not t.get('skipped'))}/{len(x['tests'])}</td></tr>" for x in run["results"])
    return (f"<!doctype html><html lang='uz'><meta charset='utf-8'><title>Run #{run['number']}</title><style>body{{font:14px system-ui;margin:24px;color:#151821}}table{{border-collapse:collapse;width:100%}}"
            "th,td{border-bottom:1px solid #e2e5ea;padding:6px 10px;text-align:left}tr.bad td{background:#fdecec}.k{display:inline-block;margin-right:18px}</style>"
            f"<h1>{html.escape(run['scope_name'])} — run #{run['number']}</h1><p>{when} · {html.escape(run['env_name'])} · {run['iterations']} iteratsiya</p>"
            f"<p><span class='k'>Bajarildi: <b>{s.get('completed', 0)}</b></span><span class='k'>Muvaffaqiyatli: <b>{s.get('successful', 0)}</b></span><span class='k'>Xato: <b>{s.get('failed', 0)}</b></span>"
            f"<span class='k'>Testlar: <b>{s.get('tests_passed', 0)}</b> o'tdi / <b>{s.get('tests_failed', 0)}</b> yiqildi</span><span class='k'>O'rtacha: <b>{s.get('avg_time', 0) * 1000:.0f} ms</b></span></p>"
            f"<table><thead><tr><th>Iter.</th><th>Metod</th><th>So'rov</th><th>Status</th><th>Vaqt</th><th>Testlar</th></tr></thead><tbody>{rows}</tbody></table></html>")


@bp.get("/runs/<int:rid>/export")
def export_run(rid):
    fmt = (request.args.get("format") or "json").lower()
    run = _store().get(rid, with_body=(fmt == "json"))
    if not run:
        return jsonify({"error": "Run topilmadi"}), 404
    name = f"run-{run['number']}"
    if fmt == "junit":
        return Response(_junit(run), content_type="application/xml", headers={"Content-Disposition": f'attachment; filename="{name}.junit.xml"'})
    if fmt == "html":
        return Response(_html(run), content_type="text/html; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}.html"'})
    return Response(json.dumps(run, ensure_ascii=False, indent=2), content_type="application/json", headers={"Content-Disposition": f'attachment; filename="{name}.json"'})
