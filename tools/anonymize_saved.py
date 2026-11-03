"""saved_requests.json -> anonimlashtirilgan fixture (tuzilma, sonlar, kalitlar va ichma-ich holat saqlanadi).

    python3 tools/anonymize_saved.py <kirish.json> <chiqish.json>

Kirish fayli FAQAT O'QILADI. Barcha matnli qiymatlar (nomlar, URL, header, body, token) almashtiriladi;
metod/body_type/content_type kabi tuzilmaviy qiymatlar saqlanadi. Oxirida o'z-o'zini tekshiradi.
"""
import json
import re
import sys
import uuid

NS = uuid.UUID("12345678-1234-5678-1234-567812345678")
KEEP = {"method": {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"},
        "body_type": {"raw", "json", "form", "multipart", "none", ""},
        "type": {"file", "text", ""}}
MIME = re.compile(r"^(application|text|multipart)/[\w.+\-]+(;.*)?$")
TS = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+$")
maps = {}


def label(kind, original):
    m = maps.setdefault(kind, {})
    if original not in m:
        m[original] = len(m) + 1
    return m[original]


def anon_id(v):
    return None if v is None else str(uuid.uuid5(NS, str(v)))


def anon_str(key, v, parent_key=""):
    if v == "":
        return ""
    if key in KEEP and v in KEEP[key]:
        return v
    if key == "content_type" and MIME.match(v):
        return v.split(";")[0]
    if TS.match(v):
        return v
    if key == "url":
        return f"https://host-{label('host', v.split('/')[2] if '://' in v else v)}.example.test/path-{label('url', v)}"
    if key == "body":
        return json.dumps({f"key{label('body', v)}": "value"}) if v.lstrip().startswith(("{", "[")) else f"body-{label('body', v)}"
    if key == "authorization":
        return "Bearer REDACTED"
    return f"{key or parent_key or 'text'}-{label(key or 'text', v)}"


def walk(node, key="", parent=""):
    if isinstance(node, dict):
        return {k: (anon_id(v) if k in ("id", "folder_id") else walk(v, k, key)) for k, v in node.items()}
    if isinstance(node, list):
        return [walk(x, key, parent) for x in node]
    if isinstance(node, str):
        return anon_str(key, node, parent)
    return node


OK = re.compile(r"^(\w+-\d+|https://host-\d+\.example\.test/path-\d+|Bearer REDACTED|[0-9a-f\-]{36}|[\w\-]+|\{\"key\d+\": \"value\"\})$")


def leaves(n):
    if isinstance(n, dict):
        for v in n.values():
            yield from leaves(v)
    elif isinstance(n, list):
        for v in n:
            yield from leaves(v)
    elif isinstance(n, str):
        yield n


def self_check(out):
    """Anonimlashtirilgan daraxtdagi har bir matn kutilgan andozaga mos bo'lishi shart."""
    return [s for s in leaves(out) if not (s == "" or OK.match(s) or MIME.match(s) or TS.match(s))]


def main(src, dst):
    with open(src, "r", encoding="utf-8") as f:        # faqat o'qish
        data = json.load(f)
    out = walk(data)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    bad = self_check(out)
    if bad:
        print("ANONIMLASHTIRISH XATOSI: tekshiruvdan o'tmagan qiymatlar soni:", len(bad), file=sys.stderr)
        return 1
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text)
    d = out if isinstance(out, dict) else {"folders": [], "requests": out}
    print(f"OK: {len(d.get('folders', []))} papka, {len(d.get('requests', []))} so'rov -> {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
