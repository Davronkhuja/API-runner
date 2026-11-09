"""cURL buyruqlari (bir yoki bir nechta, bash `\\` davomi, `$'..'` bilan) -> collection."""
import json
import re
from urllib.parse import quote, urlsplit

from ..storage import model
from .common import ImportErr

NO_ARG = {"-s", "--silent", "-S", "--show-error", "-v", "--verbose", "-i", "--include", "-k", "--insecure", "-L", "--location", "--compressed", "-f", "--fail", "-g", "--globoff", "--http1.1", "--http2",
          "--http1.0", "-N", "--no-buffer", "-#", "--progress-bar", "-O", "--remote-name", "-J", "--remote-header-name", "--tcp-nodelay", "-q", "--disable", "--path-as-is", "-Z", "--parallel", "--no-keepalive"}
WITH_ARG_IGNORED = {"-o", "--output", "-m", "--max-time", "--connect-timeout", "-x", "--proxy", "--cert", "--key", "--cacert", "-w", "--write-out", "--retry", "-T", "--upload-file", "--resolve", "--interface",
                    "--limit-rate", "-c", "--cookie-jar", "--proxy-user", "-E", "--capath", "--max-redirs", "--retry-delay", "-K", "--config", "--dns-servers", "--user-agent-ignored"}
ANSI = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b", "e": "\x1b", "f": "\f", "v": "\v"}


def looks_like_curl(text):
    return isinstance(text, str) and bool(re.match(r"^\s*(\$\s*)?curl\b", text, re.I))


def tokenize(text):
    """Buyruqlar ro'yxati (har biri — token ro'yxati). Yangi qator (davomsiz) va `;` buyruqni tugatadi."""
    text = re.sub(r"\\\r?\n", " ", text)
    cmds, cur, tok, has, i, n = [], [], [], False, 0, len(text)

    def end_tok():
        nonlocal tok, has
        if has:
            cur.append("".join(tok))
        tok, has = [], False

    def end_cmd():
        nonlocal cur
        end_tok()
        if cur:
            cmds.append(cur)
        cur = []

    while i < n:
        c = text[i]
        if c in " \t":
            end_tok(); i += 1
        elif c in "\r\n;":
            end_cmd(); i += 1
        elif c == "#" and not has and not tok:
            while i < n and text[i] != "\n":
                i += 1
        elif c == "$" and text[i + 1:i + 2] == "'":
            i += 2; has = True
            while i < n and text[i] != "'":
                if text[i] == "\\" and i + 1 < n:
                    nx = text[i + 1]
                    if nx == "x" and re.match(r"[0-9a-fA-F]{1,2}", text[i + 2:i + 4]):
                        h = re.match(r"[0-9a-fA-F]{1,2}", text[i + 2:i + 4]).group(0)
                        tok.append(chr(int(h, 16))); i += 2 + len(h)
                    elif nx == "u" and re.match(r"[0-9a-fA-F]{4}", text[i + 2:i + 6]):
                        tok.append(chr(int(text[i + 2:i + 6], 16))); i += 6
                    else:
                        tok.append(ANSI.get(nx, nx)); i += 2
                else:
                    tok.append(text[i]); i += 1
            i += 1
        elif c == "'":
            i += 1; has = True
            while i < n and text[i] != "'":
                tok.append(text[i]); i += 1
            i += 1
        elif c == '"':
            i += 1; has = True
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n and text[i + 1] in '"\\$`':
                    tok.append(text[i + 1]); i += 2
                else:
                    tok.append(text[i]); i += 1
            i += 1
        elif c == "\\" and i + 1 < n:
            tok.append(text[i + 1]); has = True; i += 2
        else:
            tok.append(c); has = True; i += 1
    end_cmd()
    return cmds


def parse_command(tokens):
    """Bitta `curl ...` -> {method, url, headers[(k,v)], data[list], form[list], user, ...}."""
    toks = list(tokens)
    if toks and toks[0] == "$":
        toks.pop(0)
    if not toks or toks[0] != "curl":
        raise ImportErr("cURL buyrug'i `curl` bilan boshlanishi kerak")
    toks = toks[1:]
    o = {"method": None, "url": None, "headers": [], "data": [], "urlencode": [], "form": [], "user": None, "get": False, "head": False, "json": False, "insecure": False}
    i = 0

    def val():
        nonlocal i
        i += 1
        if i >= len(toks):
            raise ImportErr(f"`{toks[i - 1]}` uchun qiymat yo'q")
        return toks[i]
    while i < len(toks):
        t = toks[i]
        if t.startswith("--") and "=" in t and t.split("=", 1)[0] not in NO_ARG:
            t, v = t.split("=", 1)
            toks[i:i + 1] = [t, v]
        if t in ("-X", "--request"):
            o["method"] = val().upper()
        elif t in ("-H", "--header"):
            h = val()
            k, _, v = h.partition(":")
            if _:
                o["headers"].append((k.strip(), v.strip()))
        elif t in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii"):
            o["data"].append(val())
        elif t == "--data-urlencode":
            o["urlencode"].append(val())
        elif t == "--json":
            o["json"] = True
            o["data"].append(val())
        elif t in ("-F", "--form", "--form-string"):
            o["form"].append(val())
        elif t in ("-u", "--user"):
            o["user"] = val()
        elif t in ("-A", "--user-agent"):
            o["headers"].append(("User-Agent", val()))
        elif t in ("-e", "--referer"):
            o["headers"].append(("Referer", val()))
        elif t in ("-b", "--cookie"):
            o["headers"].append(("Cookie", val()))
        elif t in ("-I", "--head"):
            o["head"] = True
        elif t in ("-G", "--get"):
            o["get"] = True
        elif t == "--url":
            o["url"] = val()
        elif t in ("-k", "--insecure"):
            o["insecure"] = True
        elif t in WITH_ARG_IGNORED:
            val()
        elif t in NO_ARG:
            pass
        elif t.startswith("-") and len(t) > 2 and not t.startswith("--") and t[:2] in ("-X", "-H", "-d", "-F", "-u", "-A", "-e", "-b"):
            toks[i:i + 1] = [t[:2], t[2:]]                                             # -XPOST, -H'A: b' kabi yopishgan qiymat
            continue
        elif t.startswith("--"):
            pass                                                                       # noma'lum flag: e'tiborsiz (xavfsiz)
        elif not t.startswith("-"):
            o["url"] = o["url"] or t
        i += 1
    if not o["url"]:
        raise ImportErr("cURL buyrug'ida URL yo'q")
    return o


def _name(method, url):
    p = urlsplit(url if "://" in url else "http://" + url)
    return f"{method} {p.netloc}{p.path or '/'}"[:90] if p.netloc else f"{method} {url}"[:90]


def to_item(o):
    url = o["url"]
    method = o["method"] or ("HEAD" if o["head"] else "POST" if (o["data"] or o["urlencode"] or o["form"] or o["json"]) and not o["get"] else "GET")
    headers = list(o["headers"])
    if o["json"]:
        if not any(k.lower() == "content-type" for k, _ in headers):
            headers.append(("Content-Type", "application/json"))
        if not any(k.lower() == "accept" for k, _ in headers):
            headers.append(("Accept", "application/json"))
    ctype = next((v for k, v in headers if k.lower() == "content-type"), "").lower()
    body = None
    payload = "&".join(o["data"])
    for u in o["urlencode"]:
        k, sep, v = u.partition("=")
        payload += ("&" if payload else "") + (f"{k}={quote(v, safe='')}" if sep else quote(k, safe=""))
    if o["get"] and payload:
        url += ("&" if "?" in url else "?") + payload
        payload = ""
    if o["form"]:
        rows = []
        for f in o["form"]:
            k, _, v = f.partition("=")
            rows.append({"key": k, "type": "file", "src": []} if v.startswith("@") else {"key": k, "value": v, "type": "text"})
        body = {"mode": "formdata", "formdata": rows}
    elif payload:
        looks_json = payload.lstrip()[:1] in "{["
        if "json" in ctype or (not ctype and looks_json) or o["json"]:
            body = {"mode": "raw", "raw": payload, "options": {"raw": {"language": "json"}}}
        elif "x-www-form-urlencoded" in ctype or (not ctype and re.match(r"^[^=&\s]+=", payload)):
            from urllib.parse import unquote_plus
            body = {"mode": "urlencoded", "urlencoded": [{"key": unquote_plus(k), "value": unquote_plus(v)} for k, _, v in (p.partition("=") for p in payload.split("&") if p)]}
        else:
            body = {"mode": "raw", "raw": payload, "options": {"raw": {"language": "text"}}}
    req = {"method": method, "header": [{"key": k, "value": v} for k, v in headers], "url": {"raw": url}}
    if "?" in url:
        req["url"]["query"] = [{"key": k, "value": v} for k, _, v in (q.partition("=") for q in url.split("?", 1)[1].split("#")[0].split("&") if q)]
    if body:
        req["body"] = body
    if o["user"]:
        u, _, p = o["user"].partition(":")
        req["auth"] = {"type": "basic", "basic": [{"key": "username", "value": u, "type": "string"}, {"key": "password", "value": p, "type": "string"}]}
    return {"id": model.new_id(), "name": _name(method, url), "request": req, "response": []}


def import_curl(text, warnings=None):
    warn = warnings if warnings is not None else []
    cmds = [c for c in tokenize(text) if c and c[0] in ("curl", "$")]
    if not cmds:
        raise ImportErr("cURL buyrug'i topilmadi")
    col = model.new_collection("cURL import")
    col["x-apirunner"]["source"] = {"kind": "curl"}
    for n, c in enumerate(cmds, 1):
        try:
            col["item"].append(to_item(parse_command(c)))
        except ImportErr as e:
            warn.append(f"{n}-buyruq o'tkazib yuborildi: {e}")
    if not col["item"]:
        raise ImportErr(warn[0] if warn else "cURL buyrug'i topilmadi")
    return col
