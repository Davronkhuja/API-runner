import random
import re
import string
import time
import uuid
from datetime import datetime, timezone

_VAR_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")
_PATH_VAR_RE = re.compile(r"(?<=/):([A-Za-z_][\w-]*)")
_MAX_PASSES = 5                                   # {{a}} qiymati ichida {{b}} bo'lsa — ichma-ich yechiladi

_FIRST = ("Ali", "Vali", "Laylo", "Dilnoza", "Jasur", "Madina", "Aziz", "Nodira")
_LAST = ("Karimov", "Rahimova", "Tursunov", "Aliyeva", "Yusupov", "Saidova")

# Postman dinamik o'zgaruvchilari ($-prefiksli): har chaqiruvda yangi qiymat
DYNAMIC = {
    "$guid": lambda: str(uuid.uuid4()),
    "$randomUUID": lambda: str(uuid.uuid4()),
    "$timestamp": lambda: str(int(time.time())),
    "$isoTimestamp": lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    "$randomInt": lambda: str(random.randint(0, 1000)),
    "$randomBoolean": lambda: random.choice(("true", "false")),
    "$randomAlphaNumeric": lambda: random.choice(string.ascii_letters + string.digits),
    "$randomFirstName": lambda: random.choice(_FIRST),
    "$randomLastName": lambda: random.choice(_LAST),
    "$randomEmail": lambda: f"{random.choice(_FIRST).lower()}{random.randint(10, 999)}@example.com",
}


def _once(text, variables):
    def replacer(match):
        key = match.group(1).strip()
        if key in variables:
            v = variables[key]
            return "" if v is None else str(v)
        if key in DYNAMIC:
            return DYNAMIC[key]()
        return match.group(0)

    return _VAR_RE.sub(replacer, text)


def replace_variables(text, variables):
    """`{{name}}` ni qiymat bilan almashtiradi. Noma'lum nom o'zgarishsiz qoladi.

    O'zgaruvchi qiymati ichidagi `{{...}}` ham yechiladi (cheklangan chuqurlikda); `{{$guid}}` kabi
    dinamik nomlar har chaqiruvda yangilanadi. Aylanma bog'lanish cheksiz tsiklga olib kelmaydi.
    """
    if text is None:
        return ""
    out = str(text)
    for _ in range(_MAX_PASSES):
        nxt = _once(out, variables)
        if nxt == out:
            break
        out = nxt
    return out


def apply_path_variables(url, path_vars):
    """`/users/:id` dagi `:id` ni qiymat bilan almashtiradi (faqat yo'l qismida; port va sxema tegilmaydi)."""
    if not path_vars:
        return url
    values = {p.get("name"): p.get("value", "") for p in path_vars if p.get("name")}
    m = re.match(r"^([a-zA-Z][\w+.-]*://[^/?#]*)?([^?#]*)(.*)$", url, re.S)
    head, path, tail = m.group(1) or "", m.group(2), m.group(3)
    path = _PATH_VAR_RE.sub(lambda mm: str(values[mm.group(1)]) if mm.group(1) in values else mm.group(0), path)
    return head + path + tail
