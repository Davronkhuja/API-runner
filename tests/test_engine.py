"""Engine'ni to'g'ridan-to'g'ri (Flask'siz) tekshirish."""
from apirunner.core.engine import ExecContext, execute


def test_execute_basic(echo):
    r = execute({"method": "GET", "url": echo + "/echo?a={{x}}"}, ExecContext(variables={"x": "1"}))
    assert r["status"] == 200 and r["response"]["args"] == {"a": ["1"]} and r["error"] is False


def test_json_body_sent_verbatim_with_content_type(echo):
    body = '{ "a" :   1 }'            # bo'shliqlar saqlanadi (qayta serializatsiya yo'q)
    r = execute({"method": "POST", "url": echo + "/echo", "body": body, "body_type": "json"})
    assert r["response"]["data"] == body and r["response"]["headers"]["Content-Type"] == "application/json"


def test_never_raises_on_bad_url():
    r = execute({"method": "GET", "url": "not a url"})
    assert r["status"] == "ERROR" and r["error"] is True


def test_stop_before_start_returns_error_result(echo):
    r = execute({"method": "GET", "url": echo + "/echo"}, ExecContext(stop=lambda: True))
    assert r["status"] == "ERROR"


def test_retry_pause_is_configurable(echo):
    r = execute({"method": "GET", "url": echo + "/flaky"}, ExecContext(retry_count=2, retry_pause=0))
    assert r["status"] == 200 and r["retries"] == 2


def test_file_policy_allowed_files(echo, tmp_path):
    import os
    f = tmp_path / "ok.txt"
    f.write_text("hi")
    spec = {"method": "POST", "url": echo + "/echo", "params": [{"name": "d", "value": str(f), "type": "file"}]}
    assert execute(spec)["status"] == "ERROR"                                         # sukut bo'yicha taqiq
    ok = execute(spec, ExecContext(allowed_files=frozenset({os.path.realpath(f)})))   # aniq tanlangan fayl
    assert ok["status"] == 200 and ok["response"]["files"]["d"]["content"] == "hi"
