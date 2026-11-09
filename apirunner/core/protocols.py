"""WebSocket va SSE mijozlari: brauzer o'rniga SERVER ulanadi (custom header, auth, subprotokol, TLS sozlamalari) va hodisalarni
xotiradagi jurnalga yozadi; UI ularni SSE orqali oqim sifatida oladi (`/api/protocols/<id>/stream`). Xabar yuborish — POST.

Hodisa: {seq, ts, type, ...}. WS `type`: connecting | open | message | close | error | reconnecting | closed.
SSE `type`: connecting | open | event | comment | error | reconnecting | closed.
"""
import asyncio
import base64
import binascii
import json
import ssl as ssl_mod
import threading
import time
import uuid

import httpx

MAX_EVENTS = 5000
MAX_MESSAGE = 16 * 1024 * 1024
KEEP_SESSIONS = 20
STABLE_SECONDS = 2.0                                       # shundan uzoq ochiq turgan ulanish "barqaror": qayta ulanish urinishlari hisobi nolga qaytadi


def _limit(rc):
    """Qayta ulanishning maksimal urinishlari: sukut 5; 0 — cheksiz."""
    v = rc.get("max_attempts")
    return 5 if v is None else int(v)


class ProtocolError(ValueError):
    pass


def decode_payload(kind, data, encoding=None):
    """UI yuborgan xabar -> (str | bytes). kind: text | json | binary (encoding: base64 | hex)."""
    if kind == "binary":
        try:
            raw = bytes.fromhex("".join((data or "").split())) if encoding == "hex" else base64.b64decode(data or "", validate=True)
        except (ValueError, binascii.Error) as e:
            raise ProtocolError("Binary xabar noto'g'ri (%s)" % ("hex" if encoding == "hex" else "base64")) from e
        if len(raw) > MAX_MESSAGE:
            raise ProtocolError("Xabar 16 MB dan katta")
        return raw
    text = data if isinstance(data, str) else json.dumps(data)
    if kind == "json":
        try:
            json.loads(text)
        except ValueError as e:
            raise ProtocolError("JSON noto'g'ri: %s" % e) from e
    if len(text.encode("utf-8")) > MAX_MESSAGE:
        raise ProtocolError("Xabar 16 MB dan katta")
    return text


class Session:
    kind = "base"

    def __init__(self, cfg):
        self.id = uuid.uuid4().hex[:12]
        self.cfg = cfg
        self.created = time.time()
        self.events = []
        self.cond = threading.Condition()
        self.status = "connecting"
        self.closing = False
        self.thread = None
        self.counts = {"in": 0, "out": 0, "bytes_in": 0, "bytes_out": 0, "errors": 0}
        self.dropped = 0                                   # MAX_EVENTS dan oshib tashlab yuborilgan eski hodisalar soni

    # ── jurnal ──
    def emit(self, type_, **data):
        with self.cond:
            ev = {"seq": self.dropped + len(self.events), "ts": time.time(), "type": type_, **data}
            self.events.append(ev)
            if len(self.events) > MAX_EVENTS:
                del self.events[:len(self.events) - MAX_EVENTS]
                self.dropped = ev["seq"] + 1 - len(self.events)
            if type_ == "error":
                self.counts["errors"] += 1
            self.cond.notify_all()
        return ev

    def snapshot(self, start=0):
        with self.cond:
            return [e for e in self.events if e["seq"] >= start]

    def stream(self, start=0):
        """Generator: hodisa (dict) yoki None (ping). Sessiya tugagach (`closed` hodisasidan keyin) to'xtaydi."""
        seq = start
        while True:
            with self.cond:
                while True:
                    pending = [e for e in self.events if e["seq"] >= seq]
                    if pending or self.status == "closed":
                        break
                    if not self.cond.wait(timeout=15):
                        pending = []
                        break
            if not pending:
                if self.status == "closed" and seq >= self.dropped + len(self.events):
                    return
                yield None
                continue
            for ev in pending:
                yield ev
                seq = ev["seq"] + 1
                if ev["type"] == "closed":
                    return

    def summary(self):
        return {"id": self.id, "kind": self.kind, "status": self.status, "url": self.cfg.get("url"), "created": self.created, "counts": dict(self.counts),
                "next_seq": self.dropped + len(self.events), "dropped": self.dropped}

    def start(self):
        self.thread = threading.Thread(target=self._guard, daemon=True)
        self.thread.start()

    def _guard(self):
        try:
            self._run()
        except Exception as exc:                    # noqa: BLE001 — oqim yo'qolmasin
            self.emit("error", message="Ichki xato: %s" % exc)
        finally:
            self.status = "closed"
            self.emit("closed")

    def close(self):
        self.closing = True
        self._interrupt()

    def _interrupt(self):
        pass

    def _reconnect_delay(self, attempt, base_ms):
        return min(30.0, (base_ms / 1000.0) * (2 ** max(0, attempt - 1)))

    def _sleep(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self.closing:
            time.sleep(0.05)


# ── WebSocket ──
class WsSession(Session):
    kind = "ws"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.loop = None
        self.outq = None
        self.stop_evt = None

    def _ssl(self):
        url = self.cfg["url"]
        if not url.lower().startswith("wss://"):
            return None
        if self.cfg.get("ssl_verify", True):
            return True
        ctx = ssl_mod.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl_mod.CERT_NONE
        return ctx

    def _run(self):
        asyncio.run(self._main())

    def _interrupt(self):
        if self.loop and self.stop_evt:
            try:
                self.loop.call_soon_threadsafe(self.stop_evt.set)
            except RuntimeError:
                pass

    async def _main(self):
        from websockets.asyncio.client import connect
        self.loop = asyncio.get_running_loop()
        self.outq = asyncio.Queue()
        self.stop_evt = asyncio.Event()
        if self.closing:
            self.stop_evt.set()
        rc = self.cfg.get("reconnect") or {}
        attempt = 0
        while not self.stop_evt.is_set():
            self.status = "connecting"
            self.emit("connecting", attempt=attempt)
            abnormal = True
            try:
                kw = dict(additional_headers=self.cfg.get("headers") or {}, subprotocols=self.cfg.get("subprotocols") or None, ssl=self._ssl(), max_size=MAX_MESSAGE,
                          open_timeout=float(self.cfg.get("timeout") or 30), ping_interval=self.cfg.get("ping_interval") or None, compression=None)
                async with connect(self.cfg["url"], **kw) as ws:
                    self.status = "open"
                    opened_at = time.monotonic()
                    resp = getattr(ws, "response", None)
                    self.emit("open", subprotocol=ws.subprotocol, status=getattr(resp, "status_code", 101), headers=dict(resp.headers) if resp is not None else {})
                    abnormal = await self._pump(ws)
                    if time.monotonic() - opened_at >= STABLE_SECONDS:
                        attempt = 0                                  # barqaror ulanish bo'lgan edi — urinishlar hisobi yangilanadi
                    code = getattr(ws, "close_code", None)
                    self.emit("close", code=code, reason=getattr(ws, "close_reason", "") or "", clean=not abnormal)
            except Exception as exc:                # noqa: BLE001
                self.emit("error", message=_ws_err(exc))
            self.outq = asyncio.Queue()                 # eski navbatdagi (yuborilmagan) xabarlar qayta ulanishda yuborilmasin
            if self.stop_evt.is_set() or not rc.get("enabled"):
                break
            if not abnormal and not rc.get("always"):
                break
            attempt += 1
            limit = _limit(rc)
            if limit and attempt > limit:
                self.emit("error", message="Qayta ulanish urinishlari tugadi (%s)" % limit)
                break
            delay = self._reconnect_delay(attempt, int(rc.get("delay_ms") or 1000))
            self.status = "reconnecting"
            self.emit("reconnecting", attempt=attempt, delay=delay)
            try:
                await asyncio.wait_for(self.stop_evt.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def _pump(self, ws):
        """Qabul/yuborish/to'xtatish. Qaytaradi: abnormal (True = kutilmagan uzilish)."""
        async def recv():
            async for msg in ws:
                binary = isinstance(msg, (bytes, bytearray))
                self.counts["in"] += 1
                size = len(msg)
                self.counts["bytes_in"] += size
                self.emit("message", dir="in", kind="binary" if binary else "text", size=size, data=base64.b64encode(msg).decode() if binary else msg)

        async def send():
            while True:
                payload = await self.outq.get()
                await ws.send(payload)
                binary = isinstance(payload, (bytes, bytearray))
                size = len(payload) if binary else len(payload.encode("utf-8"))
                self.counts["out"] += 1
                self.counts["bytes_out"] += size
                self.emit("message", dir="out", kind="binary" if binary else "text", size=size, data=base64.b64encode(payload).decode() if binary else payload)

        tasks = [asyncio.create_task(recv()), asyncio.create_task(send()), asyncio.create_task(self.stop_evt.wait())]
        abnormal = False
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if t is tasks[2]:
                    continue
                exc = t.exception()
                if exc is not None:
                    from websockets.exceptions import ConnectionClosedOK
                    if not isinstance(exc, ConnectionClosedOK):
                        abnormal = True
                        self.emit("error", message=_ws_err(exc))
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await ws.close(1000)
            except Exception:                       # noqa: BLE001
                pass
        if not abnormal and not self.stop_evt.is_set():
            code = getattr(ws, "close_code", None)
            abnormal = code not in (1000, 1001, None)
        return abnormal and not self.stop_evt.is_set()

    def send(self, payload):
        if self.status != "open" or not self.loop or self.outq is None:
            raise ProtocolError("Ulanish ochiq emas")
        self.loop.call_soon_threadsafe(self.outq.put_nowait, payload)


def _ws_err(exc):
    name = type(exc).__name__
    msg = str(exc) or name
    if name == "InvalidStatus":
        resp = getattr(exc, "response", None)
        body = bytes(getattr(resp, "body", b"") or b"")[:300].decode("utf-8", "replace").strip()
        return "Server ulanishni rad etdi: HTTP %s%s" % (getattr(resp, "status_code", "?"), (" — " + body) if body else "")
    if name in ("InvalidURI",):
        return "WebSocket manzili noto'g'ri: %s" % msg
    if name == "ConnectionClosedError":
        return "Ulanish kutilmaganda uzildi: %s" % msg
    if isinstance(exc, (OSError, TimeoutError)):
        return "Ulanib bo'lmadi: %s" % msg
    return msg


# ── SSE ──
class SseSession(Session):
    kind = "sse"

    def __init__(self, cfg):
        super().__init__(cfg)
        self._resp = None
        self.last_id = cfg.get("last_event_id") or ""
        self.retry_ms = None

    def _interrupt(self):
        r = self._resp
        if r is not None:
            try:
                r.close()
            except Exception:                       # noqa: BLE001
                pass

    def _run(self):
        rc = self.cfg.get("reconnect") or {}
        attempt = 0
        while not self.closing:
            self.status = "connecting"
            self.emit("connecting", attempt=attempt)
            retry = False
            started = time.monotonic()
            try:
                retry = self._once()
                if retry == "streamed" and time.monotonic() - started >= STABLE_SECONDS:
                    attempt = 0
            except httpx.HTTPError as exc:
                if not self.closing:
                    self.emit("error", message=_http_err(exc))
                retry = True
            except Exception as exc:                # noqa: BLE001
                if not self.closing:
                    self.emit("error", message=str(exc))
                retry = True
            if self.closing or not retry or not rc.get("enabled"):
                break
            attempt += 1
            limit = _limit(rc)
            if limit and attempt > limit:
                self.emit("error", message="Qayta ulanish urinishlari tugadi (%s)" % limit)
                break
            base = self.retry_ms if self.retry_ms is not None else int(rc.get("delay_ms") or 1000)       # server `retry:` ko'rsatgan bo'lsa shu
            delay = base / 1000.0 if self.retry_ms is not None else self._reconnect_delay(attempt, base)
            self.status = "reconnecting"
            self.emit("reconnecting", attempt=attempt, delay=delay, last_event_id=self.last_id)
            self._sleep(delay)

    def _once(self):
        """Bitta ulanish. Qaytaradi: 'streamed' (oqim ochilgan edi) | True (qayta urinsa bo'ladi) | False."""
        cfg = self.cfg
        headers = {**(cfg.get("headers") or {})}
        headers.setdefault("Accept", "text/event-stream")
        headers.setdefault("Cache-Control", "no-cache")
        if self.last_id:
            headers["Last-Event-ID"] = self.last_id
        t = float(cfg.get("timeout") or 30)
        with httpx.Client(timeout=httpx.Timeout(connect=t, read=None, write=t, pool=t), verify=bool(cfg.get("ssl_verify", True)), follow_redirects=True) as client:
            with client.stream(cfg.get("method") or "GET", cfg["url"], headers=headers, content=cfg.get("body") or None, auth=cfg.get("auth")) as r:
                self._resp = r
                ctype = r.headers.get("content-type", "")
                if r.status_code == 204:
                    self.emit("error", message="Server 204 qaytardi — oqim yopildi (qayta ulanilmaydi)")
                    return False
                if r.status_code >= 400 or not (200 <= r.status_code < 300):
                    body = r.read()[:500].decode("utf-8", "replace")
                    self.emit("error", message="Server HTTP %s qaytardi%s" % (r.status_code, (": " + body.strip()) if body.strip() else ""), status=r.status_code)
                    return r.status_code >= 500
                self.status = "open"
                self.emit("open", status=r.status_code, headers=dict(r.headers), content_type=ctype, warning=None if "text/event-stream" in ctype.lower() else "Content-Type text/event-stream emas: " + (ctype or "yo'q"))
                self._parse(r)
                self.emit("close", clean=True)
                return "streamed"

    def _parse(self, r):
        data, etype, eid = [], "", None
        for line in r.iter_lines():
            if self.closing:
                return
            if line == "":
                if data:
                    d = "\n".join(data)
                    if eid is not None:
                        self.last_id = eid
                    self.counts["in"] += 1
                    self.counts["bytes_in"] += len(d.encode("utf-8"))
                    self.emit("event", event=etype or "message", id=self.last_id or None, data=d, size=len(d.encode("utf-8")))
                data, etype, eid = [], "", None
                continue
            if line.startswith(":"):
                self.emit("comment", data=line[1:].lstrip())
                continue
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "data":
                data.append(value)
            elif field == "event":
                etype = value
            elif field == "id" and "\0" not in value:
                eid = value
            elif field == "retry" and value.isdigit():
                self.retry_ms = int(value)


def _http_err(exc):
    if isinstance(exc, httpx.ConnectError):
        return "Ulanib bo'lmadi: %s" % exc
    if isinstance(exc, httpx.ConnectTimeout):
        return "Ulanish vaqti tugadi"
    if isinstance(exc, (httpx.ReadError, httpx.RemoteProtocolError)):
        return "Oqim uzildi: %s" % exc
    return str(exc) or type(exc).__name__


class ProtocolManager:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()

    def start(self, kind, cfg):
        s = (WsSession if kind == "ws" else SseSession)(cfg)
        with self.lock:
            self.sessions[s.id] = s
            done = [k for k, v in self.sessions.items() if v.status == "closed"]
            for k in done[:max(0, len(self.sessions) - KEEP_SESSIONS)]:
                self.sessions.pop(k, None)
        s.start()
        return s

    def get(self, sid):
        with self.lock:
            return self.sessions.get(sid)

    def shutdown(self):
        for s in list(self.sessions.values()):
            s.close()
