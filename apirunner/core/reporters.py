"""Run natijalari uchun hisobotlar (JUnit XML, HTML): UI eksporti va CLI uchun umumiy."""
import html
import time
import xml.etree.ElementTree as ET


def junit(run):
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


def html_report(run):
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
