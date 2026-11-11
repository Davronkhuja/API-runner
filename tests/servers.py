"""Lokal test serverlari: WebSocket (websockets), SSE (Flask) va GraphQL (graphql-core). Tashqi tarmoq kerak emas."""
import asyncio
import json
import threading
import time

from flask import Flask, Response, jsonify, request
from werkzeug.serving import make_server

# ── WebSocket ──
WS_SECRET = "Bearer s3cret"


class WsServer:
    def __init__(self):
        self.connections = 0
        self.received = []
        self.loop = None
        self.url = None
        self._ready = threading.Event()
        self._stop = None

    def start(self):
        threading.Thread(target=lambda: asyncio.run(self._main()), daemon=True).start()
        assert self._ready.wait(10), "WS server ishga tushmadi"
        return self

    async def _handler(self, ws):
        path = ws.request.path
        self.connections += 1
        try:
            if path.startswith("/headers"):
                await ws.send(json.dumps({"headers": {k: v for k, v in ws.request.headers.items()}, "subprotocol": ws.subprotocol, "path": path}))
            elif path.startswith("/greet"):
                await ws.send("hello")
            elif path.startswith("/binary"):
                await ws.send(b"\x00\x01\x02\xff")
            elif path.startswith("/drop"):
                await ws.send("about to drop")
                ws.transport.abort()                              # kutilmagan uzilish (1006)
                return
            elif path.startswith("/ticker"):
                for i in range(1000):
                    await ws.send(json.dumps({"tick": i}))
                    await asyncio.sleep(0.03)
                return
            elif path.startswith("/bye"):
                n = 0
                async for _m in ws:
                    n += 1
                    if n >= 1:
                        await ws.close(4001, "bye now")
                        return
                return
            async for m in ws:
                self.received.append(m)
                await ws.send(m)
        except Exception:                                         # noqa: BLE001 — uzilgan ulanish testni to'xtatmasin
            pass

    def _process_request(self, connection, request):
        if request.path.startswith("/secure") and request.headers.get("Authorization") != WS_SECRET:
            return connection.respond(401, "unauthorized\n")
        if request.path.startswith("/forbidden"):
            return connection.respond(403, "no\n")
        return None

    async def _main(self):
        from websockets.asyncio.server import serve
        self.loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        async with serve(self._handler, "127.0.0.1", 0, select_subprotocol=lambda conn, offered: next((p for p in offered if p in ("chat", "json.v1")), None), process_request=self._process_request) as server:
            port = server.sockets[0].getsockname()[1]
            self.url = f"ws://127.0.0.1:{port}"
            self._ready.set()
            await self._stop.wait()

    def stop(self):
        if self.loop and self._stop:
            self.loop.call_soon_threadsafe(self._stop.set)


# ── SSE ──
def build_sse_app():
    app = Flask("sse")
    state = {"seen": [], "conn": 0}

    def sse(gen, status=200):
        return Response(gen, status=status, content_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.route("/sse/basic")
    def basic():
        def g():
            yield ": hello comment\n\n"
            yield "retry: 100\n\n"
            yield "id: 1\nevent: tick\ndata: one\n\n"
            yield "id: 2\ndata: line a\ndata: line b\n\n"
            yield 'data: {"k": 1}\n\n'
        return sse(g())

    @app.route("/sse/crlf")
    def crlf():
        return sse(iter(["id: 7\r\nevent: win\r\ndata: x\r\n\r\n", "data: y\r\n\r\n"]))

    @app.route("/sse/resume")
    def resume():
        last = request.headers.get("Last-Event-ID", "")
        state["seen"].append(last)
        n = int(last or 0)

        def g():
            yield "retry: 50\n\n"
            for i in range(n + 1, n + 3):
                yield f"id: {i}\ndata: msg {i}\n\n"
        return sse(g())

    @app.route("/sse/seen")
    def seen():
        return jsonify(state["seen"])

    @app.route("/sse/headers")
    def headers():
        payload = json.dumps({k: v for k, v in request.headers.items()})
        return sse(iter(["data: " + payload + "\n\n"]))

    @app.route("/sse/post", methods=["POST"])
    def post():
        body = request.get_data(as_text=True)
        return sse(iter([f"data: {body}\n\n"]))

    @app.route("/sse/secure")
    def secure():
        if request.headers.get("Authorization") != "Bearer s3cret":
            return Response("nope", status=401)
        return sse(iter(["data: secret ok\n\n"]))

    @app.route("/sse/status/<int:code>")
    def status(code):
        return Response("boom body", status=code, content_type="text/plain")

    @app.route("/sse/plain")
    def plain():
        return Response("data: not really sse\n\n", content_type="text/plain")

    @app.route("/sse/forever")
    def forever():
        def g():
            i = 0
            while True:
                i += 1
                yield f"id: {i}\ndata: tick {i}\n\n"
                time.sleep(0.03)
        return sse(g())

    @app.route("/sse/flaky")
    def flaky():
        state["conn"] += 1
        if state["conn"] <= 1:
            return Response("down", status=503)
        return sse(iter(["id: 1\ndata: recovered\n\n"]))

    @app.route("/sse/reset")
    def reset():
        state["seen"].clear()
        state["conn"] = 0
        return "ok"
    return app


# ── GraphQL ──
SDL = '''
"Foydalanuvchi roli"
enum Role { ADMIN USER }
interface Node { id: ID! }
"Tizim foydalanuvchisi"
type User implements Node { id: ID! name: String! email: String role: Role! posts: [Post!]! }
type Post { id: ID! title: String! author: User! }
union SearchResult = User | Post
input NewUser { name: String! email: String role: Role = USER }
type Query {
  "Salomlashish"
  hello(name: String = "world"): String!
  user(id: ID!): User
  users(limit: Int = 10, role: Role): [User!]!
  search(term: String!): [SearchResult!]!
}
type Mutation { addUser(input: NewUser!): User! }
type Subscription { ticks: Int }
schema { query: Query mutation: Mutation subscription: Subscription }
'''
USERS = [{"id": "1", "name": "Ali", "email": "ali@example.com", "role": "ADMIN"}, {"id": "2", "name": "Vali", "email": None, "role": "USER"}]


def build_graphql_app():
    from graphql import build_schema, graphql_sync
    schema = build_schema(SDL)
    app = Flask("gql")
    seen = []

    def posts_of(u):
        return [{"id": f"p{u['id']}", "title": f"Post of {u['name']}", "author": u}]
    for u in USERS:
        u["posts"] = posts_of(u)
    store = list(USERS)

    root = {
        "hello": lambda info, name="world": f"Hello, {name}!",
        "user": lambda info, id: next((u for u in store if u["id"] == id), None),
        "users": lambda info, limit=10, role=None: [u for u in store if role is None or u["role"] == role][:limit],
        "search": lambda info, term: [u for u in store if term.lower() in u["name"].lower()],
        "addUser": lambda info, input: (lambda u: (store.append(u), u)[1])({"id": str(len(store) + 1), "name": input["name"], "email": input.get("email"), "role": input.get("role", "USER"), "posts": []}),
    }

    def run(secure=False, introspection=True):
        seen.append({"headers": {k: v for k, v in request.headers.items()}, "path": request.path})
        if secure and request.headers.get("Authorization") != "Bearer s3cret":
            return jsonify({"errors": [{"message": "Unauthorized"}]}), 401
        d = request.get_json(silent=True) or {}
        q = d.get("query") or ""
        if not introspection and "__schema" in q:
            return jsonify({"errors": [{"message": "GraphQL introspection is not allowed"}]})
        res = graphql_sync(schema, q, root_value=root, variable_values=d.get("variables"), operation_name=d.get("operationName"))
        out = {}
        if res.data is not None:
            out["data"] = res.data
        if res.errors:
            out["errors"] = [e.formatted for e in res.errors]
        return jsonify(out)

    app.add_url_rule("/graphql", "gql", lambda: run(), methods=["POST"])
    app.add_url_rule("/graphql-secure", "gqls", lambda: run(secure=True), methods=["POST"])
    app.add_url_rule("/graphql-noint", "gqln", lambda: run(introspection=False), methods=["POST"])
    app.add_url_rule("/seen", "seen", lambda: jsonify(seen))
    return app


class FlaskServer:
    def __init__(self, app):
        self.srv = make_server("127.0.0.1", 0, app, threaded=True)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_port}"

    def stop(self):
        self.srv.shutdown()
