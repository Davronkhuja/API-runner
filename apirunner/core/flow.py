"""Kolleksiya oqimi (Postman Runner semantikasi): tartib bilan bajarish, iteratsiyalar (data qatorlari), `setNextRequest`, skriptlar.

UI Runner (web/src/components/RunnerTab.vue) xuddi shu qoidalarni TypeScript'da takrorlaydi; bu modul CLI (Bosqich 7) va
muvofiqlik testlari uchun server tomonidagi yagona manba.
"""
import base64
import json
from urllib.parse import parse_qsl, unquote

from .scripted import Services, run_item, scripts_chain


def flatten(items, folders=()):
    """Daraxt → [(so'rov, [ota papkalar tashqaridan ichkariga])] (chuqurlik bo'yicha, ko'rsatilgan tartibda)."""
    out = []
    for it in items:
        if "item" in it:
            out += flatten(it["item"], folders + (it,))
        else:
            out.append((it, list(folders)))
    return out


def _auth_spec(auth, spec):
    if not auth:
        return
    def f(kind, key):
        return next((x.get("value") for x in auth.get(kind, []) if x.get("key") == key), "")
    t = auth.get("type")
    if t == "bearer":
        spec["authorization"] = "Bearer " + str(f("bearer", "token"))
    elif t == "basic":
        spec["authorization"] = "Basic " + base64.b64encode(("%s:%s" % (f("basic", "username"), f("basic", "password"))).encode()).decode()
    elif t == "apikey":
        key, val = f("apikey", "key"), str(f("apikey", "value"))
        if f("apikey", "in") == "query":
            spec["params"].append({"name": key, "value": val})
        else:
            spec["headers"].append({"name": key, "value": val})


def item_to_spec(item, col, folders):
    """Postman so'rovi → engine spec (shablonlar `{{}}` yechilmagan holda). Auth merosi: so'rov → papka → collection."""
    r = item["request"]
    url = r.get("url") or {}
    raw = url if isinstance(url, str) else url.get("raw", "")
    base, _, qs = raw.partition("?")
    if isinstance(url, dict) and url.get("query"):
        params = [{"name": q["key"], "value": q.get("value") or ""} for q in url["query"] if not q.get("disabled")]
    else:
        params = [{"name": unquote(k), "value": unquote(v)} for k, v in parse_qsl(qs, keep_blank_values=True)]
    spec = {"method": (r.get("method") or "GET").upper(), "url": base, "params": params,
            "headers": [{"name": h["key"], "value": h.get("value", "")} for h in r.get("header") or [] if h.get("key") and not h.get("disabled")]}
    body = r.get("body") or {}
    if body.get("mode") == "raw":
        spec["body"] = body.get("raw", "")
        if (body.get("options") or {}).get("raw", {}).get("language") == "json":
            spec["body_type"] = "json"
    elif body.get("mode") == "urlencoded":
        from urllib.parse import quote
        spec["body"] = "&".join("%s=%s" % (quote(x["key"]), quote(str(x.get("value", "")))) for x in body.get("urlencoded") or [] if not x.get("disabled"))
        spec["body_type"], spec["content_type"] = "form", "application/x-www-form-urlencoded"
    elif body.get("mode") == "formdata":
        spec["body_type"] = "multipart"
        spec["multipart_fields"] = [{"name": x["key"], "value": str(x.get("value", ""))} for x in body.get("formdata") or [] if not x.get("disabled") and x.get("type", "text") == "text"]
    chain = [r.get("auth")] + [f.get("auth") for f in reversed(folders)] + [col.get("auth")]
    for a in chain:
        if a:
            if a.get("type") != "noauth":
                _auth_spec(a, spec)
            break
    return spec


def run_collection(services, cid, iterations=None, rows=None, spec_hook=None, max_steps=1000, on_step=None):
    """Kolleksiyani Postman Runner kabi bajaradi. Qaytaradi: [{iteration, name, id, result}].

    `setNextRequest(name)` — shu nomli birinchi so'rovga o'tadi (keyingi iteratsiyaga emas); `setNextRequest(null)` — butun run to'xtaydi.
    """
    ws = services.ws
    col = ws.get_collection(cid)
    flat = flatten(col["item"])
    names = {}
    for idx, (it, _f) in enumerate(flat):
        names.setdefault(it["name"], idx)
    rows = rows or [{}]
    total_iter = iterations or len(rows)
    steps, log, stop = 0, [], False
    for it_no in range(total_iter):
        row = rows[it_no % len(rows)]
        i = 0
        while i < len(flat) and not stop:
            steps += 1
            if steps > max_steps:
                log.append({"iteration": it_no, "name": "", "id": "", "result": None, "error": "max_steps (%d) oshdi" % max_steps})
                return log
            item, folders = flat[i]
            spec = item_to_spec(item, col, folders)
            if spec_hook:
                spec = spec_hook(spec)
            res = run_item(spec, services, scripts=scripts_chain(col, item["id"]), ref="%s:%s" % (cid, item["id"]), row=row,
                           info={"iteration": it_no, "iterationCount": total_iter, "requestName": item["name"], "requestId": item["id"]})
            step = {"iteration": it_no, "name": item["name"], "id": item["id"], "result": res}
            log.append(step)
            if on_step:
                on_step(step)
            s = res.get("scripts") or {}
            if s.get("next_set"):
                nxt = s.get("next_request")
                if nxt is None:
                    stop = True
                    break
                if nxt not in names:
                    log.append({"iteration": it_no, "name": nxt, "id": "", "result": None, "error": "setNextRequest: '%s' nomli so'rov topilmadi" % nxt})
                    return log
                i = names[nxt]
                continue
            i += 1
        if stop:
            break
    return log
