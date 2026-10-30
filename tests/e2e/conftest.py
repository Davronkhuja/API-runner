"""E2E: api_runner'ni izolyatsiyalangan holda (tmp workspace, tasodifiy port) jonli ishga tushiradi."""
import threading

import pytest
from werkzeug.serving import make_server

from apirunner.app import create_app


@pytest.fixture(scope="session")
def app_url(tmp_path_factory):
    d = tmp_path_factory.mktemp("e2e_data")
    app = create_app(workspace_dir=str(d / "workspace"), saved_file=str(d / "saved_requests.json"),
                     upload_dir=str(d / "uploads"))
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture
def app_page(page, app_url):
    page.goto(app_url)
    return page
