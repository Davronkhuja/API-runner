"""python3 -m apirunner.restore <papka>"""
from .storage.restore import main
import sys

if __name__ == "__main__":
    sys.exit(main())
