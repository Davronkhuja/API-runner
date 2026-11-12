import os
import threading
import time
import webbrowser

from flask import Flask, Response, request, send_from_directory

from .api import admin_api, importexport_api, desktop_api, monitors_api, protocols_api, proxy_api, workspaces_api, legacy, oauth, runs_api, security, workspace_api
from .core.jobs import JobManager
from .proxy import ProxyManager
from .storage.instance import InstanceLock
from .storage.prefs_migration import upgrade_safety_meta
from .monitor import MonitorStore, Scheduler
from .core.run_engine import RunManager
from .storage.cookies import CookieStore
from .core.protocols import ProtocolManager
from .mock import MockManager
from .storage.db import StateDB
from .storage.runs import RunStore
from . import __version__
from .storage import migrations
from .storage.registry import DEFAULT_ID, WorkspaceRegistry
from .storage.workspace import Workspace

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PKG_DIR)


def bind_workspace(app, ws_dir, saved_file, backup_dir, upload_dir):
    """Faol workspace'ga bog'liq hamma narsani (storage, SQLite, run/job menejerlari, cookie'lar, savat) qayta quradi. Ishga tushganda va almashtirganda."""
    ws = Workspace(ws_dir)
    result = migrations.run_all(ws, saved_file, backup_dir, __version__)       # zaxira, sonlar tekshiruvi va rollback bilan
    ext = app.extensions
    ext["workspace"] = ws
    upgrade_safety_meta(ws)
    if ext.get("instance"):
        ext["instance"].release()                       # workspace almashtirilganda eskisining sessiya qulfi qo'yib yuboriladi
    ext["instance"] = InstanceLock(ws.root, __version__, "desktop" if app.config.get("DESKTOP") else "server")
    ext["trash"] = ws.trash
    ws.trash.registry = ext.get("registry")
    ws.trash.purge_expired()                                                    # 30 kundan oshganlar tozalanadi
    ext["db"] = StateDB(os.path.join(ws.root, "state.db"))
    ext["cookies"] = CookieStore(os.path.join(ws.root, "state.db"))
    ext["runs"] = RunStore(ext["db"])
    file_roots = (upload_dir, os.path.join(ws.root, "files"))      # faqat yuklash papkasi va fayl ombori; workspace'ning qolgan qismi (state.db, JSON) emas
    ext["run_manager"] = RunManager(ext["runs"], ext["db"], ws, ext["cookies"], file_roots)
    ext["monitors"] = MonitorStore(ws.root)
    ext["jobs"] = JobManager(allowed_file_roots=file_roots, cookies=ext["cookies"], workspace=ws)
    return result


def create_app(workspace_dir=None, saved_file=None, upload_dir=None, session_token=None, backup_dir=None, desktop=None):
    """Flask ilovasini yaratadi. Barcha yo'llar argument bilan almashtiriladi (testlar uchun)."""
    if os.environ.get("APIRUNNER_TESTING") and None in (workspace_dir, saved_file, upload_dir, backup_dir):
        # testlar hech qachon haqiqiy ma'lumotga (saved_requests.json, workspace/, backups/) tegmasligi uchun
        raise RuntimeError("APIRUNNER_TESTING: barcha yo'llar (tmp) aniq berilishi shart")
    app = Flask(__name__, static_folder=os.path.join(PKG_DIR, "static"))
    workspace_dir = workspace_dir or os.environ.get("APIRUNNER_WORKSPACE") or os.path.join(ROOT_DIR, "workspace")
    saved_file = saved_file if saved_file is not None else os.path.join(ROOT_DIR, "saved_requests.json")
    upload_dir = upload_dir or os.path.join(ROOT_DIR, ".tmp_uploads")

    backup_dir = backup_dir or os.path.join(ROOT_DIR, "backups")
    registry = WorkspaceRegistry(os.path.join(os.path.dirname(os.path.abspath(workspace_dir)), "workspaces.json"), workspace_dir)
    app.extensions["registry"] = registry
    app.extensions["backup_dir"] = backup_dir
    app.extensions["saved_file"] = saved_file
    app.config["STARTED_AT"] = time.time()
    app.config["DESKTOP"] = desktop                      # {"home": …} — desktop (.app) rejimida; None — oddiy server
    app.extensions["protocols"] = ProtocolManager()
    app.extensions["mocks"] = MockManager()
    app.extensions["proxy"] = ProxyManager()
    app.config.update(UPLOAD_DIR=upload_dir)
    result = bind_workspace(app, registry.active_dir(), saved_file if registry.active == DEFAULT_ID else "", backup_dir, upload_dir)
    app.config.update(SESSION_TOKEN=session_token or security.new_token(), MIGRATION=result["legacy"], MIGRATION_RESULT=result)

    app.extensions["scheduler"] = Scheduler(app)
    if not os.environ.get("APIRUNNER_TESTING"):
        app.extensions["scheduler"].start()          # testlarda tick() qo'lda chaqiriladi
    security.install(app)
    app.register_blueprint(legacy.bp)
    app.register_blueprint(workspace_api.bp)
    app.register_blueprint(runs_api.bp)
    app.register_blueprint(admin_api.bp)
    app.register_blueprint(importexport_api.bp)
    app.register_blueprint(protocols_api.bp)
    app.register_blueprint(workspaces_api.bp)
    app.register_blueprint(monitors_api.bp)
    app.register_blueprint(desktop_api.bp)
    app.register_blueprint(proxy_api.bp)
    app.register_blueprint(oauth.bp)

    static = os.path.join(PKG_DIR, "static")

    def page(path):
        import json as _json
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        boot = security.BOOTSTRAP_JS % _json.dumps(app.config["SESSION_TOKEN"])
        html = html.replace("<head>", "<head>\n" + boot, 1)
        return Response(html, content_type="text/html; charset=utf-8", headers={"Cache-Control": "no-store"})

    @app.get("/legacy")
    def legacy_index():
        """Eski UI — yangi frontend paritetga yetib, e2e yashil bo'lguncha saqlanadi."""
        return page(os.path.join(static, "index.html"))

    @app.get("/favicon.ico")
    @app.get("/apple-touch-icon.png")
    def root_icons():
        """Brauzerlar ildizdan so'raydigan ikonkalar: haqiqiy fayl, uzoq cache (fayl o'zgarmaydi)."""
        name = request.path.lstrip("/")
        resp = send_from_directory(os.path.join(static, "app"), name, max_age=31536000)
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    @app.get("/")
    def index():
        new = os.path.join(static, "app", "index.html")
        return page(new if os.path.exists(new) else os.path.join(static, "index.html"))

    return app


def main(host="127.0.0.1", port=None, open_browser_tab=True):
    port = port or int(os.environ.get("APIRUNNER_PORT", "5050"))
    app = create_app()

    def open_browser():
        time.sleep(0.9)
        webbrowser.open(f"http://{host}:{port}")

    if open_browser_tab and os.environ.get("APIRUNNER_NO_BROWSER") != "1":
        threading.Thread(target=open_browser, daemon=True).start()
    print()
    print("=" * 50)
    print(f"  API RUNNER v{__version__}  —  http://{host}:{port}")
    print(f"  Workspace: {app.extensions['workspace'].root}")
    if app.config["MIGRATION_RESULT"]["status"] == "rolled_back":
        print("  DIQQAT: " + app.config["MIGRATION_RESULT"]["message"])
    if app.config["MIGRATION"] == "migrated":
        print("  saved_requests.json workspace'ga ko'chirildi (.bak zaxira olindi)")
    print("=" * 50)
    print()
    app.run(host=host, port=port, debug=False, threaded=True)
