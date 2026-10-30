"""Server tomonidagi auth turlari: API Key, JWT (HS*), AWS SigV4, Digest. Faqat stdlib + httpx."""
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

import httpx

from .variables import replace_variables

_HS = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}


def _b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def make_jwt(cfg, variables):
    """HS256/384/512 JWT. `payload` — JSON matn (o'zgaruvchilar va {{$timestamp}} yechiladi)."""
    alg = (cfg.get("algorithm") or "HS256").upper()
    if alg not in _HS:
        raise ValueError(f"JWT algoritmi qo'llab-quvvatlanmaydi: {alg} (HS256/HS384/HS512)")
    secret = replace_variables(cfg.get("secret", ""), variables)
    key = base64.b64decode(secret) if cfg.get("secretIsBase64") else secret.encode()
    try:
        payload = json.loads(replace_variables(cfg.get("payload") or "{}", variables))
        extra = json.loads(replace_variables(cfg.get("header") or "{}", variables))
    except json.JSONDecodeError as e:
        raise ValueError(f"JWT payload/header JSON noto'g'ri: {e}") from e
    header = {"alg": alg, "typ": "JWT", **extra}
    signing = _b64url(json.dumps(header, separators=(",", ":")).encode()) + "." + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(key, signing.encode(), _HS[alg]).digest()
    return signing + "." + _b64url(sig)


def _hmac(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sigv4_headers(method, url, payload, access_key, secret_key, region, service, session_token="", now=None):
    """AWS Signature V4: qaytaradi {Authorization, x-amz-date, [x-amz-security-token], [x-amz-content-sha256]}."""
    now = now or datetime.now(timezone.utc)
    amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    u = urlsplit(url)
    payload_hash = hashlib.sha256(payload if isinstance(payload, bytes) else b"").hexdigest() if payload is not None else "UNSIGNED-PAYLOAD"
    signed = {"host": u.netloc, "x-amz-date": amz_date}
    if session_token:
        signed["x-amz-security-token"] = session_token
    if service == "s3":
        signed["x-amz-content-sha256"] = payload_hash
    canon_path = quote(u.path or "/", safe="/-_.~%")
    pairs = sorted((quote(k, safe="-_.~"), quote(v, safe="-_.~")) for k, v in
                   (p.split("=", 1) if "=" in p else (p, "") for p in u.query.split("&") if p))
    canonical = "\n".join([method.upper(), canon_path, "&".join(f"{k}={v}" for k, v in pairs),
                           "".join(f"{k}:{v.strip()}\n" for k, v in sorted(signed.items())),
                           ";".join(sorted(signed)), payload_hash])
    scope = f"{day}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _hmac(_hmac(_hmac(_hmac(("AWS4" + secret_key).encode(), day), region), service), "aws4_request")
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    out = {"Authorization": f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={';'.join(sorted(signed))}, Signature={signature}",
           "x-amz-date": amz_date}
    if session_token:
        out["x-amz-security-token"] = session_token
    if service == "s3":
        out["x-amz-content-sha256"] = payload_hash
    return out


def apply_auth_config(cfg, v, method, url, headers, params, payload):
    """`spec.auth_config` ni headers/params ga (yoki httpx auth obyektiga) qo'llaydi.

    Qaytaradi: (url, httpx_auth | None). `headers`/`params` joyida o'zgartiriladi.
    """
    t = (cfg or {}).get("type")
    sub = lambda k: replace_variables(cfg.get(k, ""), v)  # noqa: E731
    if t == "apikey":
        key = sub("key").strip()
        if key:
            (params if cfg.get("in") == "query" else headers)[key] = sub("value")
    elif t == "jwt":
        token = make_jwt(cfg, v)
        if cfg.get("addTo") == "query":
            params[sub("queryParamKey") or "token"] = token
        else:
            headers["Authorization"] = (sub("headerPrefix") or "Bearer").strip() + " " + token
    elif t == "awsv4":
        full = str(httpx.URL(url).copy_merge_params(params)) if params else url
        headers.update(sigv4_headers(method, full, payload, sub("accessKey"), sub("secretKey"), sub("region") or "us-east-1",
                                     sub("service") or "execute-api", sub("sessionToken")))
    elif t == "digest":
        return url, httpx.DigestAuth(sub("username"), sub("password"))
    return url, None
