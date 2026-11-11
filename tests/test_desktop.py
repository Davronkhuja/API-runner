"""Desktop rejim: server tasodifiy loopback portida, ma'lumot berilgan home'da (haqiqiy workspace'ga tegmaydi)."""
import os

import requests

from apirunner import desktop


def test_start_server_uses_given_home_and_loopback(tmp_path):
    url, stop, app = desktop.start_server(str(tmp_path / "home"))
    try:
        assert url.startswith("http://127.0.0.1:")
        r = requests.get(url + "/")
        assert r.status_code == 200 and "X-Frame-Options" in r.headers
        assert requests.get(url + "/api/workspace").status_code == 401                 # token talab qilinadi
        assert os.path.isdir(tmp_path / "home" / "workspace")
    finally:
        stop()


def test_default_home_is_overridable_and_outside_repo(monkeypatch, tmp_path):
    monkeypatch.setenv("APIRUNNER_HOME", str(tmp_path))
    assert desktop.default_home() == str(tmp_path)
    monkeypatch.delenv("APIRUNNER_HOME")
    assert "API Runner" in desktop.default_home() or "api-runner" in desktop.default_home()
