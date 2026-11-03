"""Collection daraxti ustida operatsiyalar. Tartib = `item[]` massivi tartibi (Postman v2.1 ham shunday
saqlaydi), shuning uchun eksportda tartib o'z-o'zidan saqlanadi. Hamma operatsiya atomik (workspace lock ostida)."""
import copy

from . import model


class TreeError(ValueError):
    pass


def find(items, item_id, parent=None):
    """(node, ota ro'yxat, ota node|None) yoki None."""
    for it in items:
        if it.get("id") == item_id:
            return it, items, parent
        if model.is_folder(it):
            hit = find(it["item"], item_id, it)
            if hit:
                return hit
    return None


def contains(node, item_id):
    """`node` (papka) ichida (o'zini ham hisobga olib) item_id bormi."""
    if node.get("id") == item_id:
        return True
    return model.is_folder(node) and any(contains(c, item_id) for c in node["item"])


def clone_with_new_ids(node):
    n = copy.deepcopy(node)

    def walk(x):
        x["id"] = model.new_id()
        if "x-apirunner" in x and isinstance(x["x-apirunner"].get("legacy"), dict):
            x["x-apirunner"]["legacy"] = {**x["x-apirunner"]["legacy"], "id": x["id"]}
        for c in x.get("item", []):
            walk(c)
    walk(n)
    return n


def add_item(col, parent_id, item, index=None):
    if parent_id:
        hit = find(col["item"], parent_id)
        if not hit or not model.is_folder(hit[0]):
            raise TreeError("Ota papka topilmadi")
        target = hit[0]["item"]
    else:
        target = col["item"]
    item.setdefault("id", model.new_id())
    if find(col["item"], item["id"]):
        raise TreeError("Bu id band")
    target.insert(len(target) if index is None else max(0, min(index, len(target))), item)
    return item["id"]


def update_item(col, item_id, patch):
    hit = find(col["item"], item_id)
    if not hit:
        raise TreeError("Element topilmadi")
    node = hit[0]
    for k, v in patch.items():
        if k in ("id", "item"):
            continue                      # id va bolalar faqat move/add orqali
        node[k] = v
    return node


def delete_item(col, item_id):
    hit = find(col["item"], item_id)
    if not hit:
        raise TreeError("Element topilmadi")
    hit[1].remove(hit[0])
    return hit[0]


def move(ws, src_cid, ids, dst_cid, target_id, position, copy_items=False):
    """`ids` ni (tartibini saqlab) `target_id` ga nisbatan before|after|inside joylaydi.

    target_id None + inside  -> dst collection ildizining oxiriga.
    Qaytaradi: {eski_id: yangi_id} (ko'chirishda id o'zgarmaydi; nusxada yangi).
    Xatolar: papkani o'z ichiga/avlodiga, target o'zi bo'lsa, inside faqat papkaga.
    """
    if position not in ("before", "after", "inside"):
        raise TreeError("position noto'g'ri")
    if not ids or len(set(ids)) != len(ids):
        raise TreeError("ids bo'sh yoki takror")
    with ws.lock:
        src = ws.get_collection(src_cid)
        dst = src if dst_cid == src_cid else ws.get_collection(dst_cid)
        nodes = []
        for i in ids:
            hit = find(src["item"], i)
            if not hit:
                raise TreeError(f"Element topilmadi: {i}")
            nodes.append(hit[0])
        # bola tanlangan papka ichida bo'lsa — ota bilan birga ko'chadi, alohida emas
        top = [n for n in nodes if not any(m is not n and model.is_folder(m) and contains(m, n["id"]) for m in nodes)]
        t_hit = None
        if target_id:
            t_hit = find(dst["item"], target_id)
            if not t_hit:
                raise TreeError("Target topilmadi")
            if position == "inside" and not model.is_folder(t_hit[0]):
                raise TreeError("Ichiga faqat papka")
            for n in top:
                if model.is_folder(n) and contains(n, target_id) and dst is src:
                    raise TreeError("Papkani o'z ichiga ko'chirib bo'lmaydi")
        elif position != "inside":
            raise TreeError("before/after uchun target kerak")

        payload, mapping = [], {}
        for n in top:
            if copy_items:
                c = clone_with_new_ids(n)
                mapping[n["id"]] = c["id"]
                payload.append(c)
            else:
                mapping[n["id"]] = n["id"]
                payload.append(n)
        if not copy_items:                       # manbadan olib tashlash
            for n in top:
                find(src["item"], n["id"])[1].remove(n)
        # target joyi (olib tashlagandan keyin qayta topiladi)
        if not target_id:
            dst["item"].extend(payload)
        else:
            t_node, t_list, _ = find(dst["item"], target_id)
            if position == "inside":
                t_node["item"].extend(payload)
                t_node.setdefault("x-apirunner", {})["expanded"] = True
            else:
                at = t_list.index(t_node) + (1 if position == "after" else 0)
                t_list[at:at] = payload
        ws.save_collection(src)
        if dst is not src:
            ws.save_collection(dst)
        return mapping
