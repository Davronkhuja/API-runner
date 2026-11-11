"""CLI (`apirunner run`): lokal echo server bilan, haqiqiy subprocess va exit code'lar."""
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from apirunner import cli

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def col(base_tests=True):
    ev = lambda code: [{"listen": "test", "script": {"exec": code if isinstance(code, list) else [code]}}]  # noqa: E731
    return {"info": {"name": "CLI demo", "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
            "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{tok}}"}]},
            "item": [
                {"name": "Echo", "request": {"method": "GET", "url": {"raw": "{{base}}/echo?i={{n}}"}}, "event": ev(["pm.test('status 200', () => pm.response.to.have.status(200));", "pm.test('bearer sent', () => pm.expect(pm.response.json().headers.Authorization).to.equal('Bearer T0K'));", "pm.environment.set('seen', 'yes')"])},
                {"name": "Folder", "item": [
                    {"name": "Inside", "request": {"method": "POST", "url": {"raw": "{{base}}/echo"}, "body": {"mode": "raw", "raw": "{\"n\": \"{{n}}\"}", "options": {"raw": {"language": "json"}}}}, "event": ev("pm.test('json echoed', () => pm.expect(pm.response.json().json.n).to.be.a('string'))")},
                    {"name": "NotFound", "request": {"method": "GET", "url": {"raw": "{{base}}/status/404"}}, "event": ev("pm.test('expects 404', () => pm.response.to.have.status(404))")}]}]}


def env(echo):
    return {"id": "e1", "name": "Local", "values": [{"key": "base", "value": echo, "enabled": True, "type": "default"}, {"key": "tok", "value": "T0K", "enabled": True, "type": "secret"}, {"key": "n", "value": "7", "enabled": True, "type": "default"}], "_postman_variable_scope": "environment"}


def run_cli(*args, cwd=None):
    r = subprocess.run([sys.executable, "-m", "apirunner", *args], capture_output=True, text=True, cwd=cwd or ROOT, timeout=120, env={**os.environ, "PYTHONPATH": ROOT, "NO_COLOR": "1"})
    return r


@pytest.fixture
def files(tmp_path, echo):
    (tmp_path / "c.json").write_text(json.dumps(col()))
    (tmp_path / "e.json").write_text(json.dumps(env(echo)))
    return tmp_path


def test_run_passes_prints_progress_summary_and_exits_zero(files):
    r = run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "✓ GET    Echo" in r.stdout and "✓ status 200" in r.stdout and "✓ bearer sent" in r.stdout and "✓ expects 404" in r.stdout
    assert "so'rovlar" in r.stdout and "test-assertlar" in r.stdout and "Xatolar" not in r.stdout


def test_failing_test_gives_exit_code_1_and_lists_failures(files):
    c = col()
    c["item"][1]["item"][1]["event"][0]["script"]["exec"] = ["pm.test('expects 200', () => pm.response.to.have.status(200))"]
    (files / "c.json").write_text(json.dumps(c))
    r = run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"))
    assert r.returncode == 1
    assert "✗ expects 200" in r.stdout and "Xatolar (1)" in r.stdout and "NotFound" in r.stdout


def test_http_404_is_not_a_failure_unless_requested(files):
    c = col()
    c["item"][1]["item"][1]["event"] = []
    (files / "c.json").write_text(json.dumps(c))
    assert run_cli("run", str(files / "c.json"), "-e", str(files / "e.json")).returncode == 0
    assert run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"), "--fail-on-http-errors").returncode == 1


def test_transport_error_is_a_failure(files, tmp_path):
    e = env("http://127.0.0.1:1")
    (files / "e.json").write_text(json.dumps(e))
    r = run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"), "--timeout-request", "2000")
    assert r.returncode == 1 and "ERR" in r.stdout


def test_folder_filter_iterations_data_and_bail(files, tmp_path):
    r = run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"), "--folder", "Folder", "-n", "2", "--no-color")
    assert r.returncode == 0 and "Echo" not in r.stdout.split("\n\n", 1)[1].split("┌")[0] and r.stdout.count("Inside") == 2
    (tmp_path / "d.csv").write_text("n\n1\n2\n3\n")
    r = run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"), "-d", str(tmp_path / "d.csv"), "--folder", "Folder")
    assert r.stdout.count("Inside") == 3 and "3 iteratsiya" in r.stdout
    (tmp_path / "d.json").write_text(json.dumps([{"n": "a"}, {"n": "b"}]))
    r = run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"), "-d", str(tmp_path / "d.json"))
    assert "2 iteratsiya" in r.stdout
    c = col()
    c["item"][0]["event"] = [{"listen": "test", "script": {"exec": ["pm.test('boom', () => { throw new Error('x') })"]}}]
    (files / "bail.json").write_text(json.dumps(c))
    r = run_cli("run", str(files / "bail.json"), "-e", str(files / "e.json"), "--bail", "--fail-on-http-errors")
    assert r.returncode == 1 and "Inside" not in r.stdout                                   # birinchi xatodan keyin to'xtadi
    r = run_cli("run", str(files / "bail.json"), "-e", str(files / "e.json"))
    assert "Inside" in r.stdout                                                              # --bail yo'q: davom etadi


def test_reporters_json_junit_html_files(files, tmp_path):
    out = tmp_path / "rep"
    r = run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"), "--reporters", "cli,json,junit,html", "--export-dir", str(out))
    assert r.returncode == 0
    names = sorted(os.listdir(out))
    assert [n.rsplit(".", 1)[1] for n in names] == ["html", "json", "xml"]
    j = json.loads((out / [n for n in names if n.endswith(".json")][0]).read_text())
    assert j["collection"] == "CLI demo" and j["summary"]["requests"] == 3 and j["summary"]["failures"] == 0 and len(j["results"]) == 3
    assert j["results"][0]["tests"][0] == {"name": "status 200", "passed": True, "skipped": False}
    x = ET.fromstring((out / [n for n in names if n.endswith(".xml")][0]).read_text())
    assert x.tag == "testsuites" and any(tc.get("name") == "status 200" for tc in x.iter("testcase"))
    assert "CLI demo" in (out / [n for n in names if n.endswith(".html")][0]).read_text()
    exp = tmp_path / "one.json"
    r = run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"), "--reporters", "json", "--reporter-json-export", str(exp), "--silent")
    assert exp.exists() and r.stdout.strip() == ""


def test_scripts_update_environment_and_export_env_without_touching_inputs(files, tmp_path):
    before = (files / "e.json").read_text()
    out = tmp_path / "env-out.json"
    r = run_cli("run", str(files / "c.json"), "-e", str(files / "e.json"), "--export-environment", str(out), "--env-var", "n=9")
    assert r.returncode == 0
    vals = {v["key"]: v["value"] for v in json.loads(out.read_text())["values"]}
    assert vals["seen"] == "yes" and vals["n"] == "9" and vals["tok"] == ""                # secret Postman eksportida bo'sh
    assert (files / "e.json").read_text() == before                                          # kirish fayli o'zgarmadi


def test_usage_errors_exit_code_2(files, tmp_path):
    assert run_cli("run", str(tmp_path / "nope.json")).returncode == 2
    (tmp_path / "bad.json").write_text("{not json at all")
    r = run_cli("run", str(tmp_path / "bad.json"))
    assert r.returncode == 2 and "xato:" in r.stderr
    assert run_cli("run", str(files / "c.json"), "--folder", "Nope", "-e", str(files / "e.json")).returncode == 2
    assert run_cli("run", str(files / "c.json"), "-e", str(tmp_path / "missing-env.json")).returncode == 2
    assert run_cli("run", str(files / "c.json"), "--reporters", "pdf").returncode == 2
    assert run_cli("run", str(files / "c.json"), "-n", "0").returncode == 2


def test_other_formats_and_workspace_collection_by_name(files, tmp_path, echo):
    spec = {"openapi": "3.0.0", "info": {"title": "OA", "version": "1"}, "servers": [{"url": echo}], "paths": {"/echo": {"get": {"summary": "e", "responses": {"200": {"description": "ok"}}}}}}
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    r = run_cli("run", str(tmp_path / "spec.json"))
    assert r.returncode == 0 and "GET    e" in r.stdout
    from apirunner.storage.workspace import Workspace
    ws = Workspace(str(tmp_path / "myws"))
    from apirunner.importers.postman import import_postman
    ws.save_collection(import_postman(col()))
    ws.save_environment(env(echo))
    r = run_cli("run", "cli demo", "-e", "local", "--workspace", str(tmp_path / "myws"))
    assert r.returncode == 0, r.stdout + r.stderr


def test_default_invocation_still_starts_server_parser():
    args = cli.build_parser().parse_args(["serve", "--port", "5099", "--no-browser"])
    assert args.cmd == "serve" and args.port == 5099
    assert run_cli("--version").stdout.startswith("apirunner ")
