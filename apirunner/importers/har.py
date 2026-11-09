"""HAR 1.2 (brauzer DevTools "Save all as HAR") -> collection. Har yozuv — so'rov, javob — Example."""
import base64
import json
from urllib.parse import urlsplit

from ..storage import model
from .common import ImportErr

DROP_REQ = {"host", "content-length", "connection", "accept-encoding", "cookie", "upgrade-insecure-requests", "pragma", "cache-control"}
DROP_RESP = {"content-encoding", "content-length", "transfer-encoding", "connection"}


def looks_like_har(doc):
    return isinstance(doc, dict) and isinstance(doc.get("log"), dict) and isinstance(doc["log"].get("entries"), list)


def _name(method, url):
    p = urlsplit(url)
    return f"{method} {p.path or '/'}"[:90]


def _body(entry_req):
    pd = entry_req.get("postData")
    if not pd:
        return None
    mt = (pd.get("mimeType") or "").lower()
    if pd.get("params") and "form" in mt:
        key = "formdata" if "multipart" in mt else "urlencoded"
        rows = [{"key": p.get("name", ""), "value": p.get("value", ""), "type": "text"} if key == "formdata" else {"key": p.get("name", ""), "value": p.get("value", "")} for p in pd["params"]]
        return {"mode": key, key: rows}
    text = pd.get("text") or ""
    if not text:
        return None
    return {"mode": "raw", "raw": text, "options": {"raw": {"language": "json" if "json" in mt else "xml" if "xml" in mt else "text"}}}


def import_har(doc, warnings=None):
    warn = warnings if warnings is not None else []
    if not looks_like_har(doc):
        raise ImportErr("HAR emas (log.entries kerak)")
    log = doc["log"]
    entries = [e for e in log["entries"] if isinstance(e, dict) and isinstance(e.get("request"), dict) and e["request"].get("url")]
    if not entries:
        raise ImportErr("HAR'da so'rov yo'q")
    title = ((log.get("pages") or [{}])[0].get("title") or "").strip() or "HAR import"
    col = model.new_collection(title[:80])
    col["x-apirunner"]["source"] = {"kind": "har", "creator": (log.get("creator") or {}).get("name")}
    hosts = {urlsplit(e["request"]["url"]).netloc for e in entries}
    folders = {}
    dropped_cookies = False
    for e in entries:
        r = e["request"]
        url = r["url"]
        method = (r.get("method") or "GET").upper()
        headers = []
        for h in r.get("headers") or []:
            k = h.get("name", "")
            if k.startswith(":") or k.lower() in DROP_REQ:
                dropped_cookies = dropped_cookies or k.lower() == "cookie"
                continue
            headers.append({"key": k, "value": h.get("value", "")})
        req = {"method": method, "header": headers, "url": {"raw": url}}
        if r.get("queryString"):
            req["url"]["query"] = [{"key": q.get("name", ""), "value": q.get("value", "")} for q in r["queryString"]]
        body = _body(r)
        if body:
            req["body"] = body
        item = {"id": model.new_id(), "name": _name(method, url), "request": req, "response": []}
        resp = e.get("response") or {}
        if resp.get("status"):
            content = resp.get("content") or {}
            text = content.get("text") or ""
            if content.get("encoding") == "base64" and text:
                try:
                    text = base64.b64decode(text).decode("utf-8")
                except (ValueError, UnicodeDecodeError):
                    text = ""
            mt = (content.get("mimeType") or "").lower()
            item["response"].append({"id": "ex" + model.new_id()[:12], "name": f"{resp['status']} {resp.get('statusText', '')}".strip(), "originalRequest": json.loads(json.dumps(req)),
                                     "status": resp.get("statusText") or str(resp["status"]), "code": int(resp["status"]),
                                     "header": [{"key": h["name"], "value": h.get("value", "")} for h in resp.get("headers") or [] if h.get("name") and not h["name"].startswith(":") and h["name"].lower() not in DROP_RESP],
                                     "body": text, "_postman_previewlanguage": "json" if "json" in mt else "html" if "html" in mt else "text"})
        if len(hosts) > 1:
            host = urlsplit(url).netloc
            if host not in folders:
                folders[host] = model.new_folder(host)
                col["item"].append(folders[host])
            folders[host]["item"].append(item)
        else:
            col["item"].append(item)
    if dropped_cookies:
        warn.append("Cookie sarlavhalari (maxfiy bo'lishi mumkin) import qilinmadi")
    return col
