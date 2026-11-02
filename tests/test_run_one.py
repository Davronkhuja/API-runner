"""/run_one ning HOZIRGI xatti-harakati (refaktordan oldin qotirilgan)."""


def post(client, **cfg):
    return client.post("/run_one", json=cfg).get_json()


def test_get_with_params_and_headers(client, echo):
    d = post(client, url=echo + "/echo", method="GET",
             params=[{"name": "a", "value": "1"}, {"name": "", "value": "skip"}],
             headers=[{"name": "X-T", "value": "v"}])
    assert d["status"] == 200
    assert d["response"]["args"] == {"a": ["1"]}
    assert d["response"]["headers"]["X-T"] == "v"
    assert set(d) >= {"status", "time", "size", "response", "resp_headers", "url"}


def test_json_body(client, echo):
    d = post(client, url=echo + "/echo", method="POST", body='{"k": 1}',
             body_type="json", content_type="application/json")
    assert d["response"]["json"] == {"k": 1}


def test_invalid_json_sent_raw(client, echo):
    d = post(client, url=echo + "/echo", method="POST", body="{bad", body_type="json")
    assert d["response"]["data"] == "{bad"


def test_authorization_header(client, echo):
    d = post(client, url=echo + "/echo", method="GET", authorization="Bearer T")
    assert d["response"]["headers"]["Authorization"] == "Bearer T"


def test_env_vars_simple_replacement(client, echo):
    d = post(client, url=echo + "/echo?x={{v}}", method="GET", env_vars={"v": "42"})
    assert d["response"]["args"] == {"x": ["42"]}


def test_env_vars_with_spaces_replaced(client, echo):
    """Bosqich 1: yagona engine — '{{ v }}' run_one'da ham /run kabi almashtiriladi."""
    d = post(client, url=echo + "/echo", method="GET",
             headers=[{"name": "X", "value": "{{ v }}"}], env_vars={"v": "42"})
    assert d["response"]["headers"]["X"] == "42"


def test_http_error_status_passthrough(client, echo):
    d = post(client, url=echo + "/status/404", method="GET")
    assert d["status"] == 404 and d["response"] == {"code": 404}


def test_text_response(client, echo):
    d = post(client, url=echo + "/text", method="GET")
    assert d["response"] == "salom dunyo"


def test_large_text_truncated_at_500k(client, echo):
    d = post(client, url=echo + "/big", method="GET")
    assert d["size"] == 600_000
    assert len(d["response"]) < 600_000 and "qisqartirildi" in d["response"]


def test_connection_error_reported_as_ERR(client):
    d = post(client, url="http://127.0.0.1:1/x", method="GET", timeout=2)
    assert d["status"] == "ERR" and d["size"] == 0


def test_timeout_reported_as_ERR(client, echo):
    d = post(client, url=echo + "/slow?s=1.5", method="GET", timeout=0.2)
    assert d["status"] == "ERR"


def test_missing_url_is_400(client):
    assert client.post("/run_one", json={}).status_code == 400


def test_multipart_supported_via_unified_engine(client, echo):
    """Bosqich 1: run_one ham /run kabi multipart yuboradi."""
    d = post(client, url=echo + "/echo", method="POST", body_type="multipart",
             multipart_fields=[{"name": "k", "value": "{{v}}"}], env_vars={"v": "val"})
    assert d["response"]["form"] == {"k": ["val"]}


def test_file_param_in_run_one(client, echo, isolated):
    f = isolated / "uploads" / "a.txt"
    f.write_text("mazmun")
    d = post(client, url=echo + "/echo", method="POST",
             params=[{"name": "doc", "value": f"{f}::x.txt", "type": "file"}])
    assert d["response"]["files"]["doc"] == {"filename": "x.txt", "content": "mazmun"}
