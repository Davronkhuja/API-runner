import os
import threading
import time
import webbrowser

from flask import Flask, Response

from .api import legacy, oauth, security, workspace_api
from .core.jobs import JobManager
from .storage.db import StateDB
from . import __version__
from .storage import migrations
from .storage.workspace import Workspace

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PKG_DIR)


def create_app(workspace_dir=None, saved_file=None, upload_dir=None, session_token=None, backup_dir=None):
    """Flask ilovasini yaratadi. Barcha yo'llar argument bilan almashtiriladi (testlar uchun)."""
    if os.environ.get("APIRUNNER_TESTING") and None in (workspace_dir, saved_file, upload_dir, backup_dir):
        # testlar hech qachon haqiqiy ma'lumotga (saved_requests.json, workspace/, backups/) tegmasligi uchun
        raise RuntimeError("APIRUNNER_TESTING: barcha yo'llar (tmp) aniq berilishi shart")
    app = Flask(__name__, static_folder=os.path.join(PKG_DIR, "static"))
    workspace_dir = workspace_dir or os.environ.get("APIRUNNER_WORKSPACE") or os.path.join(ROOT_DIR, "workspace")
    saved_file = saved_file if saved_file is not None else os.path.join(ROOT_DIR, "saved_requests.json")
    upload_dir = upload_dir or os.path.join(ROOT_DIR, ".tmp_uploads")

    backup_dir = backup_dir or os.path.join(ROOT_DIR, "backups")
    ws = Workspace(workspace_dir)
    # barcha migratsiyalar (saved_requests.json import, sxema) — zaxira, sonlar tekshiruvi va rollback bilan
    result = migrations.run_all(ws, saved_file, backup_dir, __version__)
    app.extensions["workspace"] = ws
    app.extensions["db"] = StateDB(os.path.join(ws.root, "state.db"))
    app.extensions["backup_dir"] = backup_dir
    app.extensions["saved_file"] = saved_file
    app.extensions["jobs"] = JobManager(allowed_file_roots=(upload_dir, ws.root))
    app.config.update(UPLOAD_DIR=upload_dir, SESSION_TOKEN=session_token or security.new_token(),
                      MIGRATION=result["legacy"], MIGRATION_RESULT=result)

    security.install(app)
    app.register_blueprint(legacy.bp)
    app.register_blueprint(workspace_api.bp)
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
