"""Umumiy fixture'lar: lokal echo server va izolyatsiyalangan api_runner."""
import os
import sys
import threading

import pytest
from flask import Flask, jsonify, request
from werkzeug.serving import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import api_runner  # noqa: E402


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
def isolated(tmp_path, monkeypatch):
    """saved_requests.json va .tmp_uploads ni vaqtinchalik papkaga yo'naltiradi."""
    monkeypatch.setattr(api_runner, "SAVED_FILE", str(tmp_path / "saved_requests.json"))
    up = tmp_path / "uploads"
    up.mkdir()
    monkeypatch.setattr(api_runner, "TEMP_UPLOAD_DIR", str(up))
    return tmp_path


@pytest.fixture
def client(isolated):
    api_runner.app.config["TESTING"] = True
    return api_runner.app.test_client()


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
