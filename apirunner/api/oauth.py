"""OAuth 2.0: token olish/yangilash (server tomonida — CORS yo'q, sir brauzer tarmog'iga chiqmaydi) va redirect sahifasi."""
import base64
import time
from urllib.parse import urlsplit

import httpx
from flask import Blueprint, Response, jsonify, request

from ..core.variables import replace_variables

bp = Blueprint("oauth", __name__)

GRANTS = ("client_credentials", "password", "authorization_code", "refresh_token")

CALLBACK_HTML = """<!doctype html><meta charset="utf-8"><title>OAuth</title><body style="font:14px sans-serif;padding:24px">
<p>Avtorizatsiya yakunlandi — oyna yopilmoqda…</p>
<script>
try { window.opener && window.opener.postMessage({ type: 'apirunner-oauth', search: location.search, hash: location.hash }, location.origin) } catch (e) {}
setTimeout(function () { window.close() }, 300)
</script>"""


@bp.get("/oauth/callback")
def callback():
    return Response(CALLBACK_HTML, content_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@bp.post("/api/oauth2/token")
def token():
    """{grant_type, token_url, client_id, client_secret, scope, username, password, code, redirect_uri, code_verifier,
    refresh_token, client_auth: header|body, variables} -> {ok, status, token:{access_token,...,expires_at}}"""
    d = request.get_json(silent=True) or {}
    v = d.get("variables") or {}
    f = lambda k: replace_variables(d.get(k) or "", v).strip()  # noqa: E731
    grant, url = f("grant_type"), f("token_url")
    if grant not in GRANTS:
        return jsonify({"error": f"Grant turi noto'g'ri: {grant or '—'}"}), 400
    if urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).netloc:
        return jsonify({"error": "Token URL (http/https) kiriting"}), 400
    form = {"grant_type": grant}
    for src, dst in (("scope", "scope"), ("username", "username"), ("password", "password"), ("code", "code"),
                     ("redirect_uri", "redirect_uri"), ("code_verifier", "code_verifier"), ("refresh_token", "refresh_token")):
        if f(src):
            form[dst] = f(src)
    headers = {"Accept": "application/json"}
    cid, secret = f("client_id"), f("client_secret")
    if d.get("client_auth", "header") == "header" and cid:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{cid}:{secret}".encode()).decode()
    else:
        if cid:
            form["client_id"] = cid
        if secret:
            form["client_secret"] = secret
    try:
        with httpx.Client(timeout=30, verify=bool(d.get("ssl_verify", True))) as c:
            r = c.post(url, data=form, headers=headers)
    except httpx.HTTPError as e:
        return jsonify({"error": f"Token so'rovi bajarilmadi: {e}"}), 502
    try:
        body = r.json()
    except ValueError:
        body = {"raw": r.text[:2000]}
    if r.status_code >= 400 or "access_token" not in body:
        msg = body.get("error_description") or body.get("error") or f"HTTP {r.status_code}"
        return jsonify({"error": f"Token olinmadi: {msg}", "status": r.status_code, "body": body}), 400
    if isinstance(body.get("expires_in"), (int, float)):
        body["expires_at"] = int(time.time() + body["expires_in"])
    return jsonify({"ok": True, "status": r.status_code, "token": body})
