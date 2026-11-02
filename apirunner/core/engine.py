"""Yagona request engine: bitta so'rov, batch, runner va (keyin) CLI shu funksiyadan o'tadi.

    execute(spec, ctx) -> result

`spec`  — so'rov tavsifi (URL/header/body shablonlari, `{{var}}` bilan).
`ctx`   — bajarilish konteksti (o'zgaruvchilar, retry, stop, fayl siyosati).
HTTP kutubxonasi `_send()` ichida ajratilgan (ADR 0003: keyin httpx ga almashtirish mumkin).
"""
import json
import os
import ssl
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import httpx

from .auth import apply_auth_config
from .variables import apply_path_variables, replace_variables

MAX_TEXT_RESPONSE = 500_000
MUTATING = ("POST", "PUT", "PATCH", "DELETE")


class FilePolicyError(PermissionError):
    pass


@dataclass
class ExecContext:
    variables: dict = field(default_factory=dict)
    retry_count: int = 0
    retry_pause: float = 0.5
    stop: Optional[Callable[[], bool]] = None          # True bo'lsa — to'xta
    allowed_file_roots: tuple = ()                     # fayl parametrlari uchun ruxsat etilgan papkalar
    allowed_files: frozenset = frozenset()             # foydalanuvchi aniq tanlagan fayllar
    cookies: object = None                             # CookieStore (None = cookie jar o'chiq)

    def stopped(self):
        return bool(self.stop and self.stop())


def _sleep_interruptible(seconds, ctx):
    end = time.monotonic() + seconds
    while time.monotonic() < end and not ctx.stopped():
        time.sleep(min(0.1, max(0.0, end - time.monotonic())))


def _resolve_file(path, ctx):
    """Fayl yo'li siyosati: faqat ruxsat etilgan papkalar yoki aniq tanlangan fayllar."""
    real = os.path.realpath(path)
    if real in ctx.allowed_files:
        return real
    for root in ctx.allowed_file_roots:
        root_real = os.path.realpath(root)
        if real == root_real or real.startswith(root_real + os.sep):
            return real
    raise FilePolicyError("Fayl yo'liga ruxsat yo'q: " + path + ". 📎 orqali faylni qayta tanlang")


def _build_kwargs(spec, ctx, opened):
    v = ctx.variables
    method = spec.get("method", "GET").upper()
    body_type = spec.get("body_type", "raw")
    timeout = float(spec.get("timeout") or 120)

    headers = {}
    auth = replace_variables(spec.get("authorization", ""), v).strip()
    if auth:
        headers["Authorization"] = auth
    for item in spec.get("headers") or []:
        n = (item.get("name") or "").strip()
        if n:
            headers[n] = replace_variables(item.get("value", ""), v)

    params, file_params = {}, {}
    for item in spec.get("params") or []:
        n = (item.get("name") or "").strip()
        if not n:
            continue
        val = replace_variables(item.get("value", ""), v)
        (file_params if item.get("type") == "file" else params)[n] = val

    body = replace_variables(spec.get("body", ""), v)
    ctype = spec.get("content_type", "")
    has_ct = lambda: "content-type" in {k.lower() for k in headers}  # noqa: E731
    if body and ctype and not has_ct():
        headers["Content-Type"] = ctype

    kw = {"params": params, "headers": headers, "timeout": timeout,
          "verify": bool(spec.get("ssl_verify", True)),
          "http2": bool(spec.get("http2", False))}       # sukut: HTTP/1.1

    if file_params:
        files = {}
        for fname, fval in file_params.items():
            # qiymat: "yo'l::AslNom.ext" yoki shunchaki yo'l
            if "::" in fval:
                fpath, orig = fval.split("::", 1)
            else:
                fpath, orig = fval, os.path.basename(fval)
            fpath = fpath.strip()
            if os.path.isfile(fpath):
                fh = open(_resolve_file(fpath, ctx), "rb")
                opened.append(fh)
                files[fname] = (orig, fh, "application/octet-stream")
            else:
                files[fname] = (None, fpath)
        kw["files"] = files
        kw["headers"] = {k: x for k, x in headers.items() if k.lower() != "content-type"}
    elif method in MUTATING and spec.get("body_file"):
        # binary body: faylning xom baytlari (fayl siyosati bo'yicha tekshiriladi)
        with open(_resolve_file(spec["body_file"], ctx), "rb") as fh:
            kw["data"] = fh.read()
        if not has_ct():
            headers["Content-Type"] = ctype or "application/octet-stream"
    elif method in MUTATING and (body or body_type == "multipart"):
        if body_type == "multipart":
            files = {}
            for fld in spec.get("multipart_fields") or []:
                fn = replace_variables(fld.get("name", ""), v).strip()
                if fn:
                    files[fn] = (None, replace_variables(fld.get("value", ""), v))
            if files:
                kw["files"] = files
            kw["headers"] = {k: x for k, x in headers.items() if k.lower() != "content-type"}
        else:
            if body_type == "json" and not has_ct():
                headers["Content-Type"] = "application/json"
            kw["data"] = body.encode("utf-8") if body else b""   # xom matn, qayta serializatsiyasiz
    url = apply_path_variables(replace_variables(spec.get("url", ""), v), [
        {"name": p.get("name"), "value": replace_variables(p.get("value", ""), v)} for p in spec.get("path_variables") or []])
    cfg = spec.get("auth_config")
    if cfg:
        payload = kw.get("data") if "files" not in kw else None      # multipart: SigV4 UNSIGNED-PAYLOAD
        url, auth_obj = apply_auth_config(cfg, v, method, url, kw["headers"], kw["params"], payload if payload is not None else (b"" if "files" not in kw else None))
        if auth_obj is not None:
            kw["auth"] = auth_obj
    return method, url, kw


class _Trace:
    """httpcore trace hodisalaridan timing yig'adi. Olinmagan qiymat None qoladi (UI: "—").

    httpcore DNS'ni alohida ko'rsatmaydi, shuning uchun `dns` doim None; `connect` DNS'ni ham o'z ichiga oladi.
    """

    def __init__(self):
        self.t0 = time.perf_counter()
        self.marks = {}

    def __call__(self, name, info):
        self.marks[name] = time.perf_counter()

    def _span(self, a, b):
        if a in self.marks and b in self.marks:
            return round(self.marks[b] - self.marks[a], 6)
        return None

    def result(self, total):
        m, now = self.marks, self.t0
        first_byte = next((m[k] for k in m if k.endswith("receive_response_headers.complete")), None)
        return {
            "dns": None,
            "connect": self._span("connection.connect_tcp.started", "connection.connect_tcp.complete"),
            "tls": self._span("connection.start_tls.started", "connection.start_tls.complete"),
            "ttfb": round(first_byte - now, 6) if first_byte else None,
            "total": round(total, 6),
        }


def _tls_verify(spec):
    """verify: bool yoki ssl.SSLContext (CA to'plami / mijoz sertifikati berilganda)."""
    verify = bool(spec.get("ssl_verify", True))
    ca, cert, key = (spec.get("ca_bundle") or "").strip(), (spec.get("cert") or "").strip(), (spec.get("cert_key") or "").strip()
    if not (ca or cert):
        return verify
    for label, p in (("CA fayli", ca), ("Sertifikat fayli", cert), ("Sertifikat kaliti", key)):
        if p and not os.path.isfile(p):
            raise ValueError(f"{label} topilmadi: {p}")
    ctx = ssl.create_default_context(cafile=ca or None)
    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT      # Python 3.13+ qat'iy rejimi: xususiy CA sertifikatlarida AKI yo'q bo'lishi mumkin (requests/Postman kabi yumshoq)
    if not verify:
        ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    if cert:
        ctx.load_cert_chain(cert, key or None, spec.get("cert_passphrase") or None)
    return ctx


def _send(method, url, kw, spec=None, ctx=None):
    spec = spec or {}
    kw = dict(kw)
    params = kw.pop("params", None)
    if params:                      # httpx params'ni URL query o'rniga qo'yadi; requests kabi qo'shamiz
        url = str(httpx.URL(url).copy_merge_params(params))
    http2 = kw.pop("http2", False)
    timeout, kw_verify = kw.pop("timeout"), kw.pop("verify")
    if "data" in kw:
        kw["content"] = kw.pop("data")
    opts = {"follow_redirects": bool(spec.get("follow_redirects", True))}
    if spec.get("max_redirects") not in (None, ""):
        opts["max_redirects"] = max(0, int(spec["max_redirects"]))
    if (spec.get("proxy") or "").strip():
        opts["proxy"] = spec["proxy"].strip()
    store = ctx.cookies if ctx and spec.get("use_cookies", True) else None
    jar, loaded = store.load_jar() if store else (None, set())
    if jar is not None:
        opts["cookies"] = httpx.Cookies(jar)
    trace = _Trace()
    with httpx.Client(http2=http2, verify=_tls_verify(spec) if (spec.get("ca_bundle") or spec.get("cert")) else kw_verify, timeout=timeout, **opts) as client:
        try:
            resp = client.request(method, url, extensions={"trace": trace}, **kw)
        finally:
            if store:
                store.save_jar(client.cookies.jar, loaded)
    return resp, trace


def _parse_body(resp):
    try:
        return resp.json()
    except Exception:
        text = resp.text
        if len(text) > MAX_TEXT_RESPONSE:
            text = text[:MAX_TEXT_RESPONSE] + f"\n\n... [{len(text)/1024/1024:.1f} MB, qisqartirildi]"
        return text


def execute(spec, ctx=None):
    """Bitta so'rovni (retry bilan) bajaradi. Hech qachon exception tashlamaydi.

    Qaytaradi: {status, time, size, url, response, resp_headers, error, retries}
    `status` — son yoki "ERROR" (tarmoq/timeout/siyosat xatosi).
    """
    ctx = ctx or ExecContext()
    timeout = float(spec.get("timeout") or 120)
    last_err, last_elapsed, error_code = "Unknown error", 0.0, None
    url_for_error = replace_variables(spec.get("url", ""), ctx.variables)

    for attempt in range(ctx.retry_count + 1):
        if ctx.stopped():
            break
        if attempt > 0:
            _sleep_interruptible(ctx.retry_pause, ctx)
        opened = []
        start = time.perf_counter()
        try:
            method, url, kw = _build_kwargs(spec, ctx, opened)
            url_for_error = url
            resp, trace = _send(method, url, kw, spec, ctx)
            elapsed = last_elapsed = time.perf_counter() - start
            ok = 200 <= resp.status_code < 300
            if not ok and attempt < ctx.retry_count:
                last_err = f"HTTP {resp.status_code}"
                continue
            return {"status": resp.status_code, "time": elapsed, "size": len(resp.content),
                    "url": str(resp.url), "response": _parse_body(resp),
                    "resp_headers": dict(resp.headers), "error": not ok, "retries": attempt,
                    "timing": trace.result(elapsed), "http_version": resp.http_version,
                    "set_cookies": resp.headers.get_list("set-cookie"), "redirects": len(resp.history)}
        except httpx.TimeoutException:
            last_elapsed = time.perf_counter() - start
            last_err = "Request timed out ({:.0f}s)".format(timeout)
        except FilePolicyError as exc:
            last_elapsed = time.perf_counter() - start
            last_err = str(exc)
            error_code = "file_policy"
            break                                   # siyosat xatosini qayta urinish bema'ni
        except Exception as exc:                    # noqa: BLE001 — engine hech qachon tashlamaydi
            last_elapsed = time.perf_counter() - start
            last_err = str(exc)
        finally:
            for fh in opened:
                try:
                    fh.close()
                except OSError:
                    pass

    return {"status": "ERROR", "time": last_elapsed, "size": 0, "url": url_for_error,
            "response": last_err, "resp_headers": {}, "error": True, "retries": ctx.retry_count,
            "timing": None, "http_version": None, "error_code": error_code}
