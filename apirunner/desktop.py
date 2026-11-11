"""Desktop rejim: serverni tasodifiy loopback portida ishga tushirib, uni alohida oynada (pywebview) ko'rsatadi.
Ma'lumot — foydalanuvchi papkasida (macOS: ~/Library/Application Support/API Runner), ilova paketi ichida emas.
Ishga tushirish: `python -m apirunner.desktop` (pywebview kerak: `pip install pywebview`)."""
import os
import sys
import threading

from werkzeug.serving import make_server


def default_home():
    env = os.environ.get("APIRUNNER_HOME")
    if env:
        return env
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/API Runner")
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "API Runner")
    return os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "api-runner")


def start_server(home=None):
    """Serverni fon oqimida ishga tushiradi. Qaytaradi: (url, to'xtatish funksiyasi, app)."""
    from .app import create_app
    home = os.path.abspath(home or default_home())
    os.makedirs(home, exist_ok=True)
    app = create_app(workspace_dir=os.path.join(home, "workspace"), saved_file=os.path.join(home, "saved_requests.json"),
                     upload_dir=os.path.join(home, "uploads"), backup_dir=os.path.join(home, "backups"))
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True, name="apirunner-desktop-server").start()
    return f"http://127.0.0.1:{srv.server_port}", srv.shutdown, app


def main():
    try:
        import webview
    except ImportError:
        print("pywebview o'rnatilmagan: `pip install pywebview` (yoki packaging/build_macos_app.sh)", file=sys.stderr)
        return 1
    from . import __version__
    url, stop, _app = start_server()
    webview.settings["ALLOW_DOWNLOADS"] = True                         # eksport (zip/JSON/HTML) yuklab olish
    webview.create_window(f"API Runner {__version__}", url, width=1440, height=900, min_size=(1000, 640), text_select=True)
    try:
        webview.start()
    finally:
        stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
