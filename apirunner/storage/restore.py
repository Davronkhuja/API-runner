"""Zaxiradan tiklash.

    python3 -m apirunner.restore <zaxira-papka> [--workspace DIR] [--backups DIR]

Tiklashdan oldin joriy holat ham zaxiralanadi (`..._pre-restore`). saved_requests.json TEGILMAYDI
(zaxiradagi nusxasi qo'lda olinishi uchun papkada qoladi).
"""
import argparse
import os
import shutil
import sys
import time

from . import backup as bk


def swap_workspace(backup_path, ws_root):
    """Zaxiradagi workspace'ni ws_root o'rniga qo'yadi. Eski katalog nusxasi tekshirilgandan keyingina o'chiriladi."""
    src = os.path.join(backup_path, "workspace")
    if not os.path.isdir(src):
        raise FileNotFoundError("Zaxirada workspace/ yo'q: " + backup_path)
    ws_root = os.path.abspath(ws_root)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    staged = f"{ws_root}.restoring-{stamp}"
    old = f"{ws_root}.replaced-{stamp}"
    shutil.copytree(src, staged)
    db = os.path.join(src, bk.DB_NAME)
    if os.path.isfile(db):
        shutil.copy2(db, os.path.join(staged, bk.DB_NAME))
    os.makedirs(os.path.join(staged), exist_ok=True)
    if os.path.exists(ws_root):
        os.rename(ws_root, old)
    os.rename(staged, ws_root)
    if os.path.isdir(old):
        shutil.rmtree(old)            # asl nusxasi yuqorida zaxirada (pre-restore / migratsiya zaxirasi) mavjud


def restore_backup(backup_path, ws_root, saved_file, version, backup_dir):
    backup_path = os.path.realpath(backup_path)
    if os.path.dirname(backup_path) != os.path.realpath(backup_dir) or not bk.NAME_RE.match(os.path.basename(backup_path)):
        raise ValueError("Zaxira papkasi noto'g'ri (backups/ ichida bo'lishi kerak)")
    if not os.path.isdir(os.path.join(backup_path, "workspace")):
        raise FileNotFoundError("Zaxirada workspace/ yo'q")
    pre = bk.create_backup(ws_root, saved_file, version, backup_dir, suffix="pre-restore")   # 1) joriy holat
    swap_workspace(backup_path, ws_root)                                                       # 2) almashtirish
    return pre


def main(argv=None):
    from ..app import ROOT_DIR
    from .. import __version__
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("backup")
    ap.add_argument("--workspace", default=os.environ.get("APIRUNNER_WORKSPACE") or os.path.join(ROOT_DIR, "workspace"))
    ap.add_argument("--backups", default=os.path.join(ROOT_DIR, "backups"))
    ap.add_argument("--saved-file", default=os.path.join(ROOT_DIR, "saved_requests.json"))
    a = ap.parse_args(argv)
    path = a.backup if os.path.isabs(a.backup) or os.path.exists(a.backup) else os.path.join(a.backups, a.backup)
    try:
        pre = restore_backup(path, a.workspace, a.saved_file, __version__, a.backups)
    except (ValueError, FileNotFoundError) as e:
        print("Xato:", e, file=sys.stderr)
        return 1
    print(f"Tiklandi: {path}\nJoriy holat zaxiralandi: {pre}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
