"""Ishlash o'lchovlari (docs/performance.md): katta collection, 10 MB javob, 10 000 qatorli CSV runner, 50 tab, sovuq ishga tushish.

Ishlatish:  python3 tools/perf_bench.py [--out perf.json] [--only collection,bigjson,csv,tabs,cold]
Faqat tmp workspace; natija JSON (ms/MB). Ko'p o'lchov — playwright + `longtask` kuzatuvchisi (asosiy oqim bloklanishi) + CDP JS heap."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
os.environ["APIRUNNER_TESTING"] = "1"

import ui_audit as ua  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

LONGTASK_JS = """
window.__lt = []; window.__frames = [];
try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)) }).observe({ entryTypes: ['longtask'] }) } catch (e) {}
(function loop(prev) { requestAnimationFrame(t => { if (prev) window.__frames.push(t - prev); loop(t) }) })(0)
"""


def req(i, name, url, method="GET"):
    return {"id": i, "name": name, "request": {"method": method, "header": [], "url": {"raw": url}}, "response": []}


def heap_mb(page, cdp):
    cdp.send("HeapProfiler.collectGarbage")
    return round(cdp.send("Performance.getMetrics")["metrics"][[m["name"] for m in cdp.send("Performance.getMetrics")["metrics"]].index("JSHeapUsedSize")]["value"] / 1048576, 1)


def lt(page, reset=True):
    d = page.evaluate("() => ({ lt: window.__lt.slice(), fr: window.__frames.slice() })")
    if reset:
        page.evaluate("() => { window.__lt.length = 0; window.__frames.length = 0 }")
    fr = sorted(d["fr"]) or [0]
    return {"longtasks": len(d["lt"]), "longest_task_ms": max(d["lt"] or [0]), "frame_p95_ms": round(fr[int(len(fr) * 0.95) - 1], 1), "frame_max_ms": round(max(fr), 1)}


def timed(fn):
    t = time.perf_counter()
    fn()
    return round((time.perf_counter() - t) * 1000)


def new_page(browser, base):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1, locale="uz")
    ctx.add_init_script("try { localStorage.setItem('apirunner.onboarded','1') } catch (e) {}")
    ctx.add_init_script(LONGTASK_JS)
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Performance.enable")
    return page, cdp


def bench_collection(browser, base, echo, n_folders=40, per=30):
    cid = ua.api(base, "POST", "/api/collections", {"name": "Katta"})["id"]
    col = ua.api(base, "GET", f"/api/collections/{cid}")
    col["item"] = [{"id": f"f{f}", "name": f"Papka {f:02d}", "item": [req(f"r{f}_{i}", f"v1/resource-{f:02d}-{i:02d}", "{{base}}/echo?i=%d" % i, ["GET", "POST", "PUT", "DELETE"][i % 4]) for i in range(per)]} for f in range(n_folders)]
    ua.api(base, "PUT", f"/api/collections/{cid}", col)
    r = {"requests": n_folders * per}
    page, cdp = new_page(browser, base)
    t = time.perf_counter()
    page.goto(base)
    page.wait_for_selector("[data-testid=tree-row][data-name='Papka 00']")
    r["load_to_tree_ms"] = round((time.perf_counter() - t) * 1000)
    r["heap_after_load_mb"] = heap_mb(page, cdp)
    lt(page)
    root = page.locator("[data-testid=tree-row][data-name='Katta'] [data-testid=row-chevron]").first          # papkalar sukut bo'yicha ochiq: butun collection'ni yopib-ochamiz
    root.click()
    r["collapse_ms"] = timed(lambda: page.wait_for_function("document.querySelectorAll('[data-testid=tree-row]').length < 5"))
    root.click()
    r["expand_ms"] = timed(lambda: page.wait_for_function("document.querySelector('[data-testid=tree]').scrollHeight > 20000"))
    r["rows_in_dom"] = page.locator("[data-testid=tree-row]").count()
    r["tree_scroll_height_px"] = page.evaluate("document.querySelector('[data-testid=tree]').scrollHeight")
    r["after_expand"] = lt(page)
    r["heap_expanded_mb"] = heap_mb(page, cdp)
    # silliq aylantirish: 30 qadam
    lt(page)
    page.evaluate("""async () => { const b = document.querySelector('[data-testid=tree]'); for (let i = 0; i < 40; i++) { b.scrollTop += 400; await new Promise(r => requestAnimationFrame(r)) } }""")
    r["scroll"] = lt(page)
    # sidebar filtri
    lt(page)
    inp = page.locator("[data-testid=sb-search]")
    r["filter_type_ms"] = timed(lambda: (inp.click(), page.keyboard.type("resource-17-0", delay=0), page.wait_for_function("document.querySelectorAll('[data-testid=tree-row]').length < 60")))
    r["filter"] = lt(page)
    inp.fill("")
    # ⌘K qidiruv
    lt(page)
    page.keyboard.press("Control+k")
    r["cmdk_type_ms"] = timed(lambda: (page.keyboard.type("resource-31-2", delay=0), page.wait_for_selector("[data-testid=cmdk-row]")))
    r["cmdk"] = lt(page)
    page.keyboard.press("Escape")
    # DnD: bitta so'rovni boshqa papkaga sudrash (server round-trip bilan)
    page.wait_for_timeout(300)
    print(json.dumps(r, ensure_ascii=False), flush=True)
    for f in (0, 2):                                                                  # filtr/qidiruvdan keyin papkalar yopiq bo'lishi mumkin
        row = page.locator(f"[data-testid=tree-row][data-name='Papka {f:02d}']").first
        if row.get_attribute("aria-expanded") != "true":
            row.locator("[data-testid=row-chevron]").click()
    src = page.locator("[data-testid=tree-row][data-name='v1/resource-00-00']").first
    dst = page.locator("[data-testid=tree-row][data-name='v1/resource-00-03']").first       # ko'rinadigan qo'shni qator: «keyin» joyiga qo'yamiz (tartib o'zgaradi)
    src.scroll_into_view_if_needed()
    lt(page)
    def dnd():
        src.drag_to(dst, target_position={"x": 40, "y": 25})
        for _ in range(60):                                                           # server saqlashini kutamiz
            if [i["id"] for i in ua.api(base, "GET", f"/api/collections/{cid}")["item"][0]["item"]][3] == "r0_0":
                break
            page.wait_for_timeout(50)
    r["dnd_ms"] = timed(dnd)
    r["dnd"] = lt(page)
    moved = ua.api(base, "GET", f"/api/collections/{cid}")
    r["dnd_moved"] = [i["id"] for i in moved["item"][0]["item"]][3] == "r0_0"
    page.context.close()
    return r


def bench_bigjson(browser, base, echo, n=1_300_000):
    page, cdp = new_page(browser, base)
    page.goto(base)
    page.wait_for_selector("[data-testid=app]")
    ua.new_tab_req(page, echo, f"/bigjson?n={n}")
    lt(page)
    t = time.perf_counter()
    page.click("[data-testid=send]")
    page.wait_for_selector("[data-testid=resp-status]", timeout=120000)
    r = {"response_size": page.locator("[data-testid=resp-size]").inner_text(), "send_to_status_ms": round((time.perf_counter() - t) * 1000)}
    page.wait_for_selector("[data-testid=resp-body]", timeout=120000)
    r["send_to_pretty_visible_ms"] = round((time.perf_counter() - t) * 1000)
    page.wait_for_timeout(500)
    r["render"] = lt(page)
    r["heap_mb"] = heap_mb(page, cdp)
    lt(page)
    page.evaluate("""async () => { const s = document.querySelector('[data-testid=resp-body]'); if (!s) return; for (let i = 0; i < 40; i++) { s.scrollTop += 1500; await new Promise(r => requestAnimationFrame(r)) } }""")
    r["scroll"] = lt(page)
    r["truncated_or_virtual_note"] = page.locator("[data-testid=rp-virtual-note], [data-testid=resp-trunc-banner]").count() > 0
    page.context.close()
    return r


def bench_csv(browser, base, echo, rows=10000):
    cid = ua.api(base, "POST", "/api/collections", {"name": "CSV col"})["id"]
    col = ua.api(base, "GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base", "value": echo}]
    col["item"] = [req("a", "Echo", "{{base}}/echo?v={{v}}")]
    ua.api(base, "PUT", f"/api/collections/{cid}", col)
    tmp = Path(tempfile.mkdtemp()) / "d.csv"
    tmp.write_text("v\n" + "\n".join(f"row{i}" for i in range(rows)) + "\n")
    page, cdp = new_page(browser, base)
    page.goto(base)
    page.wait_for_selector("[data-testid=app]")
    page.locator("[data-name='CSV col']").click(button="right")
    page.click("[data-act=runner]")
    page.wait_for_selector("[data-testid=runner-tab]")
    r = {"rows": rows, "heap_before_mb": heap_mb(page, cdp)}
    page.locator("[data-testid=runner-file]").set_input_files(str(tmp))
    page.wait_for_selector("[data-testid=runner-data-info]")
    lt(page)
    t = time.perf_counter()
    page.click("[data-testid=runner-run]")
    page.wait_for_selector("[data-testid=runner-row]", timeout=60000)
    r["first_row_ms"] = round((time.perf_counter() - t) * 1000)
    page.evaluate("() => { window.__heap = []; setInterval(() => window.__heap.push(performance.memory.usedJSHeapSize), 250) }")
    page.wait_for_function(f"document.querySelector('[data-testid=runner-sub]')?.textContent.includes('{rows} iteratsiya') && document.querySelector('[data-testid=runner-run]') && !document.querySelector('[data-testid=runner-run]').disabled", timeout=600000)
    r["total_run_s"] = round(time.perf_counter() - t, 1)
    r["heap_peak_mb"] = round(max(page.evaluate("window.__heap") or [0]) / 1048576, 1)
    r["during_and_after"] = lt(page)
    r["rows_in_dom"] = page.locator("[data-testid=runner-row]").count()
    r["heap_after_mb"] = heap_mb(page, cdp)
    r["click_row_ms"] = timed(lambda: (page.locator("[data-testid=runner-row]").nth(5).click(), page.wait_for_selector("[data-testid=runner-body]")))
    page.context.close()
    return r


def bench_tabs(browser, base, echo, n=50):
    tabs = [{"id": f"t{i}", "kind": "request", "ref": None, "title": f"So'rov {i}", "preview": False, "dirty": False, "scroll": {"req": 0, "resp": 0},
             "response": None, "draft": {"name": f"So'rov {i}", "method": "GET", "url": echo + "/echo?i=%d" % i, "params": [{"key": "", "value": "", "enabled": True}], "headers": [{"key": "", "value": "", "enabled": True}]}} for i in range(n)]
    ua.api(base, "PUT", "/api/ui-state", {"tabs": {"v": 1, "activeId": "t0", "tabs": tabs}})
    page, cdp = new_page(browser, base)
    t = time.perf_counter()
    page.goto(base)
    page.wait_for_selector("[data-testid=tab]")
    page.wait_for_function(f"document.querySelectorAll('[data-testid=tab]').length >= {n}")
    r = {"tabs": n, "load_ms": round((time.perf_counter() - t) * 1000), "heap_mb": heap_mb(page, cdp)}
    lt(page)
    sw = []
    for i in (10, 25, 49, 0, 33):
        t = time.perf_counter()
        page.locator("[data-testid=tab]").nth(i).click()
        page.wait_for_function(f"document.querySelector('[data-testid=tab].active .title')?.textContent.includes('So\\'rov {i}')")
        sw.append(round((time.perf_counter() - t) * 1000))
    r["switch_ms"] = sw
    r["switching"] = lt(page)
    page.context.close()
    return r


def bench_cold(tmp):
    code = ("import time,sys;t=time.perf_counter();from apirunner.app import create_app;t1=time.perf_counter();"
            "app=create_app(workspace_dir=sys.argv[1]+'/w',saved_file=sys.argv[1]+'/s.json',upload_dir=sys.argv[1]+'/u',session_token='x',backup_dir=sys.argv[1]+'/b');t2=time.perf_counter();"
            "c=app.test_client();c.get('/');t3=time.perf_counter();print(round((t1-t)*1000),round((t2-t1)*1000),round((t3-t2)*1000))")
    out = []
    for _ in range(3):
        d = tempfile.mkdtemp(dir=tmp)
        t = time.perf_counter()
        p = subprocess.run([sys.executable, "-c", code, d], capture_output=True, text=True, cwd=str(ROOT), env={**os.environ, "APIRUNNER_TESTING": "1"})
        total = round((time.perf_counter() - t) * 1000)
        a, b, c = (int(x) for x in p.stdout.split())
        out.append({"import_ms": a, "create_app_ms": b, "first_request_ms": c, "process_total_ms": total})
    return {"runs": out, "median_total_ms": sorted(o["process_total_ms"] for o in out)[1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="perf.json")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = set(filter(None, a.only.split(",")))
    res = {}
    with tempfile.TemporaryDirectory() as tmpd, sync_playwright() as pw:
        tmp = Path(tmpd)
        base, echo, app = ua.start_servers(tmp)
        browser = pw.chromium.launch()
        for name, fn in (("collection", bench_collection), ("bigjson", bench_bigjson), ("csv", bench_csv), ("tabs", bench_tabs)):
            if only and name not in only:
                continue
            print("→", name, flush=True)
            res[name] = fn(browser, base, echo)
            print(json.dumps(res[name], ensure_ascii=False), flush=True)
        browser.close()
        if not only or "cold" in only:
            res["cold"] = bench_cold(tmp)
            print(json.dumps(res["cold"]))
    Path(a.out).write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
