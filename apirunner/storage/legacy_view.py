"""workspace -> eski tekis format ({folders, requests}). Eski UI va orqaga qaytish eksporti shu yerdan."""
from . import model
from .migrate import LEGACY_COLLECTION_ID


def derive_legacy_request(item):
    """`x-apirunner.legacy` bo'lmagan (yangi UI yaratgan / import qilingan) so'rov uchun Postman maydonlaridan."""
    req = item.get("request") or {}
    url = req.get("url") or {}
    raw_url = url.get("raw", "") if isinstance(url, dict) else str(url)
    headers = [{"name": h.get("key", ""), "value": h.get("value", "")}
               for h in req.get("header", []) if not h.get("disabled")]
    params = [{"name": q.get("key", ""), "value": q.get("value", "")}
              for q in (url.get("query", []) if isinstance(url, dict) else []) if not q.get("disabled")]
    out = {"id": item["id"], "name": item.get("name", ""), "method": req.get("method", "GET"),
           "url": raw_url.split("?")[0], "headers": headers, "params": params,
           "body": "", "body_type": "raw", "content_type": "", "authorization": ""}
    body = req.get("body") or {}
    if body.get("mode") == "raw":
        out["body"] = body.get("raw", "")
        if body.get("options", {}).get("raw", {}).get("language") == "json":
            out["body_type"] = "json"
    elif body.get("mode") == "formdata":
        out["body_type"] = "multipart"
        out["multipart_fields"] = [{"name": f.get("key", ""), "value": f.get("value", "")}
                                   for f in body.get("formdata", []) if not f.get("disabled")]
    elif body.get("mode") == "urlencoded":
        out["body_type"] = "form"
        out["body"] = "&".join(f"{f.get('key','')}={f.get('value','')}" for f in body.get("urlencoded", []))
    auth = req.get("auth") or {}
    if auth.get("type") == "bearer":
        tok = next((x.get("value") for x in auth.get("bearer", []) if x.get("key") == "token"), "")
        out["authorization"] = "Bearer " + (tok or "")
    return out


def flat_view(col, is_primary=True):
    """Bitta collection'ning tekis ko'rinishi. Eski formatda papka 1 daraja — chuqurlari "A / B" nomi bilan tekislanadi."""
    folders, requests = [], []

    def walk(items, folder_id):
        for it in items:
            if model.is_folder(it):
                ext = it.get("x-apirunner", {})
                f = dict(ext.get("legacy") or {})
                f.update(id=it["id"], name=it["name"], expanded=ext.get("expanded", True))
                folders.append(f)
                walk(it["item"], it["id"])
            else:
                if it.get("x-apirunner", {}).get("legacy"):
                    requests.append(model.request_item_to_legacy(it, folder_id))
                else:
                    r = derive_legacy_request(it)
                    r["folder_id"] = folder_id
                    requests.append(r)

    walk(col["item"], None)
    return {"folders": folders, "requests": requests}


def export_workspace(ws):
    """Butun workspace'ni saved_requests.json formatiga aylantiradi (orqaga qaytish yo'li)."""
    out = {"folders": [], "requests": []}
    for meta in ws.list_collections():
        col = ws.get_collection(meta["id"])
        view = flat_view(col)
        if meta["id"] == LEGACY_COLLECTION_ID:
            out["folders"] += view["folders"]
            out["requests"] += view["requests"]
        else:                                        # boshqa collection -> bitta papka (ichidagilar tekislanadi)
            fid = "col-" + meta["id"]
            out["folders"].append({"id": fid, "name": col["info"]["name"], "expanded": True})
            for r in view["requests"]:
                r["folder_id"] = fid
                out["requests"].append(r)
    return out
