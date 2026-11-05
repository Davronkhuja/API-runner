"""Server boshqaruvi: yangilanishdan keyin o'zini qayta ishga tushirish (PM2 `autorestart` yangi kod bilan qayta ko'taradi)."""
import json
import os
import threading

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("admin", __name__, url_prefix="/api/admin")
STATIC_VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "app", "version.json")
NOT_MANAGED_HINT = "Server PM2 ostida emas: uni to'xtating (Ctrl+C) va ./run.command bilan qayta ishga tushiring."


def managed():
    """PM2 (yoki boshqa supervisor) qayta ko'taradimi? Testlar uchun `RESTART_MANAGED` bilan almashtiriladi."""
    forced = current_app.config.get("RESTART_MANAGED")
    if forced is not None:
        return bool(forced)
    return os.environ.get("pm_id") is not None or bool(os.environ.get("PM2_HOME") and os.environ.get("NODE_APP_INSTANCE") is not None)


def disk_ui_version():
    """Diskdagi (oxirgi build) UI versiyasi — ochiq sahifa eskirganini bilishi uchun."""
    try:
        with open(current_app.config.get("UI_VERSION_FILE", STATIC_VERSION_FILE), encoding="utf-8") as f:
            return json.load(f).get("version")
    except (OSError, ValueError):
        return None


def _active():
    return list(current_app.extensions["run_manager"].active()), list(current_app.extensions["jobs"].active())


def active_count():
    runs, jobs = _active()
    return len(runs) + len(jobs)


@bp.post("/restart")
def restart():
    """Faol run yo'q (yoki `force`) bo'lsa: run'larni to'xtatadi, yozuvlarni flush qiladi va chiqadi. Host/token tekshiruvi `security.guard` da."""
    data = request.get_json(silent=True) or {}
    if not managed():
        return jsonify({"error": NOT_MANAGED_HINT, "managed": False}), 409
    runs, jobs = _active()
    if (runs or jobs) and not data.get("force"):
        return jsonify({"error": "Faol run bor", "needs_confirm": True, "active_runs": len(runs) + len(jobs)}), 409
    for r in runs:
        r.stop.set()
    for j in jobs:
        j["stop_event"].set()
    for r in runs:
        if r.thread:
            r.thread.join(5)
    for j in jobs:
        j["thread"].join(5)
    ws = current_app.extensions["workspace"]
    with ws.lock:                                              # davom etayotgan yozuvlar tugaguncha kutadi
        current_app.extensions["db"].checkpoint()
    exit_fn = current_app.extensions.get("exit_fn") or os._exit
    threading.Timer(0.4, exit_fn, args=(0,)).start()          # javob mijozga yetib borsin
    return jsonify({"ok": True, "stopped_runs": len(runs) + len(jobs)})
