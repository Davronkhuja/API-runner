"""Importerlar uchun umumiy: matn → tuzilma (JSON/YAML), format aniqlash, statistika, URL yordamchilari."""
import json
import re
from urllib.parse import parse_qsl, quote, urlsplit

import yaml

from ..storage import model

MAX_BYTES = 20 * 1024 * 1024


class ImportErr(ValueError):
    """Foydalanuvchiga ko'rsatiladigan import xatosi."""


def parse_structured(text):
    """JSON, bo'lmasa YAML. Matn emas/bo'sh/juda katta bo'lsa ImportErr."""
    if not isinstance(text, str):
        return text
    if len(text) > MAX_BYTES:
        raise ImportErr("Fayl 20 MB dan katta")
    t = text.lstrip("﻿").strip()
    if not t:
        raise ImportErr("Bo'sh matn")
    try:
        return json.loads(t)
    except json.JSONDecodeError as je:
        if t[:1] in "{[":
            try:
                return yaml.safe_load(t)                       # YAML JSON'ning superseti: sal buzuq JSON'ni ham o'qiy olishi mumkin
            except yaml.YAMLError:
                raise ImportErr(f"JSON noto'g'ri: {je.msg} ({je.lineno}-qator)") from je
        try:
            doc = yaml.safe_load(t)
        except yaml.YAMLError as ye:
            raise ImportErr("Matn JSON ham, YAML ham emas") from ye
        if not isinstance(doc, (dict, list)):
            raise ImportErr("Matn JSON ham, YAML ham, cURL ham emas")
        return doc


def detect(doc):
    """Tuzilma bo'yicha format: postman | postman-env | postman-globals | openapi | insomnia | har | None."""
    if not isinstance(doc, dict):
        return None
    if ("openapi" in doc or "swagger" in doc) and isinstance(doc.get("paths"), dict):
        return "openapi"
    if doc.get("_type") == "export" and isinstance(doc.get("resources"), list):
        return "insomnia"
    if isinstance(doc.get("log"), dict) and isinstance(doc["log"].get("entries"), list):
        return "har"
    if isinstance(doc.get("item"), list) and isinstance(doc.get("info"), dict):
        return "postman"
    if isinstance(doc.get("values"), list) and "item" not in doc:
        scope = doc.get("_postman_variable_scope")
        if scope == "globals":
            return "postman-globals"
        if scope == "environment" or "name" in doc:
            return "postman-env"
    return None


def is_curl(text):
    if not isinstance(text, str):
        return False
    body = "\n".join(l for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#"))          # boshidagi izohlar o'tkazib yuboriladi
    return bool(re.match(r"^\s*(curl|\$\s*curl)\b", body, re.I))


def walk_items(items):
    for it in items or []:
        yield it
        if model.is_folder(it):
            yield from walk_items(it["item"])


def stats(col):
    s = {"folders": 0, "requests": 0, "examples": 0, "scripts": 0, "auth": 0, "variables": len(col.get("variable") or [])}
    if col.get("auth"):
        s["auth"] += 1
    s["scripts"] += len(col.get("event") or [])
    for it in walk_items(col.get("item")):
        if model.is_folder(it):
            s["folders"] += 1
        else:
            s["requests"] += 1
            s["examples"] += len(it.get("response") or [])
            if (it.get("request") or {}).get("auth"):
                s["auth"] += 1
        s["scripts"] += len(it.get("event") or [])
        s["variables"] += len(it.get("variable") or [])
    return s


def split_url(raw):
    """`raw` URL → (base-without-query, [(key, value)] query). `{{var}}` lar buzilmaydi."""
    base, _, q = (raw or "").partition("#")[0].partition("?")
    pairs = []
    for part in q.split("&") if q else []:
        k, _, v = part.partition("=")
        pairs.append((k, v))
    return base, pairs


def parts_from_url(raw):
    """Postman url obyekti qismlari: protocol/host/path (raw'dan). Faqat raw haqiqiy URL bo'lsa."""
    base, _ = split_url(raw)
    m = re.match(r"^([a-zA-Z][\w+.-]*)://([^/]+)(/.*)?$", base)
    if m:
        host, _, port = m.group(2).partition(":") if not m.group(2).startswith("{{") else (m.group(2), "", "")
        path = [p for p in (m.group(3) or "").split("/") if p != ""]
        out = {"protocol": m.group(1), "host": host.split("."), "path": path}
        if port.isdigit():
            out["port"] = port
        return out
    m = re.match(r"^(\{\{[^}]+\}\}|[^/{]+)(/.*)?$", base)              # {{baseUrl}}/users/1
    if m and base:
        return {"host": [m.group(1)], "path": [p for p in (m.group(2) or "").split("/") if p != ""]}
    return {}


def ensure_unique_ids(items, seen=None):
    seen = seen if seen is not None else set()
    for n in items:
        i = n.get("id")
        if not i or i in seen:
            i = model.new_id()
        seen.add(i)
        n["id"] = i
        if model.is_folder(n):
            ensure_unique_ids(n["item"], seen)
    return items


def slug(s, default="x"):
    s = re.sub(r"[^A-Za-z0-9]+", "_", s or "").strip("_")
    return s or default


def qs(pairs):
    return "&".join(f"{k}={v}" if v != "" or True else k for k, v in pairs)


def query_from_url(url):
    """Haqiqiy URL (HAR/cURL) → [(key,value)] dekodlangan."""
    return parse_qsl(urlsplit(url).query, keep_blank_values=True)


def enc(s):
    return quote(s, safe="{}$-_.~")
