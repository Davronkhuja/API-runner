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


def test_timing_breakdown_keys_and_missing_values_are_none(echo):
    r = execute({"method": "GET", "url": echo + "/echo"})
    t = r["timing"]
    assert set(t) == {"dns", "connect", "tls", "ttfb", "total"}
    assert t["dns"] is None and t["tls"] is None            # plain HTTP: TLS yo'q, DNS alohida o'lchanmaydi
    assert t["connect"] is not None and 0 <= t["ttfb"] <= t["total"] + 0.01
    assert r["http_version"] == "HTTP/1.1"


def test_error_result_has_null_timing_and_no_exception():
    r = execute({"method": "GET", "url": "http://127.0.0.1:1/"})
    assert r["status"] == "ERROR" and r["timing"] is None


def test_http2_is_opt_in_and_falls_back_on_cleartext(echo):
    assert execute({"method": "GET", "url": echo + "/echo"})["http_version"] == "HTTP/1.1"
    r = execute({"method": "GET", "url": echo + "/echo", "http2": True})   # h2c yo'q → HTTP/1.1
    assert r["status"] == 200 and r["http_version"] == "HTTP/1.1"


def test_query_in_url_survives_when_params_empty_and_merges_with_params(echo):
    r = execute({"method": "GET", "url": echo + "/echo?a=1", "params": [{"name": "b", "value": "2"}]})
    assert r["response"]["args"] == {"a": ["1"], "b": ["2"]}


def test_redirects_are_followed(echo):
    r = execute({"method": "GET", "url": echo + "/redirect"})
    assert r["status"] == 200 and r["url"].endswith("/echo")


def test_engine_applies_path_variables_and_dynamic(echo):
    from apirunner.core.engine import ExecContext, execute
    r = execute({"method": "GET", "url": echo + "/echo/:id?g={{$guid}}", "path_variables": [{"name": "id", "value": "{{n}}"}]},
                ExecContext(variables={"n": "77"}))
    assert r["status"] != "ERROR", r["response"]
    assert "/echo/77" in r["url"] and "%7B" not in r["url"] and "$guid" not in r["url"]


def test_binary_body_sends_raw_bytes_and_respects_file_policy(echo, tmp_path):
    from apirunner.core.engine import ExecContext, execute
    f = tmp_path / "blob.bin"
    f.write_bytes(b"\x00\x01raw-bytes")
    spec = {"method": "POST", "url": echo + "/echo", "body_file": str(f)}
    r = execute(spec, ExecContext(allowed_files=frozenset({str(f.resolve())})))
    assert r["status"] == 200 and r["response"]["headers"]["Content-Type"] == "application/octet-stream"
    assert "raw-bytes" in r["response"]["data"]
    r = execute({**spec, "content_type": "image/png"}, ExecContext(allowed_files=frozenset({str(f.resolve())})))
    assert r["response"]["headers"]["Content-Type"] == "image/png"
    r = execute(spec, ExecContext())                                             # ruxsat berilmagan yo'l
    assert r["status"] == "ERROR" and r["error_code"] == "file_policy"
