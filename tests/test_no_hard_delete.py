"""Hech bir o'chirish yo'li savatni chetlab o'tmaydi: eski /saved, yangi API, ommaviy o'chirish, Workspace metodlari."""
import pathlib
import re

import apirunner

SRC = pathlib.Path(apirunner.__file__).parent


def trash(client):
    return client.get("/api/trash").get_json()


def legacy_req(client, name, folder=None):
    return client.post("/saved/request", json={"name": name, "method": "GET", "url": "http://x.test/" + name, "folder_id": folder}).get_json()["id"]


def test_legacy_request_delete_goes_to_trash_and_restores(client):
    rid = legacy_req(client, "legacy-one")
    assert client.delete(f"/saved/request/{rid}").status_code == 200
    assert not any(r["name"] == "legacy-one" for r in client.get("/saved").get_json()["requests"])
    rows = trash(client)
    assert len(rows) == 1 and rows[0]["name"] == "legacy-one" and rows[0]["kind"] == "item"
    client.post(f"/api/trash/{rows[0]['id']}/restore")
    assert any(r["name"] == "legacy-one" for r in client.get("/saved").get_json()["requests"])


def test_legacy_folder_delete_keeps_folder_shell_with_its_auth_in_trash(client):
    fid = client.post("/saved/folder", json={"name": "Old folder"}).get_json()["id"]
    legacy_req(client, "inside", fid)
    col = client.get("/api/collections/saved").get_json()
    next(i for i in col["item"] if i["id"] == fid)["auth"] = {"type": "bearer", "bearer": [{"key": "token", "value": "T"}]}
    client.put("/api/collections/saved", json=col)
    client.delete(f"/saved/folder/{fid}")
    rows = trash(client)
    assert len(rows) == 1 and rows[0]["name"] == "Old folder" and rows[0]["origin"]["folder"] is True
    assert any(r["name"] == "inside" for r in client.get("/saved").get_json()["requests"])      # so'rov yo'qolmadi (eski xatti-harakat)
    client.post(f"/api/trash/{rows[0]['id']}/restore")
    col = client.get("/api/collections/saved").get_json()
    shell = next(i for i in col["item"] if i["id"] == fid)
    assert shell["auth"]["bearer"][0]["value"] == "T"                                           # papka sozlamalari tiklandi


def test_bulk_deletion_through_api_leaves_every_item_recoverable(client):
    cid = client.post("/api/collections", json={"name": "Bulk"}).get_json()["id"]
    for i in range(12):
        client.post(f"/api/collections/{cid}/items", json={"item": {"id": f"i{i}", "name": f"n{i}", "request": {"method": "GET", "header": [], "url": {"raw": "http://x/"}}, "response": []}})
    for i in range(12):
        assert client.delete(f"/api/collections/{cid}/items/i{i}").status_code == 200
    assert len(trash(client)) == 12
    eid = client.post("/api/environments", json={"name": "E"}).get_json()["id"]
    client.delete(f"/api/environments/{eid}")
    client.delete(f"/api/collections/{cid}")
    assert {r["kind"] for r in trash(client)} == {"item", "environment", "collection"}


def test_workspace_methods_cannot_hard_delete(client):
    ws = client.app.extensions["workspace"]
    cid = client.post("/api/collections", json={"name": "Direct"}).get_json()["id"]
    tid = ws.delete_collection(cid)
    assert tid and any(r["id"] == tid for r in trash(client))
    eid = client.post("/api/environments", json={"name": "DirectEnv"}).get_json()["id"]
    assert ws.delete_environment(eid) and any(r["name"] == "DirectEnv" for r in trash(client))


def test_source_has_no_delete_path_outside_workspace_and_trash():
    """Strukturaviy kafolat: collection/muhit fayli va daraxt elementi faqat Workspace (savat bilan) orqali o'chadi."""
    offenders = []
    for f in SRC.rglob("*.py"):
        rel = f.relative_to(SRC).as_posix()
        if rel.startswith(("static/", "storage/workspace.py", "storage/trash.py", "storage/tree_ops.py")):
            continue
        text = f.read_text(encoding="utf-8")
        if re.search(r"tree_ops\.delete_item\(", text):
            offenders.append((rel, "tree_ops.delete_item"))
        if rel.startswith("api/") and re.search(r"os\.(remove|unlink)\(|shutil\.rmtree\(", text):
            offenders.append((rel, "os.remove/rmtree in api"))
    assert offenders == []
