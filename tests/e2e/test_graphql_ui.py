"""GraphQL: introspection, schema explorer, avtoto'ldirish, validatsiya, variables (lokal graphql-core serveri)."""
import re

import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import set_body_mode

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731


@pytest.fixture
def ui(app, page, gql_server):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    T(page, "new-tab").click()
    page.select_option("[data-testid=method]", "POST")
    u = T(page, "url")
    u.click()
    page.keyboard.type(gql_server + "/graphql")
    page.keyboard.press("Escape")
    page.click("[data-section=body]")
    set_body_mode(page, "graphql")
    return page


def test_introspection_explorer_builds_query_and_sends(ui):
    expect(T(ui, "gql-explorer-toggle")).to_be_disabled()
    T(ui, "gql-introspect").click()
    expect(T(ui, "gql-schema-info")).to_contain_text("Query, Mutation, Subscription")
    T(ui, "gql-explorer-toggle").click()
    expect(T(ui, "gql-explorer")).to_be_visible()
    ui.locator("[data-testid=gql-field]").filter(has=ui.locator("b", has_text=re.compile(r"^user$"))).click()
    q = T(ui, "gql-query").inner_text()
    assert "query Op($id: ID!)" in q and "user(id: $id)" in q and "name" in q
    expect(T(ui, "gql-issues")).to_have_count(0)                                            # skelet o'zgaruvchilarni ham to'ldiradi
    T(ui, "gql-vars").click()
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type("{}")
    expect(T(ui, "gql-issues")).to_contain_text("$id")                                      # majburiy o'zgaruvchi yo'q
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type('{"id": "1"}')
    expect(T(ui, "gql-issues")).to_have_count(0)
    with ui.expect_response(lambda r: r.url.endswith("/run_one")) as i:
        T(ui, "send").click()
    d = i.value.json()
    assert d["status"] == 200 and d["response"]["data"]["user"]["name"] == "Ali"


def test_type_browser_shows_enum_input_and_navigates(ui):
    T(ui, "gql-introspect").click()
    T(ui, "gql-explorer-toggle").click()
    T(ui, "gql-type-search").fill("role")
    ui.locator("[data-testid=gql-type]", has_text="Role").click()
    expect(T(ui, "gql-type-name")).to_contain_text("Role")
    expect(ui.locator("[data-testid=gql-explorer]")).to_contain_text("ADMIN")
    T(ui, "gql-back").click()
    T(ui, "gql-type-search").fill("User")
    ui.locator("[data-testid=gql-type]").filter(has=ui.locator("b", has_text=re.compile(r"^User$"))).click()
    expect(ui.locator("[data-testid=gql-explorer]")).to_contain_text("posts")


def test_autocomplete_and_validation_use_the_schema(ui):
    T(ui, "gql-introspect").click()
    expect(T(ui, "gql-schema-info")).to_be_visible()
    ed = T(ui, "gql-query")
    ed.click()
    ui.keyboard.type("{ us", delay=40)
    ui.wait_for_timeout(300)
    if not ui.locator(".cm-tooltip-autocomplete").count():
        ui.keyboard.press("Control+Space")
    expect(ui.locator(".cm-tooltip-autocomplete")).to_contain_text("users")
    ui.wait_for_timeout(250)
    ui.keyboard.press("Escape")
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type("{ nonexistentField }", delay=20)
    expect(ui.locator(".cm-lintRange-error").first).to_be_visible(timeout=5000)             # sxemada yo'q maydon


def test_introspection_errors_and_auth_headers(ui, gql_server):
    u = T(ui, "url")
    u.click()
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type(gql_server + "/graphql-noint")
    ui.keyboard.press("Escape")
    T(ui, "gql-introspect").click()
    expect(T(ui, "gql-error")).to_contain_text("introspection")
    u.click()
    ui.keyboard.press("ControlOrMeta+a")
    ui.keyboard.type(gql_server + "/graphql-secure")
    ui.keyboard.press("Escape")
    T(ui, "gql-introspect").click()
    expect(T(ui, "gql-error")).to_contain_text("401")
    ui.click("[data-section=auth]")
    ui.select_option("[data-testid=auth-type]", "bearer")
    T(ui, "auth-token").fill("s3cret")
    ui.click("[data-section=body]")
    T(ui, "gql-introspect").click()
    expect(T(ui, "gql-schema-info")).to_be_visible()
    expect(T(ui, "gql-error")).to_have_count(0)


def test_invalid_variables_json_is_flagged(ui):
    T(ui, "gql-query").click()
    ui.keyboard.type("query($a: Int!) { hello }")
    T(ui, "gql-vars").click()
    ui.keyboard.type("{bad")
    expect(T(ui, "gql-issues")).to_contain_text("JSON noto'g'ri")
