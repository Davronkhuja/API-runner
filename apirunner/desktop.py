"""Desktop rejim: serverni tasodifiy loopback portida ishga tushirib, uni alohida oynada (pywebview) ko'rsatadi.
Ma'lumot — foydalanuvchi papkasida (macOS: ~/Library/Application Support/API Runner), ilova paketi ichida emas.

Birinchi ishga tushishda boshqa joyda (repo `workspace/`, PM2 nusxasi) mavjud workspace topilsa — tanlov: shu ma'lumotdan foydalanish /
nusxa olish / yangi bo'sh. Tanlov `desktop.json` da saqlanadi; Sozlamalar → Workspace papkasi orqali o'zgartiriladi.
Ishga tushirish: `python -m apirunner.desktop` (pywebview kerak: `pip install pywebview`)."""
import html
import json
import os
import shutil
import sys
import threading

from werkzeug.serving import make_server

CONFIG = "desktop.json"
SKIP_COPY = (".lock", ".session.lock")


def default_home():
    env = os.environ.get("APIRUNNER_HOME")
    if env:
        return env
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/API Runner")
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "API Runner")
    return os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "api-runner")


def load_config(home):
    try:
        with open(os.path.join(home, CONFIG), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_config(home, cfg):
    os.makedirs(home, exist_ok=True)
    tmp = os.path.join(home, CONFIG + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, os.path.join(home, CONFIG))


def _is_workspace(path):
    return bool(path) and os.path.isfile(os.path.join(path, "workspace.json"))


def _pm2_cwd():
    """PM2 dump'idan `api-runner` jarayonining papkasi (eski PM2 nusxasi)."""
    try:
        with open(os.path.expanduser("~/.pm2/dump.pm2"), encoding="utf-8") as f:
            for app in json.load(f):
                if app.get("name") == "api-runner":
                    return app.get("pm_cwd") or (app.get("env") or {}).get("PWD")
    except (OSError, ValueError, TypeError):
        pass
    return None


def hint_workspace():
    """Build vaqtida yozilgan repo workspace yo'li (packaging/build_macos_app.sh → desktop_hints.json)."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop_hints.json"), encoding="utf-8") as f:
            return json.load(f).get("repo_workspace")
    except (OSError, ValueError):
        return None


def find_candidates(home):
    """Mavjud workspace'lar (ma'lumoti bor, `home` dagidan boshqa). [{path, label, collections, holder}]"""
    from .storage import instance
    raw = [(os.environ.get("APIRUNNER_LEGACY_WORKSPACE"), "APIRUNNER_LEGACY_WORKSPACE"), (hint_workspace(), "Repo papkasidagi workspace"),
           (os.path.join(_pm2_cwd(), "workspace") if _pm2_cwd() else None, "PM2 nusxasi (api-runner)")]
    seen, out = {os.path.abspath(os.path.join(home, "workspace"))}, []
    for path, label in raw:
        if not path:
            continue
        path = os.path.abspath(os.path.expanduser(path))
        if path in seen or not _is_workspace(path):
            continue
        seen.add(path)
        try:
            n = len([f for f in os.listdir(os.path.join(path, "collections")) if f.endswith(".json")])
        except OSError:
            n = 0
        out.append({"path": path, "label": label, "collections": n, "holder": instance.probe(path)})
    return out


def copy_workspace(src, dst):
    """Manba tegilmaydi: faqat o'qiladi. Vaqtinchalik papkaga nusxalab, keyin nom almashtiriladi (yarim nusxa qolmaydi)."""
    if os.path.exists(dst):
        raise FileExistsError(dst)
    tmp = dst + ".copying"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp, ignore=shutil.ignore_patterns(*SKIP_COPY, "*.db-wal", "*.db-shm"))
    os.replace(tmp, dst)


def apply_choice(home, choice, source=None):
    """choice: 'use' | 'copy' | 'fresh'. Natija desktop.json ga yoziladi va qaytariladi."""
    home = os.path.abspath(home)
    own = os.path.join(home, "workspace")
    if choice == "use":
        if not _is_workspace(source):
            raise ValueError("Tanlangan papkada workspace topilmadi")
        cfg = {"mode": "use", "workspace_dir": os.path.abspath(source), "source": os.path.abspath(source)}
    elif choice == "copy":
        if not _is_workspace(source):
            raise ValueError("Tanlangan papkada workspace topilmadi")
        if os.path.exists(own):
            raise ValueError("Nusxa uchun papka band: " + own)
        os.makedirs(home, exist_ok=True)
        copy_workspace(source, own)
        cfg = {"mode": "copy", "workspace_dir": own, "source": os.path.abspath(source)}
    elif choice == "fresh":
        cfg = {"mode": "fresh", "workspace_dir": own}
    else:
        raise ValueError("Noma'lum tanlov")
    save_config(home, cfg)
    return cfg


def paths_for(home, cfg):
    """create_app uchun yo'llar. 'use' rejimida zaxira va reestr shu workspace'ning yonida (boshqa nusxa bilan bir xil)."""
    ws = (cfg or {}).get("workspace_dir") or os.path.join(home, "workspace")
    if (cfg or {}).get("mode") in ("use", "custom") and os.path.abspath(os.path.dirname(ws)) != os.path.abspath(home):
        parent = os.path.dirname(ws)
        return {"workspace_dir": ws, "backup_dir": os.path.join(parent, "backups"), "saved_file": ""}
    return {"workspace_dir": ws, "backup_dir": os.path.join(home, "backups"), "saved_file": os.path.join(home, "saved_requests.json")}


def start_server(home=None, cfg=None):
    """Serverni fon oqimida ishga tushiradi. Qaytaradi: (url, to'xtatish funksiyasi, app)."""
    from .app import create_app
    home = os.path.abspath(home or default_home())
    os.makedirs(home, exist_ok=True)
    cfg = cfg if cfg is not None else load_config(home)
    p = paths_for(home, cfg)
    app = create_app(workspace_dir=p["workspace_dir"], saved_file=p["saved_file"], upload_dir=os.path.join(home, "uploads"), backup_dir=p["backup_dir"], desktop={"home": home})
    srv = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=srv.serve_forever, daemon=True, name="apirunner-desktop-server").start()
    return f"http://127.0.0.1:{srv.server_port}", srv.shutdown, app


def chooser_html(cands):
    """Birinchi ishga tushishdagi tanlov sahifasi (pywebview `js_api` orqali: window.pywebview.api.choose(mode, index))."""
    rows = ""
    for i, c in enumerate(cands):
        lock = ""
        if c.get("holder"):
            h = c["holder"]
            lock = (f'<p class="warn">⚠ Bu workspace hozir boshqa API Runner nusxasida ochiq (pid {html.escape(str(h.get("pid")))}'
                    f'{", v" + html.escape(str(h["version"])) if h.get("version") else ""}). «Shu ma\'lumotlardan foydalanish» ikki nusxa bir vaqtda yozishiga olib keladi — '
                    f'avval u nusxani yoping yoki <b>«Nusxa olish»</b> ni tanlang.</p>')
        rows += (f'<section><h2>{html.escape(c["label"])}</h2><code>{html.escape(c["path"])}</code><p>{c["collections"]} ta collection</p>{lock}'
                 f'<div class="btns"><button data-mode="use" onclick="pick(\'use\',{i})">Shu ma\'lumotlardan foydalanish</button>'
                 f'<button class="primary" data-mode="copy" onclick="pick(\'copy\',{i})">Nusxa olish (tavsiya)</button></div></section>')
    return f"""<!doctype html><meta charset="utf-8"><title>API Runner</title>
<style>body{{font:14px -apple-system,sans-serif;margin:0;padding:32px;background:#f6f7f9;color:#1b1f24}}h1{{margin:0 0 8px}}section{{background:#fff;border:1px solid #dde1e6;border-radius:10px;padding:16px;margin:16px 0}}
code{{display:block;word-break:break-all;color:#555}}.btns{{display:flex;gap:8px;flex-wrap:wrap}}button{{padding:8px 14px;border-radius:8px;border:1px solid #c5cad1;background:#fff;cursor:pointer;font:inherit}}.primary{{background:#4f46e5;color:#fff;border-color:#4f46e5}}.warn{{color:#a15c00;background:#fff4e0;padding:8px 10px;border-radius:8px}}.fresh{{margin-top:8px}}</style>
<h1>Mavjud ma'lumot topildi</h1><p>Bu kompyuterda API Runner'ning boshqa nusxasi ma'lumoti bor. Qanday davom etamiz?</p>{rows}
<button class="fresh" data-mode="fresh" onclick="pick('fresh',-1)">Yangi bo'sh workspace bilan boshlash</button>
<script>function pick(m,i){{document.querySelectorAll('button').forEach(b=>b.disabled=true);window.pywebview.api.choose(m,i)}}</script>"""


class ChooserApi:
    def __init__(self, home, cands, on_done):
        self.home, self.cands, self.on_done = home, cands, on_done

    def choose(self, mode, index):
        src = self.cands[index]["path"] if 0 <= index < len(self.cands) else None
        cfg = apply_choice(self.home, mode, src)
        self.on_done(cfg)
        return True


def main():
    try:
        import webview
    except ImportError:
        print("pywebview o'rnatilmagan: `pip install pywebview` (yoki packaging/build_macos_app.sh)", file=sys.stderr)
        return 1
    from . import __version__
    home = os.path.abspath(default_home())
    webview.settings["ALLOW_DOWNLOADS"] = True                         # eksport (zip/JSON/HTML) yuklab olish
    cfg = load_config(home)
    state = {}

    def launch(window, cfg):
        url, stop, _app = start_server(home, cfg)
        state["stop"] = stop
        if window is None:
            return url
        window.resize(1440, 900)
        window.load_url(url)
        return url

    cands = [] if cfg or os.path.isdir(os.path.join(home, "workspace")) else find_candidates(home)
    if cands:
        win = webview.create_window(f"API Runner {__version__}", html=chooser_html(cands), width=900, height=700, js_api=None)
        win._api = ChooserApi(home, cands, lambda c: launch(win, c))
        win.expose(win._api.choose)
    else:
        win = webview.create_window(f"API Runner {__version__}", launch(None, cfg), width=1440, height=900, min_size=(1000, 640), text_select=True)
    try:
        webview.start()
    finally:
        if state.get("stop"):
            state["stop"]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
