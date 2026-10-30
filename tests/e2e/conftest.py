"""E2E: api_runner'ni izolyatsiyalangan holda (tmp saved fayl, tasodifiy port) jonli ishga tushiradi."""
import threading

import pytest
from werkzeug.serving import make_server

import api_runner


@pytest.fixture(scope="session")
def app_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("e2e_data")
    api_runner.SAVED_FILE = str(d / "saved_requests.json")
    api_runner.TEMP_UPLOAD_DIR = str(d)
    srv = make_server("127.0.0.1", 0, api_runner.app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def app_page(page, app_url):
    page.goto(app_url)
    return page
