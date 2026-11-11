"""Lokal xavfsizlik: Host/Origin tekshiruvi (DNS rebinding) va sessiya tokeni (CSRF / begona jarayon)."""
import hmac
import logging
import re
import secrets
from urllib.parse import urlsplit

from flask import jsonify, request

ALLOWED_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}
PUBLIC_PATHS = ("/", "/legacy", "/favicon.ico", "/apple-touch-icon.png", "/oauth/callback")


def host_allowed(name):
    """Loopback nomlar; `*.localhost` (RFC 6761) brauzerda doim loopback'ga hal qilinadi — DNS rebinding mumkin emas (Caddy: api-runner.localhost)."""
    return name in ALLOWED_HOSTNAMES or name.endswith(".localhost")


def new_token():
    return secrets.token_urlsafe(32)


def _hostname(netloc):
    try:
        return (urlsplit("//" + netloc).hostname or "").lower()
    except ValueError:
        return ""


SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
                    "Content-Security-Policy": "frame-ancestors 'none'; base-uri 'self'; object-src 'none'; form-action 'self'"}
_TOKEN_RE = re.compile(r"([?&]token=)[^&\s\"]+")


class _RedactToken(logging.Filter):
    """EventSource tokenni URL'da yuboradi (header qo'ya olmaydi): kirish jurnaliga (werkzeug) tushib qolmasin."""
    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(_TOKEN_RE.sub(r"\1***", a) if isinstance(a, str) else a for a in record.args)
        return True


def install(app):
    logging.getLogger("werkzeug").addFilter(_RedactToken())

    @app.after_request
    def headers(resp):
        for k, v in SECURITY_HEADERS.items():
            resp.headers.setdefault(k, v)
        return resp

    @app.before_request
    def guard():
        if not host_allowed(_hostname(request.host)):
            return jsonify({"error": "Host ruxsat etilmagan"}), 403
        origin = request.headers.get("Origin")
        # Origin bo'lsa — aynan shu server (sxema/host/port): boshqa lokal servis yoki sandbox ("null") sahifasi so'rov yubora olmasin
        if origin and origin.split("://", 1)[-1].lower() != request.host.lower():
            return jsonify({"error": "Origin ruxsat etilmagan"}), 403
        if request.path in PUBLIC_PATHS or request.path.startswith("/static/"):
            return None
        given = request.headers.get("X-Session-Token") or request.args.get("token") or ""
        if not hmac.compare_digest(given, app.config["SESSION_TOKEN"]):
            return jsonify({"error": "Sessiya tokeni noto'g'ri yoki yo'q"}), 401
        return None


# Brauzerdagi eski UI'ni o'zgartirmasdan token qo'shish: fetch va EventSource o'rami.
BOOTSTRAP_JS = """<script>
window.__API_TOKEN__ = %s;
(function () {
  const T = window.__API_TOKEN__;
  const _fetch = window.fetch;
  window.fetch = function (input, init) {
    init = init || {};
    const h = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
    h.set('X-Session-Token', T);
    init.headers = h;
    return _fetch.call(this, input, init);
  };
  const _ES = window.EventSource;
  window.EventSource = function (url, cfg) {
    return new _ES(url + (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(T), cfg);
  };
  window.EventSource.prototype = _ES.prototype;
})();
</script>"""
