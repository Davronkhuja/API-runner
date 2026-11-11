"""Postman collection (ichki model) -> run rejasi (engine spec'lari): CLI va rejalashtirilgan run'lar uchun.

Frontend (`web/src/lib/runs.ts buildPlan`) bilan bir xil qoidalar: meros auth, collection->papka->so'rov skriptlari tartibi, o'chirilgan qatorlar tushadi.
"""
import json
import os
from urllib.parse import quote

from ..storage import model

CFG_AUTH = {"apikey", "digest", "awsv4", "jwt", "hawk", "ntlm", "basic", "bearer"}
RAW_CT = {"html": "text/html", "javascript": "application/javascript", "xml": "application/xml", "text": ""}


def _rows(a):
    t = a.get("type")
    v = a.get(t)
    if isinstance(v, dict):
        return {k: str(x) for k, x in v.items()}
    return {r.get("key"): "" if r.get("value") is None else str(r.get("value")) for r in v or [] if isinstance(r, dict)}


def effective_auth(trail, req_auth):
    """Eng yaqin auth: so'rov -> papkalar (ichkaridan) -> collection. `noauth` to'xtatadi; auth yo'q = None."""
    for a in [req_auth] + list(reversed(trail)):
        if isinstance(a, dict) and a.get("type"):
            return None if a["type"] == "noauth" else a
    return None


def apply_auth(spec, auth, warnings, name):
    if not auth:
        return
    t = auth["type"]
    r = _rows(auth)
    if t in CFG_AUTH:
        spec["auth_config"] = {"type": t, **r}
    elif t == "x-custom":
        spec["authorization"] = r.get("value", "")
    elif t == "oauth2":
        tok = r.get("accessToken") or r.get("access_token")
        if tok:
            spec["authorization"] = f"{r.get('headerPrefix') or 'Bearer'} {tok}".strip()
        else:
            warnings.append(f"«{name}»: OAuth 2.0 tokeni CLI'da olinmaydi — Authorization sarlavhasini qo'lda bering")
    else:
        warnings.append(f"«{name}»: auth turi qo'llab-quvvatlanmaydi: {t}")


def _src(ev, kind, scope, name, id_):
    sc = ev.get("script") or {}
    ex = sc.get("exec")
    text = "\n".join(ex) if isinstance(ex, list) else (ex or "")
    return {"source": text, "kind": kind, "scope": scope, "name": name, "id": id_} if text.strip() else None


def scripts_for(col, trail_nodes, item):
    out = {"prerequest": [], "test": []}
    chain = [("collection", col["info"]["name"], model.collection_id(col), col)] + [("folder", f["name"], f["id"], f) for f in trail_nodes] + [("request", item["name"], item["id"], item)]
    for scope, name, id_, node in chain:
        for ev in node.get("event") or []:
            kind = {"prerequest": "prerequest", "test": "test"}.get(ev.get("listen"))
            s = _src(ev, kind, scope, name, id_) if kind else None
            if s:
                out["prerequest" if kind == "prerequest" else "test"].append(s)
    return out if out["prerequest"] or out["test"] else None


def build_spec(item, col, trail_nodes, warnings, base_dir=None, timeout=None, insecure=False):
    r = item.get("request") or {}
    url = r.get("url") if isinstance(r.get("url"), dict) else {"raw": str(r.get("url") or "")}
    raw = url.get("raw", "")
    base = raw.split("#")[0].split("?")[0]
    params = [{"name": q.get("key", ""), "value": q.get("value") or ""} for q in (url.get("query") or []) if isinstance(q, dict) and not q.get("disabled") and q.get("key")]
    if not params and "?" in raw:
        for part in raw.split("#")[0].split("?", 1)[1].split("&"):
            if part:
                k, _, v = part.partition("=")
                params.append({"name": k, "value": v})
    spec = {"method": (r.get("method") or "GET").upper(), "url": base, "params": params, "authorization": "", "body": "", "content_type": "", "body_type": "raw", "env_vars": {},
            "headers": [{"name": h["key"], "value": h.get("value") or ""} for h in r.get("header") or [] if isinstance(h, dict) and not h.get("disabled") and h.get("key")],
            "path_variables": [{"name": v["key"], "value": v.get("value") or ""} for v in url.get("variable") or [] if isinstance(v, dict) and v.get("key")]}
    if timeout:
        spec["timeout"] = timeout
    if insecure:
        spec["ssl_verify"] = False
    b = r.get("body") or {}
    mode = b.get("mode")
    if mode == "raw":
        lang = ((b.get("options") or {}).get("raw") or {}).get("language", "text")
        spec["body"], spec["body_type"] = b.get("raw", ""), "json" if lang == "json" else "raw"
        if lang != "json":
            spec["content_type"] = RAW_CT.get(lang, "")
    elif mode == "urlencoded":
        spec["body_type"] = "form"
        spec["body"] = "&".join(f"{quote(x.get('key', ''), safe='')}={quote(x.get('value') or '', safe='')}" for x in b.get("urlencoded") or [] if not x.get("disabled") and x.get("key"))
        spec["content_type"] = "application/x-www-form-urlencoded"
    elif mode == "formdata":
        spec["body_type"] = "multipart"
        fields = []
        for x in b.get("formdata") or []:
            if x.get("disabled") or not x.get("key"):
                continue
            if x.get("type") == "file":
                srcs = x.get("src") if isinstance(x.get("src"), list) else [x.get("src")] if x.get("src") else []
                files = []
                for sfile in srcs:
                    path = sfile if os.path.isabs(sfile) else os.path.join(base_dir or ".", sfile)
                    if os.path.isfile(path):
                        files.append({"path": os.path.abspath(path), "name": os.path.basename(path)})
                    else:
                        warnings.append(f"«{item['name']}»: fayl topilmadi: {sfile}")
                fields.append({"name": x["key"], "type": "file", "files": files})
            else:
                fields.append({"name": x["key"], "value": x.get("value") or ""})
        spec["multipart_fields"] = fields
    elif mode == "graphql":
        g = b.get("graphql") or {}
        payload = {"query": g.get("query", "")}
        if (g.get("variables") or "").strip():
            try:
                payload["variables"] = json.loads(g["variables"])
            except ValueError:
                warnings.append(f"«{item['name']}»: GraphQL variables JSON noto'g'ri")
        spec["body_type"], spec["body"] = "json", json.dumps(payload)
    elif mode == "file":
        src = (b.get("file") or {}).get("src")
        if src:
            path = src if os.path.isabs(src) else os.path.join(base_dir or ".", src)
            if os.path.isfile(path):
                spec["body_file"], spec["body_file_name"] = os.path.abspath(path), os.path.basename(path)
            else:
                warnings.append(f"«{item['name']}»: fayl topilmadi: {src}")
    apply_auth(spec, effective_auth([n.get("auth") for n in [col] + list(trail_nodes)], r.get("auth")), warnings, item["name"])
    return spec


def flatten(col, folder=None):
    """[(item, [ota papkalar])] — chuqurlik bo'yicha tartib. `folder` (nom yoki id) berilsa — faqat shu papka ichida."""
    out = []

    def walk(items, trail):
        for it in items:
            if model.is_folder(it):
                walk(it["item"], trail + [it])
            elif (it.get("x-apirunner") or {}).get("protocol"):
                continue                                              # WS/SSE — runner'da yo'q
            else:
                out.append((it, trail))
    if folder:
        found = []

        def find(items, trail):
            for it in items:
                if model.is_folder(it):
                    if it["name"] == folder or it["id"] == folder:
                        found.append((it, trail))
                    find(it["item"], trail + [it])
        find(col["item"], [])
        if not found:
            raise ValueError(f"Papka topilmadi: {folder}")
        node, trail = found[0]
        walk(node["item"], trail + [node])
    else:
        walk(col["item"], [])
    return out


def build_plan(col, folder=None, env_name="", base_dir=None, settings=None, rows=None, iterations=None, timeout=None, insecure=False):
    warnings = []
    cid = model.collection_id(col)
    items = []
    for it, trail in flatten(col, folder):
        spec = build_spec(it, col, trail, warnings, base_dir, timeout, insecure)
        items.append({"id": it["id"], "name": it["name"], "method": spec["method"], "ref": f"{cid}:{it['id']}", "spec": spec, "scripts": scripts_for(col, trail, it)})
    if not items:
        raise ValueError("Bajariladigan so'rov topilmadi")
    scope = cid + (f":{folder}" if folder else "")
    rows = rows or []
    return {"scope": scope, "scope_name": col["info"]["name"] + (f" / {folder}" if folder else ""), "kind": "cli", "env_name": env_name, "items": items, "rows": rows,
            "iterations": iterations or (len(rows) or 1), "settings": settings or {}}, warnings
