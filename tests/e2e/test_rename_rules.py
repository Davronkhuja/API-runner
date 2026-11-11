"""Nom qoidalari (Postman kabi): bir papkada bir xil nom ruxsat, faqat bo'sh nom rad; yumshoq ogohlantirish; URL nomidan qisqa taklif; Body HTML/JS."""
import pytest
from playwright.sync_api import expect

from tests.e2e.conftest import eventually

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
URL_NAME = "https://api.online-mahalla.uz/v1/hm/projects/item?x=1"


def mk(i, name, method="GET", url="http://h/x"):
    return {"id": i, "name": name, "request": {"method": method, "header": [], "url": {"raw": url}}, "response": []}


@pytest.fixture
def ui(app, page, echo_server):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    col["item"] = [{"id": "f", "name": "Fold", "item": [mk("g", "v1/hm/projects", "GET"), mk("p", "other", "POST"), mk("g2", "same", "GET"), mk("g3", "tmp", "GET"), mk("u", URL_NAME, "GET", URL_NAME)]},
                   {"id": "f2", "name": "Fold2", "item": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.cid = cid
    page.echo = echo_server
    return page


def names(app, cid):
    col = app.api("GET", f"/api/collections/{cid}")
    out = {}
    def walk(items):
        for it in items:
            out[it["id"]] = it["name"]
            walk(it.get("item", []))
    walk(col["item"])
    return out


def rename(p, name, new):
    p.locator(f"[data-name='{name}']").first.press("F2")
    T(p, "rename-input").fill(new)


def test_get_and_post_can_share_a_name_in_one_folder_and_be_renamed_again(ui, app):
    rename(ui, "other", "v1/hm/projects")                                                      # POST ham GET bilan bir xil nom
    T(ui, "rename-input").press("Enter")
    expect(T(ui, "rename-input")).to_have_count(0)
    eventually(lambda: (lambda n: n["g"] == n["p"] == "v1/hm/projects")(names(app, ui.cid)))         # saqlash asinxron
    n = names(app, ui.cid)
    assert n["g"] == n["p"] == "v1/hm/projects"
    expect(ui.locator("[data-name='v1/hm/projects']")).to_have_count(2)
    ui.locator("[data-name='v1/hm/projects']").nth(1).press("F2")                              # qayta nomlash ham ishlaydi
    T(ui, "rename-input").fill("renamed")
    T(ui, "rename-input").press("Enter")
    eventually(lambda: names(app, ui.cid)["p"] == "renamed")
    n = names(app, ui.cid)
    assert n["g"] == "v1/hm/projects" and n["p"] == "renamed"


def test_empty_name_is_the_only_hard_error(ui, app):
    rename(ui, "tmp", "   ")
    T(ui, "rename-input").press("Enter")
    expect(ui.locator(".toast")).to_contain_text("Nom bo'sh bo'lishi mumkin emas")
    assert names(app, ui.cid)["g3"] == "tmp"


def test_same_name_and_method_shows_soft_gray_warning_but_saves(ui, app):
    rename(ui, "tmp", "same")                                                                  # GET + GET, nom bir xil
    expect(T(ui, "name-warn")).to_contain_text("nomi va metodi (GET) bir xil")
    T(ui, "rename-input").press("Enter")
    eventually(lambda: names(app, ui.cid)["g3"] == "same")                                                  # bloklanmadi
    rename(ui, "other", "same")                                                                # POST — metod boshqa: ogohlantirish yo'q
    expect(T(ui, "name-warn")).to_have_count(0)
    T(ui, "rename-input").press("Enter")
    eventually(lambda: names(app, ui.cid)["p"] == "same")


def test_folders_follow_the_same_rule(ui, app):
    rename(ui, "Fold2", "Fold")
    expect(T(ui, "name-warn")).to_contain_text("shu nomli papka")
    T(ui, "rename-input").press("Enter")
    expect(T(ui, "rename-input")).to_have_count(0)
    eventually(lambda: (lambda n: n["f"] == n["f2"] == "Fold")(names(app, ui.cid)))
    n = names(app, ui.cid)
    assert n["f"] == n["f2"] == "Fold"


def test_url_named_request_gets_short_host_less_suggestion_on_rename(ui, app):
    ui.locator(f"[data-name='{URL_NAME}']").first.press("F2")
    expect(T(ui, "rename-input")).to_have_value("v1/hm/projects/item")                         # host va query yo'q
    T(ui, "rename-input").press("Enter")
    eventually(lambda: names(app, ui.cid)["u"] == "v1/hm/projects/item")


def test_save_dialog_suggests_path_name_for_unnamed_request(ui, app):
    T(ui, "new-tab").click()
    ui.fill("[data-testid=url]", "https://api.online-mahalla.uz/v1/hm/projects/item?id=1")
    T(ui, "save").click()
    expect(T(ui, "saveas-name")).to_have_value("v1/hm/projects/item")


# ── Body formati: HTML va JavaScript ──
def test_body_format_has_html_and_javascript_with_matching_content_type(ui, app):
    from conftest import set_body_mode
    T(ui, "new-tab").click()
    ui.select_option("[data-testid=method]", "POST")
    ui.fill("[data-testid=url]", ui.echo + "/echo")
    ui.click("[data-section=body]")
    opts = [o.strip() for o in ui.locator("[data-testid=body-format] option").all_inner_texts()]
    assert opts == ["JSON", "Text", "HTML", "JavaScript"]
    ui.select_option("[data-testid=body-format]", "html")
    ui.locator("[data-testid=body-raw]").click()
    ui.keyboard.type("<h1>Salom</h1>")
    expect(T(ui, "content-type-auto")).to_contain_text("text/html")
    with ui.expect_response(lambda r: r.url.endswith("/run_one")) as i:
        T(ui, "send").click()
    r = i.value.json()["response"]
    assert r["data"].startswith("<h1>Salom") and r["headers"]["Content-Type"].startswith("text/html")
    ui.select_option("[data-testid=body-format]", "javascript")
    expect(T(ui, "content-type-auto")).to_contain_text("application/javascript")
    expect(T(ui, "body-mode")).to_have_attribute("data-value", "raw")
    with ui.expect_response(lambda r: r.url.endswith("/run_one")) as i:
        T(ui, "send").click()
    assert i.value.json()["response"]["headers"]["Content-Type"].startswith("application/javascript")


def test_html_format_is_saved_and_restored(ui, app):
    T(ui, "new-tab").click()
    ui.select_option("[data-testid=method]", "POST")
    ui.fill("[data-testid=url]", "http://h/p")
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-format]", "html")
    ui.locator("[data-testid=body-raw]").click()
    ui.keyboard.type("<p>x</p>")
    T(ui, "save").click()
    ui.select_option("[data-testid=saveas-target]", label="Col")
    T(ui, "saveas-ok").click()
    import time
    end = time.time() + 8
    def saved():
        for it in app.api("GET", f"/api/collections/{ui.cid}")["item"]:
            if it["id"] not in ("f", "f2"):
                return it
    while time.time() < end and not saved():
        time.sleep(0.1)
    it = saved()
    assert it["request"]["body"]["options"]["raw"]["language"] == "html"
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator(f"[data-name='{it['name']}']").first.dblclick()
    ui.click("[data-section=body]")
    expect(T(ui, "body-format")).to_have_value("html")
