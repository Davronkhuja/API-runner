"""Postman Collection v2.0/v2.1 -> ichki model (v2.1 superseti, shuning uchun deyarli o'zgarishsiz).

Saqlanadi: ichma-ich papkalar, auth, event (skriptlar), variable, description, response (Examples).
Faqat normallashtiriladi: url satr -> {raw}, id'lar to'ldiriladi/yagona qilinadi.
"""
import copy

from ..storage import model


def looks_like_postman(doc):
    return isinstance(doc, dict) and isinstance(doc.get("item"), list) and isinstance(doc.get("info"), dict) \
        and "postman" in str(doc["info"].get("schema", "")).lower() or (
            isinstance(doc, dict) and isinstance(doc.get("item"), list) and "info" in doc and "openapi" not in doc)


def _norm_request(req):
    if isinstance(req, str):                       # v2.0: "request": "http://..."
        return {"method": "GET", "header": [], "url": {"raw": req}}
    r = copy.deepcopy(req)
    url = r.get("url")
    if isinstance(url, str):
        r["url"] = {"raw": url}
    elif url is None:
        r["url"] = {"raw": ""}
    elif "raw" not in url:
        host = ".".join(url.get("host", [])) if isinstance(url.get("host"), list) else url.get("host", "")
        path = "/".join(url.get("path", [])) if isinstance(url.get("path"), list) else url.get("path", "")
        r["url"]["raw"] = (f"{url.get('protocol', 'http')}://" if host else "") + host + ("/" + path if path else "")
    r.setdefault("method", "GET")
    r.setdefault("header", [])
    return r


def _walk(items, seen):
    out = []
    for it in items:
        n = copy.deepcopy(it)
        i = n.get("id")
        if not i or i in seen:
            i = model.new_id()
        seen.add(i)
        n["id"] = i
        n.setdefault("name", "")
        if "item" in n:
            n["item"] = _walk(n["item"], seen)
        else:
            n["request"] = _norm_request(n.get("request", {}))
            n.setdefault("response", [])
        out.append(n)
    return out


def import_postman(doc):
    info = doc.get("info", {})
    col = model.new_collection(info.get("name") or "Import")
    for k in ("auth", "variable", "event"):
        if doc.get(k) is not None:
            col[k] = copy.deepcopy(doc[k])
    if info.get("description"):
        col["x-apirunner"]["description"] = info["description"] if isinstance(info["description"], str) else info["description"].get("content", "")
    col["item"] = _walk(doc.get("item", []), set())
    return col
