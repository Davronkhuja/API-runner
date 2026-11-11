"""Server tomonidagi auth turlari: API Key, JWT (HS*/RS*/PS*/ES*), AWS SigV4, Digest, Hawk, NTLM. stdlib + httpx (+ asimmetrik JWT uchun `cryptography`)."""
import base64
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import quote, urlsplit

import httpx

from .ntlm import NTLMAuth
from .variables import replace_variables

_HS = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}


def _b64url(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


_ASYM = {"RS256": ("RS", "SHA256"), "RS384": ("RS", "SHA384"), "RS512": ("RS", "SHA512"), "PS256": ("PS", "SHA256"), "PS384": ("PS", "SHA384"), "PS512": ("PS", "SHA512"),
         "ES256": ("ES", "SHA256"), "ES384": ("ES", "SHA384"), "ES512": ("ES", "SHA512")}
_ES_CURVE = {"ES256": ("secp256r1", 32), "ES384": ("secp384r1", 48), "ES512": ("secp521r1", 66)}
JWT_ALGORITHMS = list(_HS) + list(_ASYM)


def _sign_asym(alg, pem, passphrase, data):
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
        from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    except ImportError as e:          # pragma: no cover - muhitga bog'liq
        raise ValueError("RS*/PS*/ES* JWT uchun `cryptography` kerak: pip install cryptography") from e
    kind, hname = _ASYM[alg]
    h = getattr(hashes, hname)()
    try:
        key = serialization.load_pem_private_key(pem.strip().encode(), password=passphrase.encode() if passphrase else None)
    except (ValueError, TypeError) as e:
        raise ValueError(f"JWT private key o'qilmadi (PEM, kerak bo'lsa passphrase): {e}") from e
    if kind in ("RS", "PS"):
        if not isinstance(key, rsa.RSAPrivateKey):
            raise ValueError(f"{alg} uchun RSA private key kerak")
        pad = padding.PKCS1v15() if kind == "RS" else padding.PSS(mgf=padding.MGF1(h), salt_length=h.digest_size)
        return key.sign(data, pad, h)
    curve, size = _ES_CURVE[alg]
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != curve:
        raise ValueError(f"{alg} uchun EC ({curve}) private key kerak")
    r, s_ = decode_dss_signature(key.sign(data, ec.ECDSA(h)))
    return r.to_bytes(size, "big") + s_.to_bytes(size, "big")           # JOSE: r||s (DER emas)


def make_jwt(cfg, variables):
    """HS*/RS*/PS*/ES* JWT. `payload` — JSON matn (o'zgaruvchilar va {{$timestamp}} yechiladi); RS/PS/ES uchun `privateKey` (PEM)."""
    alg = (cfg.get("algorithm") or "HS256").upper()
    if alg not in _HS and alg not in _ASYM:
        raise ValueError(f"JWT algoritmi qo'llab-quvvatlanmaydi: {alg} ({', '.join(JWT_ALGORITHMS)})")
    try:
        payload = json.loads(replace_variables(cfg.get("payload") or "{}", variables))
        extra = json.loads(replace_variables(cfg.get("header") or "{}", variables))
    except json.JSONDecodeError as e:
        raise ValueError(f"JWT payload/header JSON noto'g'ri: {e}") from e
    header = {"alg": alg, "typ": "JWT", **extra}
    signing = _b64url(json.dumps(header, separators=(",", ":")).encode()) + "." + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    if alg in _HS:
        secret = replace_variables(cfg.get("secret", ""), variables)
        key = base64.b64decode(secret) if cfg.get("secretIsBase64") else secret.encode()
        sig = hmac.new(key, signing.encode(), _HS[alg]).digest()
    else:
        pem = replace_variables(cfg.get("privateKey", ""), variables)
        if not pem.strip():
            raise ValueError(f"{alg} uchun private key (PEM) kiritilmagan")
        sig = _sign_asym(alg, pem, replace_variables(cfg.get("passphrase", ""), variables), signing.encode())
    return signing + "." + _b64url(sig)


def hawk_header(cfg, method, url, payload=None, content_type="", ts=None, nonce=None):
    """Hawk `Authorization` sarlavhasi (sha256/sha1; ixtiyoriy payload hash, ext, app, dlg)."""
    algo = (cfg.get("algorithm") or "sha256").lower()
    if algo not in ("sha256", "sha1"):
        raise ValueError("Hawk algoritmi: sha256 yoki sha1")
    hid, key = cfg.get("id", ""), cfg.get("key", "")
    if not hid or not key:
        raise ValueError("Hawk: Auth ID va Auth Key kerak")
    u = urlsplit(url)
    ts = str(ts or cfg.get("timestamp") or int(time.time()))
    nonce = nonce or cfg.get("nonce") or base64.urlsafe_b64encode(os.urandom(6)).decode().rstrip("=")
    port = u.port or (443 if u.scheme == "https" else 80)
    resource = (u.path or "/") + ("?" + u.query if u.query else "")
    digest = getattr(hashlib, algo)
    phash = ""
    if str(cfg.get("includePayloadHash", "")).lower() in ("1", "true", "yes", "on") and payload is not None:
        ctype = (content_type or "").split(";")[0].strip().lower()
        phash = base64.b64encode(digest(b"hawk.1.payload\n" + ctype.encode() + b"\n" + (payload if isinstance(payload, bytes) else b"") + b"\n").digest()).decode()
    ext = (cfg.get("ext") or "")
    ext_n = ext.replace("\\", "\\\\").replace("\n", "\\n")
    lines = ["hawk.1.header", ts, nonce, method.upper(), resource, (u.hostname or "").lower(), str(port), phash, ext_n]
    if cfg.get("app"):
        lines += [cfg["app"], cfg.get("dlg") or ""]
    mac = base64.b64encode(hmac.new(key.encode(), ("\n".join(lines) + "\n").encode(), digest).digest()).decode()
    q = lambda k, v: f'{k}="{v}"'  # noqa: E731
    parts = [q("id", hid), q("ts", ts), q("nonce", nonce)] + ([q("hash", phash)] if phash else []) + ([q("ext", ext.replace(chr(92), chr(92) * 2).replace('"', '\\"'))] if ext else []) + [q("mac", mac)]
    if cfg.get("app"):
        parts += [q("app", cfg["app"])] + ([q("dlg", cfg["dlg"])] if cfg.get("dlg") else [])
    return "Hawk " + ", ".join(parts)


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
    elif t == "bearer":
        headers["Authorization"] = "Bearer " + sub("token")
    elif t == "basic":
        headers["Authorization"] = "Basic " + base64.b64encode((sub("username") + ":" + sub("password")).encode("utf-8")).decode()
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
    elif t == "ntlm":
        return url, NTLMAuth(sub("username"), sub("password"), sub("domain"), sub("workstation"))
    elif t == "hawk":
        full = str(httpx.URL(url).copy_merge_params(params)) if params else url
        ctype = next((val for k, val in headers.items() if k.lower() == "content-type"), "")
        alias = {"id": "authId", "key": "authKey", "ext": "extraData", "app": "appId", "dlg": "delegation"}      # Postman kalitlari ham qabul qilinadi
        hc = {k: sub(alias.get(k, k)) or sub(k) for k in ("id", "key", "algorithm", "ext", "app", "dlg", "nonce", "timestamp", "includePayloadHash")}
        headers["Authorization"] = hawk_header(hc, method, full, payload, ctype)
    return url, None
