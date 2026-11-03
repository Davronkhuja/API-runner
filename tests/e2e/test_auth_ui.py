"""Bosqich 2 / Auth: turlar formasi, OAuth 2.0 oqimlari, meros, avtomatik yangilash."""
import json

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    return page


def new_req(p, url):
    T(p, "new-tab").click()
    p.fill("[data-testid=url]", url)
    p.click("[data-section=auth]")


def f(p, key, val):
    T(p, f"auth-f-{key}").fill(val)


def sel_type(p, t):
    p.select_option("[data-testid=auth-type]", t)


def send_json(p):
    """Yuboradi va /run_one javobini (eski natija bilan adashmaslik uchun) to'g'ridan-to'g'ri o'qiydi."""
    with p.expect_response(lambda r: r.url.endswith("/run_one")) as info:
        T(p, "send").click()
    d = info.value.json()
    assert d["status"] == 200, d
    return d["response"]


def oauth_form(p, echo, grant, **extra):
    sel_type(p, "oauth2")
    p.select_option("[data-testid=auth-f-grant_type]", grant)
    f(p, "accessTokenUrl", echo + "/oauth/token") if grant != "implicit" else None
    f(p, "clientId", "cid")
    for k, v in extra.items():
        f(p, k, v)


def test_type_forms_render_expected_fields(ui):
    new_req(ui, "http://x")
    for t, keys in {"apikey": ["key", "value", "in"], "digest": ["username", "password"], "awsv4": ["accessKey", "secretKey", "region", "service"],
                    "jwt": ["algorithm", "secret", "payload", "addTo"], "oauth2": ["grant_type", "accessTokenUrl", "clientId", "scope"]}.items():
        sel_type(ui, t)
        for k in keys:
            expect(T(ui, f"auth-f-{k}")).to_be_visible()
    sel_type(ui, "oauth2")
    expect(T(ui, "auth-f-authUrl")).to_have_count(0)                         # client_credentials'da yo'q
    ui.select_option("[data-testid=auth-f-grant_type]", "authorization_code_pkce")
    expect(T(ui, "auth-f-authUrl")).to_be_visible()
    expect(T(ui, "auth-f-clientSecret")).to_have_count(0)                    # PKCE: secret kerak emas


def test_apikey_header_and_query(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    sel_type(ui, "apikey")
    f(ui, "key", "X-API-Key"); f(ui, "value", "K1")
    assert send_json(ui)["headers"]["X-Api-Key"] == "K1"
    ui.select_option("[data-testid=auth-f-in]", "query"); f(ui, "key", "api_key")
    assert send_json(ui)["args"]["api_key"] == ["K1"]


def test_jwt_digest_awsv4_via_ui(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    sel_type(ui, "jwt"); f(ui, "secret", "s"); f(ui, "payload", '{"a":1}')
    assert send_json(ui)["headers"]["Authorization"].startswith("Bearer eyJ")
    sel_type(ui, "awsv4"); f(ui, "accessKey", "AK"); f(ui, "secretKey", "SK")
    assert send_json(ui)["headers"]["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AK/")
    ui.fill("[data-testid=url]", echo_server + "/digest")
    sel_type(ui, "digest"); f(ui, "username", "dan"); f(ui, "password", "pw")
    assert send_json(ui)["digest"] == "ok"


def test_oauth_client_credentials_fetches_token_on_send_and_shows_it(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    oauth_form(ui, echo_server, "client_credentials", clientSecret="sec", scope="a")
    expect(T(ui, "oauth-none")).to_be_visible()
    assert send_json(ui)["headers"]["Authorization"] == "Bearer AT-client_credentials"
    expect(T(ui, "oauth-token")).to_be_visible()
    expect(T(ui, "oauth-token-value")).not_to_contain_text("client_credentials")   # maskalangan
    expect(T(ui, "oauth-expiry")).to_contain_text("s qoldi")
    T(ui, "oauth-clear").click()
    expect(T(ui, "oauth-none")).to_be_visible()


def test_oauth_get_new_token_button_password_grant_and_query_placement(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    oauth_form(ui, echo_server, "password", username="u", password="p")
    T(ui, "oauth-get").click()
    expect(T(ui, "oauth-token")).to_be_visible()
    ui.select_option("[data-testid=auth-f-addTokenTo]", "queryParams")
    j = send_json(ui)
    assert j["args"]["access_token"] == ["AT-password"] and "Authorization" not in j["headers"]


def test_oauth_error_is_shown(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    oauth_form(ui, echo_server, "client_credentials", clientSecret="bad")
    T(ui, "oauth-get").click()
    expect(T(ui, "oauth-error")).to_contain_text("bad creds")
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("ERR")                         # token yo'q — so'rov xato bilan to'xtaydi


def test_oauth_authorization_code_pkce_popup_flow(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    oauth_form(ui, echo_server, "authorization_code_pkce", authUrl=echo_server + "/oauth/authorize")
    with ui.expect_popup():
        T(ui, "oauth-get").click()
    expect(T(ui, "oauth-token")).to_be_visible(timeout=15000)
    assert send_json(ui)["headers"]["Authorization"] == "Bearer AT-authorization_code"


def test_oauth_implicit_popup_flow(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    oauth_form(ui, echo_server, "implicit", authUrl=echo_server + "/oauth/authorize")
    with ui.expect_popup():
        T(ui, "oauth-get").click()
    expect(T(ui, "oauth-token")).to_be_visible(timeout=15000)
    assert send_json(ui)["headers"]["Authorization"] == "Bearer IMP-TOK"


def test_oauth_auth_code_requires_token_and_says_what_to_do(ui, echo_server):
    new_req(ui, echo_server + "/echo")
    oauth_form(ui, echo_server, "authorization_code", authUrl=echo_server + "/oauth/authorize", clientSecret="s")
    T(ui, "send").click()
    expect(T(ui, "resp-status")).to_have_text("ERR")
    expect(T(ui, "resp-body")).to_contain_text("Get New Access Token")


def oauth_collection(app, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "OA"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["auth"] = {"type": "oauth2", "oauth2": [{"key": "grant_type", "value": "client_credentials"}, {"key": "accessTokenUrl", "value": echo_server + "/oauth/token"},
                                                {"key": "clientId", "value": "cid"}, {"key": "clientSecret", "value": "s"}, {"key": "addTokenTo", "value": "header"},
                                                {"key": "headerPrefix", "value": "Bearer"}]}
    col["item"] = [{"id": "q1", "name": "Q", "request": {"method": "GET", "header": [], "url": {"raw": echo_server + "/echo"}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)


def test_collection_level_oauth_is_inherited_and_works_in_batch(app, page, echo_server):
    oauth_collection(app, echo_server)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.locator("[data-name='Q']").dblclick()
    assert send_json(page)["headers"]["Authorization"] == "Bearer AT-client_credentials"
    page.click("[data-section=batch]")
    T(page, "batch-run").click()
    expect(T(page, "batch-status")).to_contain_text("Bajarildi")


def test_expired_token_is_refreshed_with_refresh_token(app, browser, echo_server):
    oauth_collection(app, echo_server)
    ctx = browser.new_context()
    key = f"client_credentials|{echo_server}/oauth/token||cid||"
    ctx.add_init_script("sessionStorage.getItem('apirunner_oauth_tokens') || sessionStorage.setItem('apirunner_oauth_tokens', JSON.stringify("
                        + json.dumps({key: {"access_token": "OLD", "refresh_token": "RTOK", "expires_at": 1, "obtained": 1}}) + "))")
    page = ctx.new_page()
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.locator("[data-name='Q']").dblclick()
    assert send_json(page)["headers"]["Authorization"] == "Bearer AT-refresh_token"
    ctx.close()
