"""Manba (matn/zip) -> `Parsed`: format aniqlanadi va mos importer chaqiriladi. Bitta manba bir nechta narsa berishi mumkin."""
import base64

from ..exporters import workspace as wsexp
from ..storage import model
from .common import ImportErr, detect, is_curl, parse_structured, stats
from .curl import import_curl
from .har import import_har
from .insomnia import import_insomnia
from .openapi import import_openapi
from .postman import import_postman, import_postman_env, import_postman_globals

KIND_LABEL = {"postman": "Postman Collection", "postman-env": "Postman Environment", "postman-globals": "Postman Globals", "openapi": "OpenAPI", "insomnia": "Insomnia", "har": "HAR", "curl": "cURL", "workspace": "API Runner workspace"}


def parse_source(content, name="", encoding=None):
    """-> {kind, label, collections[], environments[], globals: [rows]|None, files{}, warnings[]}. Xato — ImportErr."""
    warn = []
    out = {"kind": None, "collections": [], "environments": [], "globals": None, "files": {}, "warnings": warn}
    if encoding == "base64" or (isinstance(name, str) and name.lower().endswith(".zip") and encoding != "text"):
        try:
            data = base64.b64decode(content) if isinstance(content, str) else content
            z = wsexp.read_zip(data)
        except ValueError as e:
            raise ImportErr(str(e)) from e
        out.update(kind="workspace", collections=z["collections"], environments=z["environments"], files=z["files"], zip_manifest=z["manifest"])
        if z["globals"]:
            out["globals"] = [v for v in z["globals"].get("values", []) if v.get("key")]
        for c in out["collections"]:                                           # o'z formatimiz: yagonalashtirish uchun import yo'lidan o'tmaydi, id'lar saqlanadi
            c.setdefault("x-apirunner", {})
    elif isinstance(content, str) and is_curl(content):
        out.update(kind="curl", collections=[import_curl(content, warn)])
    else:
        doc = parse_structured(content)
        kind = detect(doc)
        if kind is None:
            if isinstance(doc, dict) and str(doc.get("type", "")).startswith("collection.insomnia"):
                raise ImportErr("Insomnia v5 formati qo'llab-quvvatlanmaydi — Insomnia'da «Export → Insomnia v4 (JSON)» ni tanlang")
            raise ImportErr("Format tanilmadi. Qo'llab-quvvatlanadi: Postman collection/environment/globals, OpenAPI 3.x/Swagger 2.0 (JSON/YAML), Insomnia v4, HAR, cURL")
        out["kind"] = kind
        if kind == "postman":
            out["collections"] = [import_postman(doc, warn)]
        elif kind == "postman-env":
            out["environments"] = [import_postman_env(doc)]
        elif kind == "postman-globals":
            out["globals"] = import_postman_globals(doc)
        elif kind == "openapi":
            out["collections"] = [import_openapi(doc, warn)]
        elif kind == "har":
            out["collections"] = [import_har(doc, warn)]
        elif kind == "insomnia":
            out["collections"], out["environments"] = import_insomnia(doc, warn)
    out["label"] = KIND_LABEL.get(out["kind"], out["kind"])
    return out


def items_of(parsed):
    """Ko'rsatish/qo'llash uchun yassi ro'yxat: [{type, name, stats, ref}] (ref = parsed ichidagi obyekt)."""
    items = []
    for c in parsed["collections"]:
        items.append({"type": "collection", "name": c["info"]["name"], "stats": stats(c), "ref": c})
    for e in parsed["environments"]:
        items.append({"type": "environment", "name": e.get("name", ""), "stats": {"variables": len(e.get("values") or [])}, "ref": e})
    if parsed["globals"] is not None:
        items.append({"type": "globals", "name": "Globals", "stats": {"variables": len(parsed["globals"])}, "ref": parsed["globals"]})
    return items


__all__ = ["parse_source", "items_of", "ImportErr", "model"]
