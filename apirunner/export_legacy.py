"""Orqaga qaytish skripti: workspace/ -> saved_requests.json.

    python3 -m apirunner.export_legacy [--workspace DIR] [-o saved_requests.json] [--force]

Mavjud chiqish fayli bo'lsa, `--force` siz yozmaydi (zaxira nusxa o'rniga to'xtaydi).
"""
import argparse
import json
import os
import sys

from .app import ROOT_DIR
from .storage.legacy_view import export_workspace
from .storage.workspace import Workspace


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", default=os.environ.get("APIRUNNER_WORKSPACE") or os.path.join(ROOT_DIR, "workspace"))
    ap.add_argument("-o", "--output", default=os.path.join(ROOT_DIR, "saved_requests.export.json"))
    ap.add_argument("--force", action="store_true", help="mavjud faylni ustidan yozish")
    a = ap.parse_args(argv)
    if os.path.exists(a.output) and not a.force:
        print(f"Xato: {a.output} mavjud. Boshqa nom bering (-o) yoki --force.", file=sys.stderr)
        return 1
    data = export_workspace(Workspace(a.workspace))
    with open(a.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"{len(data['folders'])} papka, {len(data['requests'])} so'rov -> {a.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
