"""Lokal xavfsizlik: Host/Origin tekshiruvi (DNS rebinding) va sessiya tokeni (CSRF / begona jarayon)."""
import hmac
import secrets
from urllib.parse import urlsplit

from flask import jsonify, request

ALLOWED_HOSTNAMES = {"127.0.0.1", "localhost", "::1"}
PUBLIC_PATHS = ("/", "/favicon.ico")


def new_token():
    return secrets.token_urlsafe(32)


def _hostname(netloc):
    try:
        return (urlsplit("//" + netloc).hostname or "").lower()
    except ValueError:
        return ""


def install(app):
    @app.before_request
    def guard():
        if _hostname(request.host) not in ALLOWED_HOSTNAMES:
            return jsonify({"error": "Host ruxsat etilmagan"}), 403
        origin = request.headers.get("Origin")
        if origin and origin != "null" and _hostname(urlsplit(origin).netloc) not in ALLOWED_HOSTNAMES:
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
