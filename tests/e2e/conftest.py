"""E2E: api_runner'ni izolyatsiyalangan holda (tmp workspace, tasodifiy port) jonli ishga tushiradi.

Har test o'z serveri va workspace'i bilan ishlaydi (holat tablar/daraxt testlariga sizib o'tmasin).
"""
import threading

import os

os.environ["APIRUNNER_TESTING"] = "1"

import pytest
import requests
from werkzeug.serving import make_server

from apirunner.app import create_app

E2E_TOKEN = "e2e-token"


class App:
    def __init__(self, tmp):
        self.tmp = tmp
        self._start()

    def _start(self):
        self.flask = create_app(workspace_dir=str(self.tmp / "workspace"), saved_file=str(self.tmp / "saved_requests.json"),
                                upload_dir=str(self.tmp / "uploads"), session_token=E2E_TOKEN,
                                backup_dir=str(self.tmp / "backups"))
        self.srv = make_server("127.0.0.1", 0, self.flask, threaded=True)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}"

    def restart(self):
        """Server qayta ishga tushishini taqlid qiladi (xuddi shu workspace, yangi port va jarayon holati)."""
        self.srv.shutdown()
        self._start()

    def api(self, method, path, json=None):
        r = requests.request(method, self.url + path, json=json, headers={"X-Session-Token": E2E_TOKEN})
        r.raise_for_status()
        return r.json()

    def seed(self, structure, name="Col"):
        """structure: [(id, name, children|None)] — papka (children list) yoki so'rov (None)."""
        cid = self.api("POST", "/api/collections", {"name": name})["id"]

        def build(nodes):
            out = []
            for i, n, kids in nodes:
                if kids is None:
                    out.append({"id": i, "name": n, "request": {"method": "GET", "header": [], "url": {"raw": "http://x/" + n}}, "response": []})
                else:
                    out.append({"id": i, "name": n, "item": build(kids)})
            return out
        col = self.api("GET", f"/api/collections/{cid}")
        col["item"] = build(structure)
        self.api("PUT", f"/api/collections/{cid}", col)
        return cid

    def collection(self, cid):
        return self.api("GET", f"/api/collections/{cid}")


@pytest.fixture
def app(tmp_path):
    a = App(tmp_path)
    yield a
    a.srv.shutdown()


@pytest.fixture
def app_url(app):
    return app.url


@pytest.fixture
def app_page(page, app):
    """Eski UI (/legacy) — paritet e2e yashil bo'lguncha saqlanadi."""
    page.goto(app.url + "/legacy")
    return page


@pytest.fixture
def new_page(page, app):
    """Yangi frontend (/)."""
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def eventually(fn, timeout=8.0, interval=0.05):
    """Shart bajarilguncha kutadi (qat'iy sleep emas). `fn` True qaytarsa yoki AssertionError tashlamasa — tayyor."""
    import time
    end = time.monotonic() + timeout
    last = None
    while time.monotonic() < end:
        try:
            r = fn()
            if r is None or r:
                return
        except AssertionError as e:
            last = e
        time.sleep(interval)
    raise AssertionError(f"shart {timeout}s ichida bajarilmadi" + (f": {last}" if last else ""))
