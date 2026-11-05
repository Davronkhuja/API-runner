"""Bosqich 4: Collection Runner v2 — run #N, Testlar ustuni, tarix, solishtirish, eksport, SQLite'dagi oxirgi natijalar, yagona Run sozlamalari."""
import re

import pytest
from playwright.sync_api import expect

from apirunner.core import scripting

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


def req(i, name, url, method="GET", events=()):
    return {"id": i, "name": name, "request": {"method": method, "header": [], "url": {"raw": url}}, "response": [], **({"event": list(events)} if events else {})}


@pytest.fixture
def world(app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["variable"] = [{"key": "base", "value": echo_server}]
    col["item"] = [req("a", "Ok", "{{base}}/status/200"), req("b", "Missing", "{{base}}/status/404"), req("c", "Echo", "{{base}}/echo?v={{v}}")]
    app.api("PUT", f"/api/collections/{cid}", col)
    return cid


@pytest.fixture
def ui(app, page, world):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def open_runner(p):
    p.locator("[data-name='Col']").click(button="right")
    p.click("[data-act=runner]")
    expect(T(p, "runner-tab")).to_be_visible()


def run(p, count):
    T(p, "runner-run").click()
    expect(T(p, "runner-s-done")).to_contain_text(f"{count}")
    expect(T(p, "runner-progress-label")).to_contain_text("Tugadi", timeout=20000)


def test_run_header_number_tests_column_and_history(ui):
    open_runner(ui)
    expect(T(ui, "runner-title")).to_contain_text("Col")
    run(ui, 3)
    expect(T(ui, "runner-title")).to_contain_text("run #1")
    expect(T(ui, "runner-sub")).to_contain_text("1 iteratsiya")
    expect(T(ui, "runner-s-ok")).to_have_text("2")
    expect(T(ui, "runner-s-fail")).to_have_text("1")
    expect(T(ui, "runner-tests-cell")).to_have_count(3)
    run(ui, 3)
    expect(T(ui, "runner-title")).to_contain_text("run #2")
    expect(T(ui, "runner-history").locator("option")).to_have_count(2)


def test_results_survive_reload_from_sqlite(ui):
    open_runner(ui)
    run(ui, 3)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    open_runner(ui)
    expect(T(ui, "runner-title")).to_contain_text("run #1")
    expect(T(ui, "runner-row")).to_have_count(3)


def test_data_file_iterations_and_stored_response(ui, tmp_path):
    open_runner(ui)
    f = tmp_path / "d.csv"
    f.write_text("v\nx1\nx2\n")
    T(ui, "runner-file").set_input_files(str(f))
    expect(T(ui, "runner-data-info")).to_contain_text("2 qator")
    run(ui, 6)
    expect(T(ui, "runner-sub")).to_contain_text("2 iteratsiya")
    T(ui, "runner-row").nth(5).click()
    expect(T(ui, "runner-body")).to_contain_text("x2")


def test_compare_with_previous_run_and_export_downloads(ui):
    open_runner(ui)
    run(ui, 3)
    expect(T(ui, "runner-compare")).to_be_disabled()
    run(ui, 3)
    T(ui, "runner-compare").click()
    expect(T(ui, "runner-compare-dialog")).to_be_visible()
    expect(T(ui, "rc-row")).to_have_count(3)
    expect(T(ui, "rc-summary")).to_contain_text("#1 → #2")
    ui.keyboard.press("Escape")
    for fmt, ext in (("json", ".json"), ("html", ".html"), ("junit", ".xml")):
        T(ui, "runner-export").click()
        with ui.expect_download() as d:
            T(ui, f"runner-export-{fmt}").click()
        assert d.value.suggested_filename.endswith(ext), d.value.suggested_filename


def test_parallel_and_stop_on_error_settings(ui):
    open_runner(ui)
    T(ui, "runner-parallel").fill("3")
    T(ui, "runner-stop-on-error").check()
    T(ui, "runner-run").click()
    expect(T(ui, "runner-progress-label")).to_contain_text(re.compile("Tugadi|To'xtatildi"), timeout=20000)
    expect(T(ui, "runner-s-fail")).to_have_text("1")


def test_folder_overview_last_results_come_from_sqlite_not_localstorage(ui):
    open_runner(ui)
    run(ui, 3)
    ui.evaluate("() => localStorage.removeItem('apirunner.lastrun.v1')")
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='Col']").dblclick()
    expect(T(ui, "ov-lr-ok")).to_have_text("2", timeout=8000)
    expect(T(ui, "ov-dots").locator(".dot")).to_have_count(3)
    expect(T(ui, "ov-row-status").first).to_be_visible()


def test_batch_and_runner_share_one_settings_panel(ui):
    ui.locator("[data-name='Ok']").dblclick()
    ui.click("[data-section=batch]")
    for t in ("batch-delay", "batch-concurrency", "batch-retry", "batch-timeout", "batch-save-vars", "batch-stop-on-error", "batch-save-responses", "batch-ssl"):
        expect(T(ui, t)).to_be_visible()
    open_runner(ui)
    for t in ("runner-delay", "runner-parallel", "runner-retry", "runner-timeout", "runner-save-vars", "runner-stop-on-error", "runner-save-responses", "runner-ssl"):
        expect(T(ui, t)).to_be_visible()


@pytest.mark.skipif(not scripting.available(), reason="quickjs-ng o'rnatilmagan")
def test_tests_column_counts_script_tests(ui, app, world):
    col = app.api("GET", f"/api/collections/{world}")
    col["item"][0]["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": ["pm.test('ok', () => pm.response.to.have.status(200));", "pm.test('bad', () => pm.response.to.have.status(500));"]}}]
    app.api("PUT", f"/api/collections/{world}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    open_runner(ui)
    run(ui, 3)
    expect(T(ui, "runner-tests-cell").first).to_have_text("1/2")
    expect(T(ui, "runner-s-tests")).to_contain_text("1")
    T(ui, "runner-row").first.click()
    expect(T(ui, "runner-test")).to_have_count(2)
