"""Umumiy fixture'lar: lokal echo server va izolyatsiyalangan api_runner."""
import os
import sys

os.environ["APIRUNNER_TESTING"] = "1"      # create_app() faqat aniq (tmp) yo'llar bilan ishlaydi
import threading

import pytest
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from apirunner.app import create_app  # noqa: E402

TOKEN = "test-token"


def _build_echo_app():
    app = Flask("echo")
    state = {"flaky": 0}

    @app.route("/echo", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def echo():
        return jsonify({
            "method": request.method,
            "args": request.args.to_dict(flat=False),
            "headers": {k: v for k, v in request.headers.items()},
            "json": request.get_json(silent=True),
            "data": request.get_data(as_text=True),
            "form": request.form.to_dict(flat=False),
            "files": {k: {"filename": f.filename, "content": f.read().decode("utf-8", "replace")}
                      for k, f in request.files.items()},
        })

    @app.route("/status/<int:code>")
    def status(code):
        return jsonify({"code": code}), code

    @app.route("/text")
    def text():
        return "salom dunyo", 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.route("/flaky")
    def flaky():
        """Birinchi ikki chaqiruv 500, keyin 200."""
        state["flaky"] += 1
        return (jsonify({"n": state["flaky"]}), 500) if state["flaky"] <= 2 else jsonify({"n": state["flaky"]})

    @app.route("/flaky/reset")
    def flaky_reset():
        state["flaky"] = 0
        return "ok"

    @app.route("/slow")
    def slow():
        import time
        time.sleep(float(request.args.get("s", "0.3")))
        return jsonify({"slow": True})

    @app.route("/redirect")
    def redirect_():
        from flask import redirect
        return redirect("/echo")

    @app.route("/big")
    def big():
        return "x" * 600_000, 200, {"Content-Type": "text/plain"}

    return app


@pytest.fixture(scope="session")
def echo_server():
    srv = make_server("127.0.0.1", 0, _build_echo_app(), threaded=True)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def echo(echo_server):
    import requests
    requests.get(echo_server + "/flaky/reset")
    return echo_server


@pytest.fixture
def isolated(tmp_path):
    """Hamma narsa (workspace, saved fayl, uploads) vaqtinchalik papkada."""
    (tmp_path / "uploads").mkdir()
    return tmp_path


@pytest.fixture
def make_client(isolated):
    """make_client(legacy=<saved_requests.json matni | None>) -> test client (tokenli)."""
    def _make(legacy=None):
        saved = isolated / "saved_requests.json"
        if legacy is not None:
            saved.write_text(legacy, encoding="utf-8")
        app = create_app(workspace_dir=str(isolated / "workspace"), saved_file=str(saved),
                         upload_dir=str(isolated / "uploads"), session_token=TOKEN,
                         backup_dir=str(isolated / "backups"))
        app.config["TESTING"] = True
        c = app.test_client()
        c.environ_base["HTTP_X_SESSION_TOKEN"] = TOKEN
        c.app = app
        return c
    return _make


@pytest.fixture
def client(make_client):
    return make_client()


@pytest.fixture
def run_batch(client):
    """/run + /stream ni to'liq o'qib, (results, summary) qaytaradi."""
    import json

    def _run(cfg, stop_after=None):
        r = client.post("/run", json=cfg)
        assert r.status_code == 200, r.get_data(as_text=True)
        job_id = r.get_json()["job_id"]
        if stop_after is not None:
            import time
            time.sleep(stop_after)
            client.post(f"/stop/{job_id}")
        body = client.get(f"/stream/{job_id}").get_data(as_text=True)
        results, summary = [], None
        for block in body.split("\n\n"):
            if block.startswith("event: result"):
                results.append(json.loads(block.split("data: ", 1)[1]))
            elif block.startswith("event: done"):
                summary = json.loads(block.split("data: ", 1)[1])
        return results, summary

    return _run
