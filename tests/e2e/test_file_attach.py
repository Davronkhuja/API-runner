"""Postman uslubidagi fayl biriktirish: Body → form-data (Turi: Text|File), ko'p fayl, sudrash, topilmadi, binary, Params 📎 tezkor tugmasi."""
import os
import re
import time

import pytest
from playwright.sync_api import expect

T = lambda p, t: p.locator(f"[data-testid={t}]")  # noqa: E731
FD = "[data-testid=formdata-table]"


@pytest.fixture
def ui(app, page, echo_server):
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.echo = echo_server
    return page


def new_post(p, url=None):
    T(p, "new-tab").click()
    p.select_option("[data-testid=method]", "POST")
    p.fill("[data-testid=url]", url or p.echo + "/echo")


def to_formdata(p):
    p.click("[data-section=body]")
    p.select_option("[data-testid=body-mode]", "multipart")


def fd_rows(p):
    return p.locator(f"{FD} tbody tr")


def make(tmp_path, name, data="x"):
    f = tmp_path / name
    f.write_bytes(data if isinstance(data, bytes) else data.encode())
    return str(f)


def send(p):
    with p.expect_response(lambda r: r.url.endswith("/run_one")) as i:
        T(p, "send").click()
    return i.value.json()


def drop_files(p, selector, files):
    """Brauzerda haqiqiy File obyektlari bilan drop hodisasi: files = [(nom, matn)]."""
    p.evaluate("""([sel, files]) => {
        const el = document.querySelector(sel); const dt = new DataTransfer();
        for (const [n, t] of files) dt.items.add(new File([t], n));
        el.dispatchEvent(new DragEvent('dragover', {dataTransfer: dt, bubbles: true, cancelable: true}));
        el.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true})); }""", [selector, files])


# ── Body → form-data: Turi ustuni ──
def test_formdata_has_type_column_text_default_and_file_choice(ui, tmp_path):
    new_post(ui)
    to_formdata(ui)
    heads = [t.strip() for t in ui.locator(".kv-head thead th").all_inner_texts()]
    assert "Turi" in heads and "Content-Type" in heads
    expect(ui.locator(f"{FD} tr[data-ghost] [data-testid=fd-type]")).to_have_count(0)        # ghost'da select yo'q
    ui.locator(f"{FD} [data-cell='0:0']").fill("title")
    sel = ui.locator(f"{FD} [data-testid=fd-type]").first
    assert sel.input_value() == "text" and sel.locator("option").all_inner_texts() == ["Text", "File"]
    ui.locator(f"{FD} [data-cell='0:1']").fill("salom")
    ui.locator(f"{FD} [data-cell='1:0']").fill("doc")
    ui.locator(f"{FD} [data-testid=fd-type]").nth(1).select_option("file")
    expect(ui.locator(f"{FD} [data-testid=fd-add]").first).to_have_text("Fayl tanlash…")
    f = make(tmp_path, "ariza.pdf", "PDFDATA")
    ui.locator(f"{FD} input[type=file]").first.set_input_files(f)
    expect(T(ui, "fd-name")).to_have_text("ariza.pdf")
    expect(T(ui, "fd-size")).to_have_text("7 B")
    d = send(ui)["response"]
    assert d["form"] == {"title": ["salom"]} and d["files"]["doc"] == {"filename": "ariza.pdf", "content": "PDFDATA"}
    assert d["files_ct"]["doc"] == "application/pdf"                                          # Content-Type fayl turidan


def test_multiple_files_under_one_key_replace_and_remove(ui, tmp_path):
    new_post(ui)
    to_formdata(ui)
    ui.locator(f"{FD} [data-cell='0:0']").fill("docs")
    ui.locator(f"{FD} [data-testid=fd-type]").first.select_option("file")
    ui.locator(f"{FD} input[type=file]").first.set_input_files([make(tmp_path, "a.txt", "AAA"), make(tmp_path, "b.txt", "BBB")])
    expect(T(ui, "fd-file")).to_have_count(2)
    d = send(ui)["response"]
    assert d["files_all"]["docs"] == ["a.txt", "b.txt"]                                       # bitta kalitga ikkita fayl
    with ui.expect_file_chooser() as fc:
        T(ui, "fd-replace").first.click()
    fc.value.set_files(make(tmp_path, "c.txt", "CCC"))
    expect(T(ui, "fd-name")).to_have_text(["c.txt", "b.txt"])                                 # birinchisi almashtirildi
    T(ui, "fd-remove").nth(1).click()
    expect(T(ui, "fd-file")).to_have_count(1)
    assert send(ui)["response"]["files"]["docs"]["content"] == "CCC"


def test_content_type_column_placeholder_follows_file_and_custom_value_is_sent(ui, tmp_path):
    new_post(ui)
    to_formdata(ui)
    ui.locator(f"{FD} [data-cell='0:0']").fill("img")
    ui.locator(f"{FD} [data-testid=fd-type]").first.select_option("file")
    ui.locator(f"{FD} input[type=file]").first.set_input_files(make(tmp_path, "r.png", b"\x89PNG"))
    ct = T(ui, "fd-ct").first
    expect(ct).to_have_attribute("placeholder", "image/png")
    assert send(ui)["response"]["files_ct"]["img"] == "image/png"
    ct.fill("application/x-custom")
    assert send(ui)["response"]["files_ct"]["img"] == "application/x-custom"


# ── sudrab tashlash ──
def test_dropping_files_on_a_row_turns_it_into_a_file_row(ui):
    new_post(ui)
    to_formdata(ui)
    ui.locator(f"{FD} [data-cell='0:0']").fill("x")
    ui.locator(f"{FD} [data-cell='0:1']").fill("matn")
    drop_files(ui, f"{FD} tbody tr:nth-child(1)", [("d1.txt", "D1"), ("d2.txt", "D2")])
    expect(T(ui, "fd-name")).to_have_text(["d1.txt", "d2.txt"])                               # qator o'zi File'ga o'tdi, ikkala fayl bitta kalitda
    expect(ui.locator(f"{FD} [data-testid=fd-type]").first).to_have_value("file")
    assert send(ui)["response"]["files_all"]["x"] == ["d1.txt", "d2.txt"]
    drop_files(ui, f"{FD} tr[data-ghost]", [("g.txt", "G")])                                  # ghost'ga tashlash — kalit "file"
    expect(ui.locator(f"{FD} [data-cell='1:0']")).to_have_value("file")
    expect(fd_rows(ui)).to_have_count(3)


# ── Params 📎 tezkor tugmasi ──
def test_params_attach_moves_file_to_body_formdata_and_removes_the_param_row(ui, tmp_path):
    new_post(ui, ui.echo + "/echo?keep=1")
    ui.click("[data-section=params]")
    ui.locator("[data-testid=params-table] input[type=text]").nth(0).fill("keep")
    ui.locator("[data-testid=params-table] [data-cell='1:0']").fill("doc")                    # ikkinchi qator: kalit "doc"
    f = make(tmp_path, "up.txt", "UP")
    ui.locator("[data-testid=params-table] tbody tr").nth(1).locator("input[type=file]").set_input_files(f)
    expect(T(ui, "toast")).to_contain_text("Fayl Body → form-data'ga qo'shildi")
    expect(T(ui, "body-panel")).to_be_visible()                                               # Body tabi ochildi
    expect(T(ui, "body-mode")).to_have_value("multipart")
    expect(ui.locator(f"{FD} [data-cell='0:0']")).to_have_value("doc")
    expect(T(ui, "fd-name")).to_have_text("up.txt")
    ui.click("[data-section=params]")
    assert [i.input_value() for i in ui.locator("[data-testid=params-table] [data-cell$=':0']").all()] == ["keep", ""]   # "doc" qatori o'chdi, ghost qoldi
    d = send(ui)["response"]
    assert d["args"] == {"keep": ["1"]} and d["files"]["doc"] == {"filename": "up.txt", "content": "UP"}


def test_dropping_a_file_on_params_adds_a_file_row_named_file(ui):
    new_post(ui)
    ui.click("[data-section=params]")
    drop_files(ui, "[data-testid=params-table] tr[data-ghost]", [("dropped.txt", "DD")])
    expect(T(ui, "body-panel")).to_be_visible()
    expect(ui.locator(f"{FD} [data-cell='0:0']")).to_have_value("file")
    expect(T(ui, "fd-name")).to_have_text("dropped.txt")
    ui.click("[data-section=params]")
    expect(ui.locator("[data-testid=params-table] tbody tr")).to_have_count(1)                # Params'ga hech narsa qo'shilmadi


def test_attach_icon_only_in_params(ui):
    new_post(ui)
    ui.click("[data-section=params]")
    ui.locator("[data-testid=params-table] [data-cell='0:0']").fill("a")
    expect(T(ui, "params-attach")).to_have_count(1)
    ui.click("[data-section=headers]")
    ui.locator("[data-testid=headers-table] [data-cell='0:0']").fill("H")
    expect(ui.locator("[data-testid=headers-table] input[type=file]")).to_have_count(0)
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "form")
    ui.locator("[data-testid=form-table] [data-cell='0:0']").fill("k")
    expect(ui.locator("[data-testid=form-table] input[type=file]")).to_have_count(0)


# ── saqlash: fayl workspace ichida ──
def test_saved_request_keeps_working_file_lives_in_workspace(app, ui, tmp_path):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    expect(ui.locator("[data-name='Col']")).to_be_visible()                                     # daraxt yuklandi (saqlash maqsadi kerak)
    new_post(ui)
    to_formdata(ui)
    ui.locator(f"{FD} [data-cell='0:0']").fill("doc")
    ui.locator(f"{FD} [data-testid=fd-type]").first.select_option("file")
    ui.locator(f"{FD} input[type=file]").first.set_input_files(make(tmp_path, "keep.txt", "KEEP"))
    expect(T(ui, "fd-name")).to_have_text("keep.txt")
    T(ui, "save").click()
    ui.fill("[data-testid=saveas-name]", "Yuklash")
    ui.select_option("[data-testid=saveas-target]", label="Col")                                # boshlang'ich "Mening collection" ham bor
    T(ui, "saveas-ok").click()
    deadline = time.time() + 8
    while time.time() < deadline and not app.api("GET", f"/api/collections/{cid}")["item"]:
        time.sleep(0.1)                                                                         # saqlash asinxron
    item = app.api("GET", f"/api/collections/{cid}")["item"][0]
    fd = item["request"]["body"]["formdata"]
    assert fd == [{"key": "doc", "type": "file", "src": [fd[0]["src"][0]]}] and fd[0]["src"][0].startswith("files/")
    assert app.api("POST", "/api/files/status", {"refs": fd[0]["src"]})[fd[0]["src"][0]]["exists"]
    for p in (tmp_path / "keep.txt", ):                                                       # asl fayl o'chsa ham saqlangan so'rov ishlaydi
        p.unlink()
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='Yuklash']").dblclick()
    ui.click("[data-section=body]")
    expect(T(ui, "fd-name")).to_have_text("keep.txt")
    expect(T(ui, "fd-size")).to_have_text("4 B")
    assert send(ui)["response"]["files"]["doc"]["content"] == "KEEP"


# ── fayl topilmasa ──
@pytest.fixture
def broken(app, ui, tmp_path):
    cid = app.api("POST", "/api/collections", {"name": "Col"})["id"]
    col = app.api("GET", f"/api/collections/{cid}")
    gone = str(tmp_path / "tozalangan" / "ariza.pdf")
    col["item"] = [{"id": "r1", "name": "Eskirgan", "request": {"method": "POST", "header": [], "url": {"raw": ui.echo + "/echo"},
                    "body": {"mode": "formdata", "formdata": [{"key": "doc", "type": "file", "src": [gone]}, {"key": "t", "type": "text", "value": "v"}]}}, "response": []}]
    app.api("PUT", f"/api/collections/{cid}", col)
    ui.reload()
    ui.wait_for_selector("[data-testid=app]")
    ui.locator("[data-name='Eskirgan']").dblclick()
    ui.click("[data-section=body]")
    return ui


def test_missing_file_row_is_red_with_message_and_warns_before_sending(broken):
    p = broken
    expect(p.locator(f"{FD} tr[data-missing]")).to_have_count(1)
    expect(T(p, "fd-missing")).to_have_text("topilmadi, qayta tanlang")
    sent = []
    p.on("request", lambda r: sent.append(r.url) if r.url.endswith("/run_one") else None)
    T(p, "send").click()
    expect(T(p, "confirm-dialog")).to_contain_text("ariza.pdf")
    p.click("[data-testid=confirm-dialog] button:not(.primary)")
    p.wait_for_timeout(300)
    assert sent == []                                                                         # ogohlantirishdan keyin yuborilmadi
    T(p, "send").click()
    T(p, "confirm-ok").click()
    expect(T(p, "resp-body")).to_contain_text("Fayl topilmadi: ariza.pdf")


def test_choosing_the_file_again_clears_the_red_state(broken, tmp_path):
    p = broken
    with p.expect_file_chooser() as fc:
        T(p, "fd-replace").click()
    fc.value.set_files(make(tmp_path, "ariza.pdf", "YANGI"))
    expect(p.locator(f"{FD} tr[data-missing]")).to_have_count(0)
    expect(T(p, "fd-missing")).to_have_count(0)
    expect(T(p, "fd-size")).to_have_text("5 B")
    assert send(p)["response"]["files"]["doc"]["content"] == "YANGI"


# ── binary ──
def test_binary_drop_zone_name_size_and_auto_content_type(ui, tmp_path):
    new_post(ui)
    ui.click("[data-section=body]")
    ui.select_option("[data-testid=body-mode]", "binary")
    expect(T(ui, "binary-panel")).to_contain_text("Faylni shu yerga tashlang")
    drop_files(ui, "[data-testid=binary-panel]", [("rasm.png", "PNGDATA")])
    expect(T(ui, "binary-name")).to_have_text("rasm.png")
    expect(T(ui, "binary-size")).to_have_text("7 B")
    expect(T(ui, "content-type-auto")).to_contain_text("image/png")                           # Content-Type avtomatik
    d = send(ui)["response"]
    assert d["headers"]["Content-Type"] == "image/png" and d["data"] == "PNGDATA"
    ui.locator("[data-testid=binary-file]").set_input_files(make(tmp_path, "doc.pdf", "P"))   # almashtirish
    expect(T(ui, "binary-name")).to_have_text("doc.pdf")
    assert send(ui)["response"]["headers"]["Content-Type"] == "application/pdf"
    T(ui, "binary-clear").click()
    expect(T(ui, "binary-pick")).to_be_visible()


# ── snippet / cURL ──
def test_snippets_and_curl_export_show_form_data_files(ui, tmp_path):
    new_post(ui, "http://h/up")
    to_formdata(ui)
    ui.locator(f"{FD} [data-cell='0:0']").fill("title")
    ui.locator(f"{FD} [data-cell='0:1']").fill("salom")
    ui.locator(f"{FD} [data-cell='1:0']").fill("file")
    ui.locator(f"{FD} [data-testid=fd-type]").nth(1).select_option("file")
    ui.locator(f"{FD} input[type=file]").first.set_input_files([make(tmp_path, "ariza.pdf"), make(tmp_path, "ilova.pdf")])
    expect(T(ui, "fd-file")).to_have_count(2)
    T(ui, "curl-btn").click()
    out = T(ui, "curl-output")
    expect(out).to_contain_text("-F 'title=salom'")
    expect(out).to_contain_text("-F 'file=@ariza.pdf'")
    expect(out).to_contain_text("-F 'file=@ilova.pdf'")
    ui.select_option("[data-testid=snippet-lang]", "python")
    expect(out).to_contain_text('open("ariza.pdf", "rb")')
    ui.select_option("[data-testid=snippet-lang]", "php")
    expect(out).to_contain_text("new CURLFile")


# ── eski sessiya qoralamasi ──
def test_old_session_draft_with_params_file_row_moves_to_body(app, page, tmp_path):
    f = tmp_path / "old.txt"
    f.write_text("OLD")
    draft = {"name": "Eski", "method": "POST", "url": app.url + "/api/version", "headers": [{"key": "", "value": "", "enabled": True}],
             "params": [{"key": "q", "value": "1", "enabled": True}, {"key": "doc", "value": f"{f}::old.txt", "enabled": True, "kind": "file"}, {"key": "", "value": "", "enabled": True}]}
    state = {"tabs": {"v": 1, "activeId": "t1", "tabs": [{"id": "t1", "kind": "request", "ref": None, "title": "Eski", "preview": False, "dirty": True, "draft": draft, "response": None, "scroll": {"req": 0, "resp": 0}}]}}
    app.api("PUT", "/api/ui-state", state)
    page.goto(app.url)
    page.wait_for_selector("[data-testid=app]")
    page.click("[data-section=params]")
    assert [i.input_value() for i in page.locator("[data-testid=params-table] [data-cell$=':0']").all()] == ["q", ""]
    page.click("[data-section=body]")
    expect(T(page, "body-mode")).to_have_value("multipart")
    expect(T(page, "fd-name")).to_have_text("old.txt")


# ── tozalash (Sozlamalar → Fayllar) ──
def test_settings_files_section_cleans_only_unused_files(app, ui, tmp_path):
    keep = app.api("POST", "/api/environments", {"name": "E"})["id"]                             # (muhit havola qilmaydi — faqat tab/kolleksiya)
    assert keep
    import requests
    from conftest import E2E_TOKEN
    up = requests.post(app.url + "/api/files", files={"file": ("lost.txt", b"lost")}, headers={"X-Session-Token": E2E_TOKEN}).json()
    root = app.tmp / "workspace" / "files"
    os.utime(root / up["hash"], (time.time() - 7200,) * 2)
    T(ui, "settings-btn").click()
    expect(T(ui, "files-unused")).to_have_text("1")
    T(ui, "files-cleanup").click()
    expect(T(ui, "confirm-dialog")).to_contain_text("1 ta ishlatilmayotgan fayl")
    T(ui, "confirm-ok").click()
    expect(T(ui, "files-unused")).to_have_text("0")
    assert not (root / up["hash"]).exists()


# ── migratsiya: eski so'rov migratsiyadan keyin AVVALGIDEK yuboradi (xarakteristika) ──
def test_migrated_legacy_request_sends_exactly_what_it_sent_before(tmp_path, page, echo_server):
    import requests
    from apirunner.storage import model
    from apirunner.storage.atomic import atomic_write_json
    from apirunner.storage.workspace import Workspace
    from conftest import E2E_TOKEN, App

    up = tmp_path / "uploads"
    up.mkdir()
    (up / "u.bin").write_bytes(b"CONTENT")
    legacy = {"id": "r1", "name": "Yuklash", "method": "POST", "url": echo_server + "/echo", "headers": [], "body": "", "body_type": "raw",
              "params": [{"name": "q", "value": "1"}, {"name": "doc", "value": f"{up / 'u.bin'}::ariza.pdf", "type": "file"}]}
    ws = Workspace(str(tmp_path / "workspace"))
    col = model.new_collection("Eski")
    col["item"] = [model.legacy_to_request_item(legacy)]
    ws.save_collection(col)
    meta = ws.meta()
    meta["schemaVersion"] = 2                                                                  # migratsiyadan oldingi sxema
    atomic_write_json(os.path.join(ws.root, "workspace.json"), meta)

    app = App(tmp_path)                                                                        # ishga tushishda migratsiya (zaxira bilan) bajariladi
    try:
        old = requests.post(app.url + "/run_one", json={"url": legacy["url"], "method": "POST", "params": legacy["params"]}, headers={"X-Session-Token": E2E_TOKEN}).json()
        assert os.listdir(tmp_path / "backups")                                                # migratsiyadan oldin zaxira olingan
        page.goto(app.url)
        page.wait_for_selector("[data-testid=app]")
        page.locator("[data-name='Yuklash']").dblclick()
        page.click("[data-section=params]")
        assert [i.input_value() for i in page.locator("[data-testid=params-table] [data-cell$=':0']").all()] == ["q", ""]     # matnli parametr query'da qoldi
        page.click("[data-section=body]")
        expect(T(page, "body-mode")).to_have_value("multipart")
        expect(T(page, "fd-name")).to_have_text("ariza.pdf")
        new = send(page)
        keep = lambda d: {k: d["response"][k] for k in ("method", "args", "form", "files")}  # noqa: E731
        assert keep(old) == keep(new) and new["response"]["files"]["doc"] == {"filename": "ariza.pdf", "content": "CONTENT"}
        (up / "u.bin").unlink()                                                                # vaqtinchalik papka tozalansa ham ishlaydi (fayl workspace'ga ko'chirilgan)
        assert send(page)["response"]["files"]["doc"]["content"] == "CONTENT"
    finally:
        app.srv.shutdown()
