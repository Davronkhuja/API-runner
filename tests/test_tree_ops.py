import pytest


def mk(client, structure):
    """structure: [(id, name, [children]|None)] -> yangi collection, id qaytaradi."""
    cid = client.post("/api/collections", json={"name": "T"}).get_json()["id"]

    def build(nodes):
        out = []
        for i, n, kids in nodes:
            if kids is None:
                out.append({"id": i, "name": n, "request": {"method": "GET", "url": {"raw": "http://x/" + n}}, "response": []})
            else:
                out.append({"id": i, "name": n, "item": build(kids)})
        return out
    col = client.get(f"/api/collections/{cid}").get_json()
    col["item"] = build(structure)
    client.put(f"/api/collections/{cid}", json=col)
    return cid


def shape(client, cid):
    def walk(items):
        return [(i["id"], walk(i["item"])) if "item" in i else i["id"] for i in items]
    return walk(client.get(f"/api/collections/{cid}").get_json()["item"])


def mv(client, cid, ids, target, pos, dst=None, copy=False):
    return client.post("/api/items/move", json={"src": cid, "dst": dst or cid, "ids": ids,
                                                "target_id": target, "position": pos, "copy": copy})


BASE = [("f1", "F1", [("a", "A", None), ("b", "B", None)]), ("f2", "F2", [("f3", "F3", [])]), ("c", "C", None)]


def test_reorder_within_folder(client):
    cid = mk(client, BASE)
    assert mv(client, cid, ["b"], "a", "before").status_code == 200
    assert shape(client, cid)[0] == ("f1", ["b", "a"])


def test_reorder_after(client):
    cid = mk(client, BASE)
    mv(client, cid, ["a"], "b", "after")
    assert shape(client, cid)[0] == ("f1", ["b", "a"])


def test_move_request_into_other_folder_and_root(client):
    cid = mk(client, BASE)
    mv(client, cid, ["a"], "f2", "inside")
    assert shape(client, cid) == [("f1", ["b"]), ("f2", [("f3", []), "a"]), "c"]
    mv(client, cid, ["a"], None, "inside")
    assert shape(client, cid)[-1] == "a"


def test_move_folder_into_folder(client):
    cid = mk(client, BASE)
    mv(client, cid, ["f1"], "f3", "inside")
    assert shape(client, cid) == [("f2", [("f3", [("f1", ["a", "b"])])]), "c"]


def test_cannot_move_folder_into_itself_or_descendant(client):
    cid = mk(client, BASE)
    assert mv(client, cid, ["f2"], "f3", "inside").status_code == 400
    assert mv(client, cid, ["f2"], "f2", "inside").status_code == 400
    assert mv(client, cid, ["f2"], "f3", "before").status_code == 400
    assert shape(client, cid) == [("f1", ["a", "b"]), ("f2", [("f3", [])]), "c"]


def test_inside_requires_folder_and_bad_args(client):
    cid = mk(client, BASE)
    assert mv(client, cid, ["a"], "c", "inside").status_code == 400
    assert mv(client, cid, ["a"], None, "before").status_code == 400
    assert mv(client, cid, [], "c", "before").status_code == 400
    assert mv(client, cid, ["nope"], "c", "before").status_code == 400
    assert mv(client, cid, ["a"], "nope", "before").status_code == 400
    assert mv(client, cid, ["a"], "c", "sideways").status_code == 400


def test_copy_creates_new_ids_and_keeps_original(client):
    cid = mk(client, BASE)
    m = mv(client, cid, ["f1"], "c", "after", copy=True).get_json()["mapping"]
    s = shape(client, cid)
    assert s[0] == ("f1", ["a", "b"]) and s[2] == "c"
    new = s[3]
    assert new[0] == m["f1"] != "f1" and len(new[1]) == 2 and not {"a", "b"} & set(new[1])


def test_multi_move_keeps_given_order(client):
    cid = mk(client, BASE)
    mv(client, cid, ["c", "a"], "f2", "inside")
    assert shape(client, cid)[1] == ("f2", [("f3", []), "c", "a"])


def test_multi_move_parent_and_child_selected_moves_parent_only(client):
    cid = mk(client, BASE)
    mv(client, cid, ["f1", "a"], "f2", "inside")
    assert shape(client, cid) == [("f2", [("f3", []), ("f1", ["a", "b"])]), "c"]


def test_move_between_collections(client):
    c1 = mk(client, BASE)
    c2 = mk(client, [("z", "Z", None)])
    assert mv(client, c1, ["f1"], "z", "before", dst=c2).status_code == 200
    assert shape(client, c2) == [("f1", ["a", "b"]), "z"]
    assert shape(client, c1) == [("f2", [("f3", [])]), "c"]


def test_move_expands_target_folder(client):
    cid = mk(client, BASE)
    mv(client, cid, ["c"], "f3", "inside")
    col = client.get(f"/api/collections/{cid}").get_json()
    assert col["item"][1]["item"][0]["x-apirunner"]["expanded"] is True


def test_order_persists_in_collection_file_and_export(client):
    cid = mk(client, BASE)
    mv(client, cid, ["c"], "f1", "before")
    assert shape(client, cid)[0] == "c"
    ids = [r["id"] for r in client.get("/api/export/legacy").get_json()["requests"]]
    assert ids.index("c") < ids.index("a")


def test_item_crud(client):
    cid = mk(client, BASE)
    r = client.post(f"/api/collections/{cid}/items", json={"parent_id": "f2", "index": 0,
                    "item": {"id": "n", "name": "N", "request": {"method": "GET", "url": {"raw": "u"}}}})
    assert r.status_code == 200 and shape(client, cid)[1] == ("f2", ["n", ("f3", [])])
    assert client.post(f"/api/collections/{cid}/items", json={"item": {"id": "n", "name": "dup"}}).status_code == 400
    client.patch(f"/api/collections/{cid}/items/n", json={"name": "N2", "id": "hack", "item": []})
    n = client.get(f"/api/collections/{cid}").get_json()["item"][1]["item"][0]
    assert n["name"] == "N2" and n["id"] == "n"
    client.delete(f"/api/collections/{cid}/items/n")
    assert shape(client, cid)[1] == ("f2", [("f3", [])])
    assert client.delete(f"/api/collections/{cid}/items/n").status_code == 400


def test_ui_state_roundtrip_and_survives_restart(isolated, make_client):
    c = make_client()
    state = {"tabs": [{"id": "t1", "kind": "request", "ref": "a"}], "active": "t1"}
    assert c.get("/api/ui-state").get_json() == {}
    c.put("/api/ui-state", json=state)
    c2 = make_client()                              # server qayta ishga tushdi
    assert c2.get("/api/ui-state").get_json() == state
    assert c2.put("/api/ui-state", json=[1]).status_code == 400


def test_history_add_delete_and_active_env(client):
    client.post("/api/history", json={"kind": "request", "payload": {"url": "u1"}})
    client.post("/api/history", json={"kind": "url", "payload": "http://a"})
    assert len(client.get("/api/history").get_json()) == 2
    assert client.post("/api/history", json={"kind": "x"}).status_code == 400
    hid = client.get("/api/history?kind=request").get_json()[0]["id"]
    client.delete(f"/api/history?id={hid}")
    assert client.get("/api/history?kind=request").get_json() == []
    client.delete("/api/history")
    assert client.get("/api/history").get_json() == []
    assert client.put("/api/workspace/meta", json={"active_environment_id": "e1", "evil": 1}).get_json()["meta"]["active_environment_id"] == "e1"
