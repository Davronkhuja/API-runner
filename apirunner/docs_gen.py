"""Collection/papkadan statik HTML hujjat: tavsiflar (Markdown), so'rovlar, parametrlar, body, auth va Example'lar. Bitta fayl, tashqi resurssiz."""
import html
import json
import re
import time

from .storage import model

E = html.escape


# ── xavfsiz Markdown -> HTML (web/src/lib/markdown.ts bilan bir xil qoidalar) ──
def _safe_url(u):
    t = u.strip()
    return t if re.match(r"^(https?://|mailto:)", t, re.I) and not re.search(r'[\s<>"]', t) else None


def _inline(src):
    codes = []

    def keep(m):
        codes.append(f"<code>{m.group(1)}</code>")
        return f"\0{len(codes) - 1}\0"
    s = re.sub(r"`([^`\n]+)`", keep, E(src))

    def link(m):
        u = _safe_url(m.group(2).replace("&amp;", "&"))
        return f'<a href="{E(u)}" target="_blank" rel="noopener noreferrer">{m.group(1)}</a>' if u else m.group(0)
    s = re.sub(r"\[([^\]\n]+)\]\(([^)\s]+)\)", link, s)
    s = re.sub(r"\*\*([^*\n]+)\*\*|__([^_\n]+)__", lambda m: f"<strong>{m.group(1) or m.group(2)}</strong>", s)
    s = re.sub(r"(^|[^*\w])\*([^*\n]+)\*(?!\w)", r"\1<em>\2</em>", s)
    s = re.sub(r"~~([^~\n]+)~~", r"<del>\1</del>", s)
    return re.sub(r"\0(\d+)\0", lambda m: codes[int(m.group(1))], s)


def md(text):
    lines = (text or "").replace("\0", "").replace("\r\n", "\n").split("\n")      # NUL — ichki o'rinbosar belgi: kiritishdan olib tashlanadi
    out, i = [], 0
    special = re.compile(r"^(#{1,6}\s|```|>\s?|\s*([-*+]|\d+\.)\s+|\s*(-{3,}|\*{3,})\s*$)")
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        f = re.match(r"^```(\w*)\s*$", ln)
        if f:
            buf = []
            i += 1
            while i < len(lines) and not re.match(r"^```\s*$", lines[i]):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(f"<pre><code>{E(chr(10).join(buf))}</code></pre>")
            continue
        h = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", ln)
        if h:
            n = min(6, len(h.group(1)) + 2)                               # sahifa h1/h2 band: kontent sarlavhalari h3+
            out.append(f"<h{n}>{_inline(h.group(2))}</h{n}>")
            i += 1
            continue
        if re.match(r"^\s*(-{3,}|\*{3,})\s*$", ln):
            out.append("<hr>")
            i += 1
            continue
        if re.match(r"^>\s?", ln):
            buf = []
            while i < len(lines) and re.match(r"^>\s?", lines[i]):
                buf.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{md(chr(10).join(buf))}</blockquote>")
            continue
        ul, ol = re.match(r"^\s*[-*+]\s+", ln), re.match(r"^\s*\d+\.\s+", ln)
        if ul or ol:
            rx = re.compile(r"^\s*[-*+]\s+(.*)$" if ul else r"^\s*\d+\.\s+(.*)$")
            items = []
            while i < len(lines) and rx.match(lines[i]):
                items.append(f"<li>{_inline(rx.match(lines[i]).group(1))}</li>")
                i += 1
            out.append(f"<{'ul' if ul else 'ol'}>{''.join(items)}</{'ul' if ul else 'ol'}>")
            continue
        buf = []
        while i < len(lines) and lines[i].strip() and (not buf or not special.match(lines[i])):
            buf.append(lines[i])
            i += 1
        out.append("<p>" + "<br>".join(_inline(b) for b in buf) + "</p>")
    return "".join(out)


# ── hujjat ──
def _slug(s, used):
    base = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "item"
    n, out = 1, base
    while out in used:
        n += 1
        out = f"{base}-{n}"
    used.add(out)
    return out


def _url_raw(r):
    u = r.get("url")
    return u.get("raw", "") if isinstance(u, dict) else str(u or "")


def _text(d):
    return d if isinstance(d, str) else (d or {}).get("content", "") if isinstance(d, dict) else ""


def _kv_table(rows, head=("Nomi", "Qiymat", "Tavsif")):
    rows = [r for r in rows or [] if isinstance(r, dict) and r.get("key")]
    if not rows:
        return ""
    body = "".join(f"<tr><td><code>{E(r['key'])}</code></td><td><code>{E(str(r.get('value') or ''))}</code></td><td>{_inline(_text(r.get('description')))}{' <span class=\"tag\">o\'chirilgan</span>' if r.get('disabled') else ''}</td></tr>" for r in rows)
    return f"<table><thead><tr>{''.join(f'<th>{h}</th>' for h in head)}</tr></thead><tbody>{body}</tbody></table>"


def _auth_text(a):
    if not isinstance(a, dict) or not a.get("type"):
        return ""
    t = {"noauth": "Auth yo'q", "bearer": "Bearer Token", "basic": "Basic Auth", "apikey": "API Key", "oauth2": "OAuth 2.0", "digest": "Digest", "awsv4": "AWS Signature V4", "jwt": "JWT", "hawk": "Hawk", "ntlm": "NTLM"}.get(a["type"], a["type"])
    return t


def _curl(r):
    parts = [f"curl -X {r.get('method', 'GET')} '{_url_raw(r)}'"]
    for h in r.get("header") or []:
        if isinstance(h, dict) and h.get("key") and not h.get("disabled"):
            parts.append(f"-H '{h['key']}: {h.get('value', '')}'")
    b = r.get("body") or {}
    if b.get("mode") == "raw" and b.get("raw"):
        parts.append("-d '" + b["raw"].replace("'", "'\\''") + "'")
    return " \\\n  ".join(parts)


def _example(ex):
    hdr = "".join(f"<div><code>{E(h['key'])}: {E(str(h.get('value', '')))}</code></div>" for h in ex.get("header") or [] if isinstance(h, dict) and h.get("key"))
    body = ex.get("body") or ""
    try:
        body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        pass
    code = int(ex.get("code") or 0)
    return (f"<details class='ex'><summary><span class='code c{code // 100}'>{code or ''}</span> {E(ex.get('name', ''))}</summary>"
            f"{('<div class=hdrs>' + hdr + '</div>') if hdr else ''}{('<pre><code>' + E(body) + '</code></pre>') if body else ''}</details>")


def _request(it, anchors):
    r = it.get("request") or {}
    url = r.get("url") if isinstance(r.get("url"), dict) else {}
    b = r.get("body") or {}
    bhtml = ""
    if b.get("mode") == "raw":
        lang = ((b.get("options") or {}).get("raw") or {}).get("language", "text")
        bhtml = f"<h5>Body ({E(lang)})</h5><pre><code>{E(b.get('raw', ''))}</code></pre>"
    elif b.get("mode") in ("urlencoded", "formdata"):
        bhtml = f"<h5>Body ({E(b['mode'])})</h5>" + _kv_table(b.get(b["mode"]))
    elif b.get("mode") == "graphql":
        g = b.get("graphql") or {}
        bhtml = f"<h5>Body (GraphQL)</h5><pre><code>{E(g.get('query', ''))}</code></pre>"
    auth = _auth_text(r.get("auth"))
    parts = [f"<section class='req' id='{anchors[it['id']]}'><h4><span class='m m-{E(r.get('method', 'GET'))}'>{E(r.get('method', 'GET'))}</span> {E(it['name'])}</h4>",
             f"<p class='url'><code>{E(_url_raw(r))}</code></p>", md(_text(r.get("description")))]
    if url.get("variable"):
        parts.append("<h5>Yo'l parametrlari</h5>" + _kv_table(url["variable"]))
    if url.get("query"):
        parts.append("<h5>Query parametrlari</h5>" + _kv_table(url["query"]))
    if r.get("header"):
        parts.append("<h5>Sarlavhalar</h5>" + _kv_table(r["header"]))
    parts.append(bhtml)
    if auth:
        parts.append(f"<p><b>Auth:</b> {E(auth)}</p>")
    parts.append(f"<details><summary>cURL namunasi</summary><pre><code>{E(_curl(r))}</code></pre></details>")
    if it.get("response"):
        parts.append("<h5>Javob namunalari</h5>" + "".join(_example(e) for e in it["response"] if isinstance(e, dict)))
    parts.append("</section>")
    return "".join(parts)


CSS = """:root{--bg:#fff;--fg:#151821;--muted:#596170;--bd:#e2e5ea;--code:#f6f7f9;--accent:#4338ca}@media (prefers-color-scheme:dark){:root{--bg:#0e1015;--fg:#e7e9ee;--muted:#9aa2b1;--bd:#252933;--code:#151820;--accent:#a5b4fc}}
*{box-sizing:border-box}body{margin:0;font:15px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--fg);display:flex}nav{width:300px;flex:none;height:100vh;position:sticky;top:0;overflow:auto;border-right:1px solid var(--bd);padding:16px}
nav input{width:100%;padding:6px 10px;border:1px solid var(--bd);border-radius:8px;background:var(--bg);color:var(--fg);margin-bottom:12px}nav a{display:block;padding:3px 8px;color:var(--fg);text-decoration:none;border-radius:6px;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}nav a:hover{background:var(--code)}
nav .f{font-weight:600;margin-top:10px;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}main{flex:1;min-width:0;max-width:920px;padding:32px 40px}h1{margin:0 0 4px}h2{margin:40px 0 8px;border-bottom:1px solid var(--bd);padding-bottom:6px}h3{margin:28px 0 6px}.meta{color:var(--muted)}
.req{border:1px solid var(--bd);border-radius:12px;padding:16px 20px;margin:16px 0}.req h4{margin:0 0 6px;font-size:17px}.req h5{margin:16px 0 6px;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.m{display:inline-block;min-width:54px;font:700 12px ui-monospace,Menlo,monospace}.m-GET{color:#157a3a}.m-POST{color:#ad4f08}.m-PUT{color:#1d4ed8}.m-PATCH{color:#7e22ce}.m-DELETE{color:#b91c1c}.m-WS,.m-SSE{color:#0f766e}
code,pre{font:13px ui-monospace,Menlo,monospace}pre{background:var(--code);border:1px solid var(--bd);border-radius:8px;padding:10px 12px;overflow:auto;margin:6px 0}code{background:var(--code);border-radius:4px;padding:1px 4px}pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid var(--bd);padding:5px 8px;text-align:left;vertical-align:top}th{color:var(--muted);font-weight:600}.url{margin:4px 0 8px}.tag{font-size:11px;color:var(--muted);border:1px solid var(--bd);border-radius:999px;padding:0 6px}
details{margin:6px 0}summary{cursor:pointer}.code{display:inline-block;min-width:34px;font:700 12px ui-monospace,monospace;border-radius:6px;padding:1px 6px;background:var(--code)}.c2{color:#157a3a}.c4,.c5{color:#b91c1c}.hdrs{margin:6px 0;color:var(--muted)}
blockquote{margin:8px 0;padding:0 14px;border-left:3px solid var(--bd);color:var(--muted)}a{color:var(--accent)}@media (max-width:800px){body{display:block}nav{position:static;width:auto;height:auto;border:0}main{padding:16px}}"""

JS = "document.getElementById('q').addEventListener('input',function(e){var v=e.target.value.toLowerCase();document.querySelectorAll('nav a').forEach(function(a){a.style.display=a.textContent.toLowerCase().indexOf(v)<0?'none':''})})"


def build_docs(col, folder=None):
    """HTML matn. `folder` — papka nomi/id (faqat shu papka)."""
    root_items, title, desc = col.get("item", []), col["info"]["name"], (col.get("x-apirunner") or {}).get("description", "")
    if folder:
        node = None
        stack = list(root_items)
        while stack:
            x = stack.pop(0)
            if model.is_folder(x):
                if folder in (x["name"], x["id"]):
                    node = x
                    break
                stack = x["item"] + stack
        if not node:
            raise ValueError(f"Papka topilmadi: {folder}")
        root_items, title, desc = node["item"], f"{title} / {node['name']}", (node.get("x-apirunner") or {}).get("description", "")
    used, anchors, nav, body = set(), {}, [], []

    def assign(items):
        for it in items:
            anchors[it["id"]] = _slug(it["name"], used)
            if model.is_folder(it):
                assign(it["item"])
    assign(root_items)

    def walk(items, depth):
        for it in items:
            if model.is_folder(it):
                nav.append(f"<div class='f'>{E(it['name'])}</div>")
                n = min(4, 2 + depth)
                body.append(f"<h{n} id='{anchors[it['id']]}'>{E(it['name'])}</h{n}>{md((it.get('x-apirunner') or {}).get('description', ''))}")
                walk(it["item"], depth + 1)
            else:
                r = it.get("request") or {}
                nav.append(f"<a href='#{anchors[it['id']]}'><span class='m m-{E(r.get('method', 'GET'))}'>{E(r.get('method', 'GET'))}</span> {E(it['name'])}</a>")
                body.append(_request(it, anchors))
    walk(root_items, 0)
    ver = col["info"].get("version")
    return (f"<!doctype html><html lang='uz'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{E(title)} — API hujjat</title><style>{CSS}</style></head><body>"
            f"<nav><input id='q' type='search' placeholder='Qidirish…' aria-label='Qidirish'>{''.join(nav)}</nav><main><h1>{E(title)}</h1>"
            f"<p class='meta'>{('v' + E(str(ver)) + ' · ') if ver else ''}{len(anchors)} ta element · {time.strftime('%Y-%m-%d')} · API Runner</p>{md(desc)}{''.join(body)}</main><script>{JS}</script></body></html>")


def run_cli(args):
    from .cli import CliError, load_collection
    col, _b, _w = load_collection(args)
    try:
        text = build_docs(col, args.folder)
    except ValueError as e:
        raise CliError(str(e)) from e
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Hujjat yozildi: {args.output}")
    return 0
