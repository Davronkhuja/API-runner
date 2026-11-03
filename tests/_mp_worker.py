"""Ko'p jarayonli testlar uchun yengil ishchi (spawn bilan import qilinadi; pytest/Playwright'ga bog'liq emas)."""
from apirunner.storage import tree_ops
from apirunner.storage.workspace import Workspace


def adds(root, cid, tag, n):
    ws = Workspace(root)
    for i in range(n):
        with ws.lock:
            col = ws.get_collection(cid)
            tree_ops.add_item(col, None, {"id": f"{tag}-{i}", "name": f"{tag}{i}",
                                          "request": {"method": "GET", "url": {"raw": "u"}}, "response": []})
            ws.save_collection(col)
