"""OpenAPI 3.x / Swagger 2.0 (JSON) -> collection. Birinchi tag bo'yicha papkalar."""
from ..storage import model

METHODS = ("get", "put", "post", "delete", "patch", "head", "options")


def looks_like_openapi(doc):
    return isinstance(doc, dict) and ("openapi" in doc or "swagger" in doc) and isinstance(doc.get("paths"), dict)


def _base_url(doc):
    if doc.get("servers"):
        return doc["servers"][0].get("url", "").rstrip("/")
    if doc.get("host"):
        scheme = (doc.get("schemes") or ["https"])[0]
        return f"{scheme}://{doc['host']}{doc.get('basePath', '')}".rstrip("/")
    return ""


def import_openapi(doc):
    title = doc.get("info", {}).get("title") or "OpenAPI"
    col = model.new_collection(title)
    base = _base_url(doc)
    folders = {}
    for path, ops in doc["paths"].items():
        if not isinstance(ops, dict):
            continue
        for m in METHODS:
            op = ops.get(m)
            if not isinstance(op, dict):
                continue
            params = [p for p in (ops.get("parameters", []) + op.get("parameters", [])) if isinstance(p, dict)]
            query = [{"key": p["name"], "value": "", "disabled": not p.get("required", False)} for p in params if p.get("in") == "query"]
            headers = [{"key": p["name"], "value": ""} for p in params if p.get("in") == "header"]
            req = {"method": m.upper(), "header": headers,
                   "url": {"raw": base + path, "query": query},
                   "description": op.get("description", "")}
            if "requestBody" in op and "application/json" in op["requestBody"].get("content", {}):
                req["body"] = {"mode": "raw", "raw": "{}", "options": {"raw": {"language": "json"}}}
            item = {"id": model.new_id(), "name": op.get("summary") or f"{m.upper()} {path}", "request": req, "response": []}
            tags = op.get("tags") or []
            if tags:
                if tags[0] not in folders:
                    folders[tags[0]] = model.new_folder(tags[0])
                    col["item"].append(folders[tags[0]])
                folders[tags[0]]["item"].append(item)
            else:
                col["item"].append(item)
    return col
