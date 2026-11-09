"""Workspace bo'ylab Find & Replace: ruxsat etilgan matn maydonlari (URL, header, param, body, auth, skript, tavsif, nom, o'zgaruvchi, muhit) bo'yicha
qidirish, oldindan ko'rish va tanlanganlarini almashtirish. Tuzilma kalitlari/id'lar hech qachon tegilmaydi."""
import re

from . import model

TARGETS = ("name", "url", "params", "headers", "body", "auth", "scripts", "description", "variables", "environments")
MAX_FIELDS = 2000
MAX_TEXT = 2_000_000
SNIP = 40


class FindError(ValueError):
    pass


def build_regex(query, case=False, word=False, regex=False):
    if not query:
        raise FindError("Qidiruv matni bo'sh")
    pat = query if regex else re.escape(query)
    if word:
        pat = r"(?<![\w])(?:" + pat + r")(?![\w])"
    try:
        return re.compile(pat, 0 if case else re.IGNORECASE | re.UNICODE)
    except re.error as e:
        raise FindError(f"Regex noto'g'ri: {e}") from e


def _get(doc, path):
    cur = doc
    for p in path:
        try:
            cur = cur[p]
        except (KeyError, IndexError, TypeError):
            return None
    return cur


def _set(doc, path, value):
    cur = doc
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = value


class Field:
    __slots__ = ("id", "doc_kind", "doc", "doc_id", "doc_name", "owner_kind", "owner_id", "owner_name", "path", "label", "secret", "text", "is_lines")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _fields_of_collection(col, targets):
    cid, cname = model.collection_id(col), col["info"]["name"]
    out = []

    def add(owner_kind, owner_id, owner_name, path, label, target, secret=False):
        if target not in targets:
            return
        v = _get(col, path)
        is_lines = isinstance(v, list)
        if is_lines:
            v = "\n".join(str(x) for x in v)
        if not isinstance(v, str) or not v or len(v) > MAX_TEXT:
            return
        out.append(Field(id=f"c:{cid}:{owner_id}:" + "/".join(str(p) for p in path), doc_kind="collection", doc=col, doc_id=cid, doc_name=cname, owner_kind=owner_kind,
                         owner_id=owner_id, owner_name=owner_name, path=path, label=label, secret=secret, text=v, is_lines=is_lines))

    def kv(base, label, target, owner, arr, keys=("key", "value"), secret_types=()):
        for i, row in enumerate(_get(col, base + [arr]) or []):
            if not isinstance(row, dict):
                continue
            for k in keys:
                add(*owner, base + [arr, i, k], f"{label} · {row.get('key', '')} ({k})" if k != "key" else f"{label} · kalit", target, secret=(k == "value" and row.get("type") == "secret"))

    def common(base, owner):
        if "auth" in targets and isinstance(_get(col, base + ["auth"]), dict):
            a = _get(col, base + ["auth"])
            t = a.get("type")
            for i, row in enumerate(a.get(t) or [] if isinstance(a.get(t), list) else []):
                if isinstance(row, dict) and isinstance(row.get("value"), str):
                    add(*owner, base + ["auth", t, i, "value"], f"Auth · {t} · {row.get('key', '')}", "auth", secret=True)
        for j, ev in enumerate(_get(col, base + ["event"]) or []):
            if isinstance(ev, dict) and isinstance((ev.get("script") or {}).get("exec"), (list, str)):
                add(*owner, base + ["event", j, "script", "exec"], f"Skript · {ev.get('listen', '')}", "scripts")
        kv(base, "O'zgaruvchi", "variables", owner, "variable", ("value",))

    col_owner = ("collection", "", cname)
    add(*col_owner, ["info", "name"], "Nomi", "name")
    add(*col_owner, ["x-apirunner", "description"], "Tavsif", "description")
    common([], col_owner)

    def walk(items, base):
        for idx, it in enumerate(items):
            p = base + [idx]
            if model.is_folder(it):
                owner = ("folder", it["id"], it["name"])
                add(*owner, p + ["name"], "Nomi", "name")
                add(*owner, p + ["x-apirunner", "description"], "Tavsif", "description")
                common(p, owner)
                walk(it["item"], p + ["item"])
            else:
                owner = ("item", it["id"], it["name"])
                add(*owner, p + ["name"], "Nomi", "name")
                r = p + ["request"]
                if isinstance(it.get("request"), dict):
                    add(*owner, r + ["url", "raw"], "URL", "url")
                    kv(r + ["url"], "Param", "params", owner, "query")
                    kv(r, "Header", "headers", owner, "header")
                    add(*owner, r + ["description"], "Tavsif", "description")
                    b = it["request"].get("body") or {}
                    add(*owner, r + ["body", "raw"], "Body", "body")
                    kv(r + ["body"], "Body (urlencoded)", "body", owner, "urlencoded")
                    for i, row in enumerate(b.get("formdata") or []):
                        if isinstance(row, dict) and row.get("type") != "file":
                            for k in ("key", "value"):
                                add(*owner, r + ["body", "formdata", i, k], f"Body (form-data) · {row.get('key', '')} ({k})", "body")
                    add(*owner, r + ["body", "graphql", "query"], "Body (GraphQL)", "body")
                    add(*owner, r + ["body", "graphql", "variables"], "Body (GraphQL variables)", "body")
                    if "auth" in targets and isinstance(it["request"].get("auth"), dict):
                        a = it["request"]["auth"]
                        t = a.get("type")
                        for i, row in enumerate(a.get(t) if isinstance(a.get(t), list) else []):
                            if isinstance(row, dict) and isinstance(row.get("value"), str):
                                add(*owner, r + ["auth", t, i, "value"], f"Auth · {t} · {row.get('key', '')}", "auth", secret=True)
                for j, ev in enumerate(it.get("event") or []):
                    if isinstance(ev, dict) and isinstance((ev.get("script") or {}).get("exec"), (list, str)):
                        add(*owner, p + ["event", j, "script", "exec"], f"Skript · {ev.get('listen', '')}", "scripts")
    walk(col.get("item", []), ["item"])
    return out


def _fields_of_env(env):
    out = []
    for i, row in enumerate(env.get("values") or []):
        for k, label in (("value", "Initial"), ("current", "Current")):
            v = row.get(k)
            if isinstance(v, str) and v:
                out.append(Field(id=f"e:{env['id']}::values/{i}/{k}", doc_kind="environment", doc=env, doc_id=env["id"], doc_name=env.get("name", ""), owner_kind="environment", owner_id=env["id"],
                                 owner_name=env.get("name", ""), path=["values", i, k], label=f"{row.get('key', '')} ({label})", secret=row.get("type") == "secret", text=v, is_lines=False))
    return out


def collect(collections, environments, targets, collection_ids=None):
    targets = set(targets or TARGETS) & set(TARGETS)
    out = []
    for col in collections:
        if collection_ids and model.collection_id(col) not in collection_ids:
            continue
        out += _fields_of_collection(col, targets)
    if "environments" in targets and not collection_ids:
        for env in environments:
            out += _fields_of_env(env)
    return out


def search(fields, rx, replacement, regex):
    results, truncated = [], False
    for f in fields:
        ms = list(rx.finditer(f.text))
        if not ms:
            continue
        if len(results) >= MAX_FIELDS:
            truncated = True
            break
        snips = []
        if not f.secret:
            for m in ms[:3]:
                a, b = max(0, m.start() - SNIP), min(len(f.text), m.end() + SNIP)
                try:
                    rep = m.expand(replacement) if regex else replacement
                except (re.error, IndexError) as e:
                    raise FindError(f"Almashtirish matni noto'g'ri: {e}") from e
                snips.append({"before": f.text[a:m.start()], "match": m.group(0), "after": f.text[m.end():b], "replacement": rep, "lead": a > 0, "trail": b < len(f.text)})
        results.append({"id": f.id, "doc_kind": f.doc_kind, "collection_id": f.doc_id if f.doc_kind == "collection" else None, "collection_name": f.doc_name,
                        "owner_kind": f.owner_kind, "owner_id": f.owner_id, "owner_name": f.owner_name, "field": f.label, "count": len(ms), "secret": f.secret, "snippets": snips})
    return results, truncated


def apply(fields, rx, replacement, regex, ids):
    """Tanlangan maydonlarga almashtirishni qo'llaydi (hujjatlar joyida o'zgaradi). Qaytaradi: (o'zgargan hujjatlar to'plami, almashtirishlar soni, o'tkazib yuborilgan id'lar)."""
    want, changed_docs, total = set(ids), {}, 0
    seen = set()
    for f in fields:
        if f.id not in want:
            continue
        seen.add(f.id)
        new, n = rx.subn(replacement if regex else (lambda _m, r=replacement: r), f.text)
        if not n:
            continue
        _set(f.doc, f.path, new.split("\n") if f.is_lines else new)
        total += n
        changed_docs[(f.doc_kind, f.doc_id)] = f.doc
    return changed_docs, total, sorted(want - seen)
