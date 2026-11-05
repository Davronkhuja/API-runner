"""Savat: o'chirilgan element 30 kun saqlanadi, tiklanadi; avval savatga yoziladi, keyin o'chiriladi."""
import pytest


def mk_col(client, name="Col"):
    cid = client.post("/api/collections", json={"name": name}).get_json()["id"]
    return cid


def add(client, cid, item, parent=None):
    r = client.post(f"/api/collections/{cid}/items", json={"item": item, "parent_id": parent})
    assert r.status_code in (200, 201), r.get_data(as_text=True)
    return r.get_json()


def req(name, rid=None):
    return {**({"id": rid} if rid else {}), "name": name, "request": {"method": "GET", "header": [], "url": {"raw": "http://x.test/" + name}}, "response": []}


def names(client, cid):
    def walk(items):
        return [(i["name"], walk(i["item"])) if "item" in i else i["name"] for i in items]
    return walk(client.get(f"/api/collections/{cid}").get_json()["item"])


@pytest.fixture
def clock(client):
    t = {"now": 1_000_000.0}
    client.app.extensions["trash"].now = lambda: t["now"]
    return t


def test_deleted_request_goes_to_trash_and_restores_in_place(client, clock):
    cid = mk_col(client)
    for n in ("a", "b", "c"):
        add(client, cid, req(n, n))
    assert client.delete(f"/api/collections/{cid}/items/b").get_json()["trash_id"]
    assert names(client, cid) == ["a", "c"]
    rows = client.get("/api/trash").get_json()
    assert len(rows) == 1 and rows[0]["kind"] == "item" and rows[0]["name"] == "b" and rows[0]["days_left"] == 30
    assert rows[0]["origin"]["collection_name"] == "Col" and rows[0]["origin"]["index"] == 1
    r = client.post(f"/api/trash/{rows[0]['id']}/restore").get_json()
    assert r["ok"] and r["item_id"] == "b"
    assert names(client, cid) == ["a", "b", "c"]                          # o'z o'rniga qaytdi
    assert client.get("/api/trash").get_json() == []


def test_folder_with_children_restores_whole_subtree_and_orphan_goes_to_root(client, clock):
    cid = mk_col(client)
    add(client, cid, {"id": "f", "name": "Fold", "item": []})
    add(client, cid, req("x", "x"), "f")
    add(client, cid, req("y", "y"), "f")
    client.delete(f"/api/collections/{cid}/items/x")                        # bola
    client.delete(f"/api/collections/{cid}/items/f")                        # keyin ota papka
    assert names(client, cid) == []
    rows = {r["name"]: r for r in client.get("/api/trash").get_json()}
    assert rows["Fold"]["origin"]["requests"] == 1 and rows["Fold"]["origin"]["folder"] is True
    assert client.post(f"/api/trash/{rows['x']['id']}/restore").get_json()["to_root"] is True      # ota yo'q → ildiz
    client.post(f"/api/trash/{rows['Fold']['id']}/restore")
    assert names(client, cid) == [("Fold", ["y"]), "x"]


def test_id_conflict_restores_with_new_ids(client, clock):
    cid = mk_col(client)
    add(client, cid, req("a", "a"))
    client.delete(f"/api/collections/{cid}/items/a")
    add(client, cid, req("a2", "a"))                                        # xuddi shu id band
    tid = client.get("/api/trash").get_json()[0]["id"]
    client.post(f"/api/trash/{tid}/restore")
    assert sorted(names(client, cid)) == ["a", "a2"]
    ids = [i["id"] for i in client.get(f"/api/collections/{cid}").get_json()["item"]]
    assert len(set(ids)) == 2


def test_collection_and_environment_restore(client, clock):
    cid = mk_col(client, "Big")
    add(client, cid, req("r1", "r1"))
    eid = client.post("/api/environments", json={"name": "Prod env"}).get_json()["id"]
    client.delete(f"/api/collections/{cid}")
    client.delete(f"/api/environments/{eid}")
    assert client.get(f"/api/collections/{cid}").status_code == 404
    rows = {r["kind"]: r for r in client.get("/api/trash").get_json()}
    assert rows["collection"]["origin"]["requests"] == 1 and rows["environment"]["name"] == "Prod env"
    assert client.post(f"/api/trash/{rows['collection']['id']}/restore").get_json()["collection_id"] == cid
    client.post(f"/api/trash/{rows['environment']['id']}/restore")
    assert names(client, cid) == ["r1"]
    assert any(e["id"] == eid for e in client.get("/api/workspace").get_json()["environments"])


def test_item_of_deleted_collection_restores_into_new_collection(client, clock):
    cid = mk_col(client, "Gone")
    add(client, cid, req("keep", "keep"))
    client.delete(f"/api/collections/{cid}/items/keep")
    client.delete(f"/api/collections/{cid}")
    item_row = next(r for r in client.get("/api/trash").get_json() if r["kind"] == "item")
    r = client.post(f"/api/trash/{item_row['id']}/restore").get_json()
    assert r["new_collection"] is True
    assert names(client, r["collection_id"]) == ["keep"]
    assert client.get(f"/api/collections/{r['collection_id']}").get_json()["info"]["name"] == "Gone (tiklangan)"


def test_expiry_after_30_days_purges_and_delete_forever_and_empty(client, clock):
    cid = mk_col(client)
    for n in ("a", "b", "c"):
        add(client, cid, req(n, n))
        client.delete(f"/api/collections/{cid}/items/{n}")
    rows = client.get("/api/trash").get_json()
    assert len(rows) == 3
    assert client.delete(f"/api/trash/{rows[0]['id']}").status_code == 200
    assert client.post(f"/api/trash/{rows[0]['id']}/restore").status_code == 404
    clock["now"] += 29 * 86400
    r = client.get("/api/trash").get_json()
    assert len(r) == 2 and r[0]["days_left"] == 1
    clock["now"] += 2 * 86400
    assert client.get("/api/trash").get_json() == []                         # 30 kundan keyin tozalandi
    add(client, cid, req("d", "d"))
    client.delete(f"/api/collections/{cid}/items/d")
    assert client.delete("/api/trash").get_json()["deleted"] == 1


def test_deletion_is_aborted_when_trash_cannot_be_written(client, monkeypatch):
    cid = mk_col(client)
    add(client, cid, req("keep", "keep"))
    tr = client.app.extensions["trash"]
    monkeypatch.setattr(tr, "_put", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        client.delete(f"/api/collections/{cid}/items/keep")
    assert names(client, cid) == ["keep"]                                     # ma'lumot yo'qolmadi


def test_trash_survives_restart_and_ignores_corrupt_files(client, clock, make_client):
    cid = mk_col(client)
    add(client, cid, req("a", "a"))
    client.delete(f"/api/collections/{cid}/items/a")
    import os
    open(os.path.join(client.app.extensions["trash"].dir, "bad.json"), "w").write("{not json")
    assert [r["name"] for r in client.get("/api/trash").get_json()] == ["a"]
