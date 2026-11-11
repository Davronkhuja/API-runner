"""Proxy capture: lokal HTTP proxy. Orqali o'tgan HTTP so'rovlar yozib olinadi va collection'ga saqlanadi.
HTTPS (CONNECT) faqat tunnel qilinadi — shifrlangan trafikni o'qimaymiz (MITM sertifikat yo'q), jurnalda faqat host ko'rinadi."""
import select
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import httpx

MAX_LOG, MAX_BODY = 500, 1_000_000
HOP = {"connection", "proxy-connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade", "content-length", "content-encoding"}


class ProxyServer:
    def __init__(self, host="127.0.0.1", port=0):
        self.host, self.log, self.seq, self.lock = host, [], 0, threading.Lock()
        proxy = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _forward(self):
                t0 = time.time()
                url = self.path
                if not url.startswith(("http://", "https://")):
                    self.send_error(400, "Proxy: absolyut URL kerak")
                    return
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                headers = [(k, v) for k, v in self.headers.items() if k.lower() not in HOP and k.lower() != "host"]
                entry = {"ts": t0, "method": self.command, "url": url, "kind": "http", "request_headers": headers, "request_body": body[:MAX_BODY].decode("utf-8", "replace")}
                try:
                    with httpx.Client(follow_redirects=False, timeout=30, trust_env=False) as c:
                        r = c.request(self.command, url, headers=headers, content=body or None)
                except httpx.HTTPError as e:
                    entry.update(status=502, error=str(e), ms=round((time.time() - t0) * 1000), response_headers=[], response_body="")
                    proxy._record(entry)
                    self.send_error(502, "Proxy: " + str(e)[:200])
                    return
                data = r.content
                entry.update(status=r.status_code, ms=round((time.time() - t0) * 1000), response_headers=[(k, v) for k, v in r.headers.items() if k.lower() not in HOP],
                             response_body=data[:MAX_BODY].decode("utf-8", "replace"))
                proxy._record(entry)
                self.send_response(r.status_code)
                for k, v in entry["response_headers"]:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(data)

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = do_OPTIONS = _forward

            def do_CONNECT(self):
                host, _, port = self.path.partition(":")
                t0 = time.time()
                try:
                    up = socket.create_connection((host, int(port or 443)), timeout=10)
                except (OSError, ValueError) as e:
                    proxy._record({"ts": t0, "method": "CONNECT", "url": self.path, "kind": "tunnel", "status": 502, "error": str(e), "ms": 0})
                    self.send_error(502, "Proxy: ulanib bo'lmadi")
                    return
                self.send_response(200, "Connection Established")
                self.end_headers()
                proxy._record({"ts": t0, "method": "CONNECT", "url": self.path, "kind": "tunnel", "status": 200, "ms": round((time.time() - t0) * 1000)})
                socks = [self.connection, up]
                try:
                    while True:
                        r, _, x = select.select(socks, [], socks, 30)
                        if x or not r:
                            break
                        for s in r:
                            d = s.recv(65536)
                            if not d:
                                return
                            (up if s is self.connection else self.connection).sendall(d)
                finally:
                    up.close()
                    self.close_connection = True

        self.srv = ThreadingHTTPServer((host, int(port or 0)), H)
        self.srv.daemon_threads = True
        self.port = self.srv.server_address[1]
        self.thread = None

    @property
    def url(self):
        return f"http://{self.host}:{self.port}"

    def start(self):
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _record(self, e):
        with self.lock:
            e["seq"] = self.seq
            self.seq += 1
            self.log.append(e)
            del self.log[:-MAX_LOG]

    def entries(self, start=0, full=False):
        with self.lock:
            rows = [e for e in self.log if e["seq"] >= start]
        return rows if full else [{k: v for k, v in e.items() if k in ("seq", "ts", "method", "url", "kind", "status", "ms", "error")} for e in rows]

    def clear(self):
        with self.lock:
            self.log.clear()


def entries_to_items(entries):
    """Ushlangan HTTP yozuvlarni Postman so'rov elementlariga (javob namunasi bilan) aylantiradi."""
    from .storage import model
    out = []
    for e in entries:
        if e.get("kind") != "http":
            continue
        u = urlsplit(e["url"])
        raw = e["url"]
        ctype = next((v for k, v in e.get("request_headers", []) if k.lower() == "content-type"), "")
        req = {"method": e["method"], "header": [{"key": k, "value": v} for k, v in e.get("request_headers", []) if k.lower() not in ("host", "content-length")],
               "url": {"raw": raw, "protocol": u.scheme, "host": u.hostname.split(".") if u.hostname else [], "path": [p for p in u.path.split("/") if p],
                       "query": [{"key": k, "value": v} for k, _, v in (p.partition("=") for p in u.query.split("&") if p)]}}
        if e.get("request_body"):
            req["body"] = {"mode": "raw", "raw": e["request_body"], "options": {"raw": {"language": "json" if "json" in ctype else "text"}}}
        out.append({"id": model.new_id(), "name": f"{e['method']} {u.path or '/'}", "request": req, "response": [{
            "id": model.new_id(), "name": f"{e.get('status')}", "originalRequest": req, "status": "", "code": e.get("status") or 0,
            "header": [{"key": k, "value": v} for k, v in e.get("response_headers", [])], "body": e.get("response_body", "")}]})
    return out


class ProxyManager:
    def __init__(self):
        self.proxy = None
        self.lock = threading.Lock()

    def start(self, port=0):
        with self.lock:
            if self.proxy:
                raise ValueError("Proxy allaqachon ishlayapti")
            try:
                self.proxy = ProxyServer(port=port).start()
            except OSError as e:
                raise ValueError(f"Port {port} band yoki ochib bo'lmadi") from e
            return self.proxy

    def stop(self):
        with self.lock:
            p, self.proxy = self.proxy, None
        if p:
            p.stop()
        return bool(p)

    stop_all = stop
