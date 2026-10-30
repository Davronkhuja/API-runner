"""Frontenddagi parseCurl() ning hozirgi xatti-harakati (brauzerda baholanadi)."""
import pytest


def parse(page, raw):
    return page.evaluate("raw => parseCurl(raw)", raw)


def test_basic_post_with_headers_and_body(app_page):
    r = parse(app_page, """curl -X POST 'https://a.io/x?y=1' -H 'Content-Type: application/json' -H "X-A: b" -d '{"k":1}'""")
    assert r["method"] == "POST" and r["url"] == "https://a.io/x?y=1"
    assert {"name": "X-A", "value": "b"} in r["headers"]
    assert r["body"] == '{"k":1}'


def test_data_implies_post(app_page):
    assert parse(app_page, "curl https://a.io -d 'a=1'")["method"] == "POST"


def test_basic_auth_flag(app_page):
    assert parse(app_page, "curl -u user:pass https://a.io")["auth"] == "Basic dXNlcjpwYXNz"


def test_line_continuations(app_page):
    r = parse(app_page, "curl https://a.io \\\n  -H 'A: 1' \\\n  --compressed")
    assert r["url"] == "https://a.io" and r["headers"] == [{"name": "A", "value": "1"}]


def test_not_curl_returns_null(app_page):
    assert parse(app_page, "https://a.io") is None


def test_no_url_returns_null(app_page):
    assert parse(app_page, "curl -X GET") is None


def test_url_flag(app_page):
    assert parse(app_page, "curl --url https://a.io/p")["url"] == "https://a.io/p"


def test_get_flag(app_page):
    assert parse(app_page, "curl -G https://a.io -d 'q=1'")["method"] == "GET"


@pytest.mark.parametrize("flag", ["-k", "-L", "-s", "--insecure", "--compressed"])
def test_known_valueless_flags_dont_swallow_url(app_page, flag):
    assert parse(app_page, f"curl {flag} https://a.io")["url"] == "https://a.io"
