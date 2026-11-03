"""Server tomonidagi auth: API Key, JWT, AWS SigV4, Digest va OAuth 2.0 token endpoint."""
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone

from apirunner.core.auth import make_jwt, sigv4_headers


def post(client, **cfg):
    return client.post("/run_one", json=cfg).get_json()


# ── JWT ──
def test_jwt_hs256_matches_reference_vector():
    tok = make_jwt({"algorithm": "HS256", "secret": "your-256-bit-secret",
                    "payload": '{"sub":"1234567890","name":"John Doe","iat":1516239022}'}, {})
    assert tok == ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ."
                   "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")


def test_jwt_variables_and_other_hs_and_errors():
    t = make_jwt({"algorithm": "HS512", "secret": "{{s}}", "payload": '{"u":"{{u}}","t":{{$timestamp}}}'}, {"s": "k", "u": "bob"})
    h, p, sig = t.split(".")
    pad = lambda x: x + "=" * (-len(x) % 4)  # noqa: E731
    assert json.loads(base64.urlsafe_b64decode(pad(h)))["alg"] == "HS512"
    body = json.loads(base64.urlsafe_b64decode(pad(p)))
    assert body["u"] == "bob" and isinstance(body["t"], int)
    expect = base64.urlsafe_b64encode(hmac.new(b"k", f"{h}.{p}".encode(), hashlib.sha512).digest()).rstrip(b"=").decode()
    assert sig == expect
    for bad in ({"algorithm": "RS256"}, {"payload": "{nope"}):
        try:
            make_jwt({"secret": "s", **bad}, {})
            assert False
        except ValueError:
            pass


# ── AWS SigV4 (AWS test suite: get-vanilla) ──
def test_sigv4_get_vanilla_reference():
    h = sigv4_headers("GET", "https://example.amazonaws.com/", b"", "AKIDEXAMPLE", "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
                      "us-east-1", "service", now=datetime(2015, 8, 30, 12, 36, 0, tzinfo=timezone.utc))
    assert h["x-amz-date"] == "20150830T123600Z"
    assert h["Authorization"] == ("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20150830/us-east-1/service/aws4_request, "
                                  "SignedHeaders=host;x-amz-date, "
                                  "Signature=5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31")


def test_sigv4_session_token_and_s3_hash():
    h = sigv4_headers("PUT", "https://b.s3.amazonaws.com/k?b=2&a=1", b"data", "A", "S", "eu-west-1", "s3", session_token="TOK")
    assert h["x-amz-security-token"] == "TOK" and h["x-amz-content-sha256"] == hashlib.sha256(b"data").hexdigest()
    assert "x-amz-content-sha256" in h["Authorization"] and "x-amz-security-token" in h["Authorization"]


# ── engine orqali ──
def test_apikey_header_and_query(client, echo):
    d = post(client, url=echo + "/echo", auth_config={"type": "apikey", "key": "X-Key", "value": "{{k}}", "in": "header"}, env_vars={"k": "KV"})
    assert d["response"]["headers"]["X-Key"] == "KV"
    d = post(client, url=echo + "/echo", auth_config={"type": "apikey", "key": "api_key", "value": "Q", "in": "query"})
    assert d["response"]["args"]["api_key"] == ["Q"]


def test_jwt_header_and_query_via_engine(client, echo):
    d = post(client, url=echo + "/echo", auth_config={"type": "jwt", "secret": "s", "payload": '{"a":1}', "headerPrefix": "Bearer"})
    assert d["response"]["headers"]["Authorization"].startswith("Bearer eyJ")
    d = post(client, url=echo + "/echo", auth_config={"type": "jwt", "secret": "s", "payload": '{"a":1}', "addTo": "query", "queryParamKey": "jwt"})
    assert d["response"]["args"]["jwt"][0].count(".") == 2


def test_jwt_error_is_reported_not_raised(client, echo):
    d = post(client, url=echo + "/echo", auth_config={"type": "jwt", "algorithm": "RS256", "secret": "s"})
    assert d["status"] in ("ERR", "ERROR") and "RS256" in d["response"]


def test_awsv4_headers_sent_via_engine(client, echo):
    d = post(client, url=echo + "/echo?x=1", auth_config={"type": "awsv4", "accessKey": "AK", "secretKey": "SK", "region": "us-east-1", "service": "execute-api"})
    h = d["response"]["headers"]
    assert h["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AK/") and "X-Amz-Date" in h


def test_digest_auth_completes_challenge(client, echo):
    d = post(client, url=echo + "/digest", auth_config={"type": "digest", "username": "dan", "password": "pw"})
    assert d["status"] == 200 and d["response"] == {"digest": "ok"}
    d = post(client, url=echo + "/digest")
    assert d["status"] == 401


# ── OAuth 2.0 token endpoint ──
def tok(client, **kw):
    return client.post("/api/oauth2/token", json=kw)


def test_oauth_client_credentials_basic_header_and_expiry(client, echo):
    r = tok(client, grant_type="client_credentials", token_url=echo + "/oauth/token", client_id="cid", client_secret="sec", scope="a b")
    j = r.get_json()
    assert r.status_code == 200 and j["token"]["access_token"] == "AT-client_credentials"
    assert j["token"]["basic"] is True and j["token"]["echo"]["scope"] == "a b" and "client_secret" not in j["token"]["echo"]
    assert j["token"]["expires_at"] > 0


def test_oauth_body_client_auth_password_code_refresh(client, echo):
    j = tok(client, grant_type="password", token_url=echo + "/oauth/token", client_id="c", client_secret="s", client_auth="body", username="u", password="p").get_json()
    assert j["token"]["echo"] == {"grant_type": "password", "username": "u", "password": "p", "client_id": "c", "client_secret": "s"}
    j = tok(client, grant_type="authorization_code", token_url=echo + "/oauth/token", code="CODE", redirect_uri="http://x/cb", code_verifier="V", client_id="c").get_json()
    assert j["token"]["echo"]["code"] == "CODE" and j["token"]["echo"]["code_verifier"] == "V"
    j = tok(client, grant_type="refresh_token", token_url=echo + "/oauth/token", refresh_token="RT").get_json()
    assert j["token"]["echo"]["refresh_token"] == "RT"


def test_oauth_variables_and_errors(client, echo):
    j = tok(client, grant_type="client_credentials", token_url="{{h}}/oauth/token", client_id="{{id}}", variables={"h": echo, "id": "VID"}).get_json()
    assert j["ok"]
    r = tok(client, grant_type="client_credentials", token_url=echo + "/oauth/token", client_id="c", client_secret="bad")
    assert r.status_code == 400 and "bad creds" in r.get_json()["error"]
    assert tok(client, grant_type="nope", token_url=echo).status_code == 400
    assert tok(client, grant_type="client_credentials", token_url="ftp://x").status_code == 400
    assert tok(client, grant_type="client_credentials", token_url="http://127.0.0.1:9/t").status_code == 502


def test_oauth_callback_page_is_public_and_requires_no_token(make_client):
    c = make_client()
    c.environ_base.pop("HTTP_X_SESSION_TOKEN")
    r = c.get("/oauth/callback?code=1")
    assert r.status_code == 200 and b"apirunner-oauth" in r.data
    assert c.post("/api/oauth2/token", json={}).status_code == 401           # endpoint himoyalangan
