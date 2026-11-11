"""`apirunner` buyruq qatori: `serve` (UI, sukut), `run` (newman analogi), `mock`, `docs`.

    apirunner run collection.json -e env.json -d data.csv -n 3 --reporters cli,json,junit,html --bail
Chiqish kodi: 0 — hammasi yaxshi; 1 — so'rov xatosi yoki test yiqildi; 2 — noto'g'ri foydalanish/kirish fayli.
"""
import argparse
import csv
import json
import os
import sys
import tempfile
import time

from . import __version__

EXIT_FAIL, EXIT_USAGE = 1, 2


class CliError(Exception):
    pass


# ── kirish fayllari ──
def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise CliError(f"Faylni o'qib bo'lmadi: {path} ({e.strerror})") from e


def _workspace_dir(args):
    return getattr(args, "workspace", None) or os.environ.get("APIRUNNER_WORKSPACE") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace")


def load_collection(args):
    """Fayl (har qanday import formati) yoki ish joyidagi collection nomi/id'si -> (collection, base_dir)."""
    from .importers.common import ImportErr
    from .importers.registry import parse_source
    src = args.source
    if os.path.isfile(src):
        try:
            parsed = parse_source(_read(src), os.path.basename(src))
        except ImportErr as e:
            raise CliError(str(e)) from e
        cols = parsed["collections"]
        if not cols:
            raise CliError(f"{src}: collection topilmadi (format: {parsed['label']})")
        if getattr(args, "collection", None):
            cols = [c for c in cols if c["info"]["name"] == args.collection] or cols
        return cols[0], os.path.dirname(os.path.abspath(src)), parsed["warnings"]
    from .storage.workspace import Workspace
    wdir = _workspace_dir(args)
    if not os.path.isdir(wdir):
        raise CliError(f"Fayl ham, workspace ham topilmadi: {src}")
    ws = Workspace(wdir)
    for c in ws.list_collections():
        if src.lower() in (c["name"].lower(), c["id"].lower()):
            return ws.get_collection(c["id"]), os.getcwd(), []
    raise CliError(f"Collection topilmadi: {src} (workspace: {wdir})")


def load_env(spec, args):
    from .importers.common import ImportErr
    from .importers.registry import parse_source
    if os.path.isfile(spec):
        try:
            p = parse_source(_read(spec), os.path.basename(spec))
        except ImportErr as e:
            raise CliError(str(e)) from e
        if not p["environments"]:
            raise CliError(f"{spec}: environment emas")
        return p["environments"][0]
    from .storage.workspace import Workspace
    wdir = _workspace_dir(args)
    if os.path.isdir(wdir):
        ws = Workspace(wdir)
        for e in ws.list_environments():
            if spec.lower() in ((e.get("name") or "").lower(), e["id"].lower()):
                return e
    raise CliError(f"Environment topilmadi: {spec}")


def load_rows(path):
    text = _read(path)
    try:
        if path.lower().endswith(".json"):
            rows = json.loads(text)
            if not isinstance(rows, list):
                raise CliError("Data JSON massiv bo'lishi kerak")
            return [{k: ("" if v is None else v) for k, v in r.items()} for r in rows if isinstance(r, dict)]
        return [dict(r) for r in csv.DictReader(text.splitlines())]
    except (ValueError, csv.Error) as e:
        raise CliError(f"Data faylni o'qib bo'lmadi: {e}") from e


# ── hisobotlar ──
class Colors:
    def __init__(self, on):
        self.on = on

    def __call__(self, code, s):
        return f"\033[{code}m{s}\033[0m" if self.on else s
    ok = lambda self, s: self("32", s)      # noqa: E731
    bad = lambda self, s: self("31", s)     # noqa: E731
    dim = lambda self, s: self("2", s)      # noqa: E731
    bold = lambda self, s: self("1", s)     # noqa: E731


def is_failure(step, strict):
    if step.get("status") == "SKIPPED":
        return False
    if step.get("status") == "ERR" or step.get("test_fail"):
        return True
    return bool(strict and str(step.get("status")).isdigit() and int(step["status"]) >= 400)


def print_step(out, c, s, verbose, strict):
    bad = is_failure(s, strict)
    mark = c.bad("✗") if bad else c.ok("✓")
    st = s["status"]
    ms = "%.0f ms" % (s["time"] * 1000)
    line = f"{mark} {c.bold(s['method'].ljust(6))} {s['name']}  {c.bad(str(st)) if bad else str(st)}  {c.dim(ms)}"
    if s.get("iter", 1) > 1 or verbose:
        line += c.dim(f"  [#{s['iter']}]")
    out.write(line + "\n")
    if verbose and s.get("url"):
        out.write(c.dim(f"    {s['url']}") + "\n")
    for t in s.get("tests") or []:
        if t.get("skipped"):
            out.write(c.dim(f"    ○ {t['name']} (o'tkazib yuborildi)") + "\n")
        elif t["passed"]:
            out.write(f"    {c.ok('✓')} {t['name']}\n")
        else:
            out.write(f"    {c.bad('✗')} {t['name']}" + (f" — {t['error']}" if t.get("error") else "") + "\n")
    if s.get("error") and st == "ERR":
        out.write(c.bad(f"    {(s.get('response') or '')[:200]}") + "\n")


def summarize(run, strict):
    res = run["results"]
    fails = [r for r in res if is_failure({**r, "test_fail": sum(1 for t in r["tests"] if not t["passed"])}, strict)]
    tests = [t for r in res for t in r["tests"]]
    return {"iterations": run["iterations"], "requests": len(res), "failed_requests": len([r for r in res if r["status"] == "ERR" or (strict and str(r["status"]).isdigit() and int(r["status"]) >= 400)]),
            "assertions": len([t for t in tests if not t.get("skipped")]), "failed_assertions": len([t for t in tests if not t["passed"]]), "skipped_assertions": len([t for t in tests if t.get("skipped")]),
            "failures": len(fails), "total_time": round(sum(r["time"] for r in res), 3), "avg_time": round(sum(r["time"] for r in res) / len(res), 3) if res else 0}


def print_summary(out, c, sm, run, strict):
    rows = [("iteratsiyalar", sm["iterations"], 0), ("so'rovlar", sm["requests"], sm["failed_requests"]), ("test-assertlar", sm["assertions"], sm["failed_assertions"])]
    out.write("\n┌─────────────────────┬──────────┬──────────┐\n│                     │ bajarildi│   xato   │\n├─────────────────────┼──────────┼──────────┤\n")
    for name, n, f in rows:
        out.write(f"│ {name.ljust(19)} │ {str(n).rjust(8)} │ {(c.bad if f else c.ok)(str(f).rjust(8))} │\n")
    out.write("└─────────────────────┴──────────┴──────────┘\n")
    out.write(f"umumiy vaqt: {sm['total_time']:.2f} s · o'rtacha: {sm['avg_time'] * 1000:.0f} ms" + (f" · o'tkazib yuborilgan assertlar: {sm['skipped_assertions']}" if sm["skipped_assertions"] else "") + "\n")
    bads = [r for r in run["results"] if is_failure({**r, "test_fail": sum(1 for t in r["tests"] if not t["passed"])}, strict)]
    if bads:
        out.write(c.bad(f"\nXatolar ({len(bads)}):") + "\n")
        for i, r in enumerate(bads, 1):
            why = [f"test: {t['name']}" + (f" — {t['error']}" if t.get("error") else "") for t in r["tests"] if not t["passed"]] or [f"HTTP {r['status']}" if r["status"] != "ERR" else (r.get("error") and "so'rov xatosi")]
            out.write(f" {i}. [#{r['iter']}] {r['method']} {r['name']}\n      " + "\n      ".join(str(w) for w in why) + "\n")


def write_reports(args, run, sm, col, env_name):
    from .core import reporters
    wanted = [x.strip() for x in (args.reporters or "cli").split(",") if x.strip()]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in col["info"]["name"]).strip("_") or "run"
    written = []
    for kind in wanted:
        if kind == "cli":
            continue
        if kind not in ("json", "junit", "html"):
            raise CliError(f"Noma'lum reporter: {kind} (cli, json, junit, html)")
        ext = {"json": "json", "junit": "xml", "html": "html"}[kind]
        path = getattr(args, f"reporter_{kind}_export", None) or os.path.join(args.export_dir, f"{safe}-{stamp}.{ext}")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if kind == "json":
            body = json.dumps({"collection": col["info"]["name"], "environment": env_name, "run": {k: run[k] for k in ("number", "started", "finished", "status", "iterations")}, "summary": sm, "results": run["results"], "failures": sm["failures"]}, indent=2, ensure_ascii=False)
        elif kind == "junit":
            body = reporters.junit(run)
        else:
            body = reporters.html_report(run)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        written.append(path)
    return written


# ── run ──
def cmd_run(args):
    from .core.planner import build_plan
    from .core.run_engine import RunManager
    from .storage.cookies import CookieStore
    from .storage.db import StateDB
    from .storage.runs import RunStore
    from .storage.workspace import Workspace
    out = sys.stdout
    c = Colors(out.isatty() and not args.no_color and not os.environ.get("NO_COLOR"))
    col, base_dir, import_warn = load_collection(args)
    rows = load_rows(args.data) if args.data else []
    if args.iterations is not None and args.iterations < 1:
        raise CliError("-n kamida 1 bo'lsin")
    env = load_env(args.env, args) if args.env else None
    if env and args.env_var:
        for kv in args.env_var:
            k, sep, v = kv.partition("=")
            if not sep:
                raise CliError(f"--env-var K=V ko'rinishida bo'lsin: {kv}")
            for row in env["values"]:
                if row["key"] == k:
                    row["value"], row["current"] = v, None
                    break
            else:
                env["values"].append({"key": k, "value": v, "enabled": True, "type": "default"})
    with tempfile.TemporaryDirectory(prefix="apirunner-cli-") as tmp:
        ws = Workspace(os.path.join(tmp, "ws"))
        db = StateDB(os.path.join(ws.root, "state.db"))
        mgr = RunManager(RunStore(db), db, ws, CookieStore(os.path.join(ws.root, "state.db")), (os.getcwd(), base_dir, ws.root))
        ws.save_collection(col)
        env_name = ""
        if env:
            ws.save_environment(env)
            ws.update_meta(active_environment_id=env["id"])
            env_name = env.get("name", "")
        if args.globals:
            from .importers.registry import parse_source
            g = parse_source(_read(args.globals), os.path.basename(args.globals))
            if g["globals"] is None:
                raise CliError(f"{args.globals}: globals emas")
            ws.save_globals({**ws.get_globals(), "values": g["globals"]})
        settings = {"delay_ms": args.delay, "parallel": 1, "retry": args.retry, "timeout": args.timeout_request / 1000.0 if args.timeout_request else 30, "ssl": not args.insecure,
                    "stop_on_error": False, "bail": args.bail, "save_vars": True, "save_responses": False, "include_response": False}
        try:
            plan, warns = build_plan(col, args.folder, env_name, base_dir, settings, rows, args.iterations, settings["timeout"], args.insecure)
        except ValueError as e:
            raise CliError(str(e)) from e
        if not args.silent and "cli" in (args.reporters or "cli"):
            out.write(c.bold(f"apirunner v{__version__}") + f" — {plan['scope_name']}" + (f" · env: {env_name}" if env_name else "") + f" · {plan['iterations']} iteratsiya · {len(plan['items'])} so'rov\n\n")
            for w in import_warn + warns:
                out.write(c.dim(f"⚠ {w}") + "\n")
        run = mgr.start(plan)
        show = not args.silent and "cli" in (args.reporters or "cli")
        for kind, data in run.stream(0):
            if kind == "step":
                if show:
                    print_step(out, c, data, args.verbose, args.fail_on_http_errors)
                if args.bail and args.fail_on_http_errors and is_failure(data, True) and not data.get("test_fail") and data.get("status") != "ERR":
                    run.stop.set()                                                              # --bail + --fail-on-http-errors: HTTP xatosida ham
            elif kind == "note" and show:
                out.write(c.dim(f"ℹ {data.get('message', '')}") + "\n")
            elif kind == "done" and data.get("error") and show:
                out.write(c.bad(f"\n✗ {data['error']}") + "\n")
        run.thread.join(timeout=5)
        full = mgr.store.get(run.id)
        sm = summarize(full, args.fail_on_http_errors)
        if show:
            print_summary(out, c, sm, full, args.fail_on_http_errors)
        paths = write_reports(args, full, sm, col, env_name)
        if paths and not args.silent:
            out.write("\n" + "\n".join(f"hisobot: {p}" for p in paths) + "\n")
        if args.export_environment and env:
            env_now = ws.get_environment(env["id"])
            with open(args.export_environment, "w", encoding="utf-8") as f:
                from .exporters.postman import export_environment
                json.dump(export_environment({**env_now, "values": [{**v, "value": v.get("current") if v.get("current") is not None else v.get("value", "")} for v in env_now["values"]]}), f, indent=2, ensure_ascii=False)
        error = (full.get("summary") or {}).get("error")
    return EXIT_FAIL if (sm["failures"] or error) else 0


# ── mock / docs / serve ──
def warn_if_exposed(host):
    """Loopback'dan boshqa manzil — ilova tarmoqqa ochiladi (sukut 127.0.0.1). Xavfsizlik ko'rigi: foydalanuvchi bilishi shart."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"⚠ Diqqat: {host} manzili tarmoqdagi boshqa qurilmalarga ochiq. Mock javoblari/UI shu tarmoqdagi hammaga ko'rinadi.", file=sys.stderr)


def cmd_mock(args):
    from .mock import run_cli
    warn_if_exposed(args.host)
    return run_cli(args)


def cmd_docs(args):
    from .docs_gen import run_cli
    return run_cli(args)


def cmd_serve(args):
    from .app import main as serve
    warn_if_exposed(args.host)
    serve(host=args.host, port=args.port, open_browser_tab=not args.no_browser)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="apirunner", description="API Runner: lokal Postman-ga o'xshash klient (UI), newman analogi (`run`), mock server va hujjat generatori.")
    p.add_argument("--version", action="version", version=f"apirunner {__version__}")
    sub = p.add_subparsers(dest="cmd")
    s = sub.add_parser("serve", help="UI serverini ishga tushirish (sukut)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=None)
    s.add_argument("--no-browser", action="store_true")
    s.set_defaults(fn=cmd_serve)
    r = sub.add_parser("run", help="collection/papkani bajarish (newman analogi)", description="Collection faylini (Postman/OpenAPI/Insomnia/HAR/cURL) yoki ish joyidagi collection nomini bajaradi.")
    r.add_argument("source", help="collection fayli yoki ish joyidagi collection nomi/id")
    r.add_argument("--folder", help="faqat shu papka (nom yoki id)")
    r.add_argument("--collection", help="fayl bir nechta collection bersa (Insomnia) — nomi")
    r.add_argument("-e", "--env", help="environment fayli yoki ish joyidagi muhit nomi")
    r.add_argument("-g", "--globals", help="globals fayli (Postman)")
    r.add_argument("--env-var", action="append", metavar="K=V", help="o'zgaruvchini bekor qilish (takrorlanadi)")
    r.add_argument("-d", "--data", help="CSV/JSON ma'lumot fayli (har qator — iteratsiya)")
    r.add_argument("-n", "--iterations", type=int, help="iteratsiyalar soni (sukut: data qatorlari yoki 1)")
    r.add_argument("--workspace", help="ish joyi papkasi (nom bo'yicha qidirish uchun)")
    r.add_argument("--reporters", default="cli", help="vergul bilan: cli,json,junit,html (sukut: cli)")
    r.add_argument("--export-dir", default="apirunner-reports", help="hisobotlar papkasi")
    for k in ("json", "junit", "html"):
        r.add_argument(f"--reporter-{k}-export", metavar="FAYL", help=f"{k} hisobot yo'li")
    r.add_argument("--export-environment", metavar="FAYL", help="tugagach yangilangan muhitni yozish")
    r.add_argument("--bail", action="store_true", help="birinchi xatoda to'xtash")
    r.add_argument("--delay", type=int, default=0, metavar="MS", help="so'rovlar orasida kechikish")
    r.add_argument("--timeout-request", type=int, metavar="MS", help="bitta so'rov uchun vaqt chegarasi")
    r.add_argument("--retry", type=int, default=0)
    r.add_argument("--insecure", action="store_true", help="SSL sertifikatini tekshirmaslik")
    r.add_argument("--fail-on-http-errors", action="store_true", help="HTTP 4xx/5xx ham xato hisoblansin (exit code 1)")
    r.add_argument("--no-color", action="store_true")
    r.add_argument("--silent", action="store_true")
    r.add_argument("--verbose", action="store_true")
    r.set_defaults(fn=cmd_run)
    m = sub.add_parser("mock", help="collection example'lari asosida mock server")
    m.add_argument("source", help="collection fayli yoki ish joyidagi collection nomi")
    m.add_argument("--port", type=int, default=3000)
    m.add_argument("--host", default="127.0.0.1")
    m.add_argument("--delay", type=int, default=0, metavar="MS", help="barcha javoblarga qo'shimcha kechikish")
    m.add_argument("--workspace")
    m.add_argument("--collection")
    m.set_defaults(fn=cmd_mock)
    d = sub.add_parser("docs", help="collection/papkadan statik HTML hujjat")
    d.add_argument("source")
    d.add_argument("--folder")
    d.add_argument("-o", "--output", default="docs.html")
    d.add_argument("--workspace")
    d.add_argument("--collection")
    d.set_defaults(fn=cmd_docs)
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version"):
        argv = ["serve"] + argv                                    # `apirunner` / `apirunner --port 5051` — eski xatti-harakat
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args) or 0
    except CliError as e:
        sys.stderr.write(f"xato: {e}\n")
        return EXIT_USAGE
    except KeyboardInterrupt:
        return 130


def entry():
    sys.exit(main())


if __name__ == "__main__":
    entry()
