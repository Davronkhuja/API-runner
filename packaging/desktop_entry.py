"""PyInstaller kirish nuqtasi. `--selftest`: oynasiz — server ishga tushadi, `/` javob beradi, chiqadi (build tekshiruvi)."""
import sys

from apirunner import desktop

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        url, stop, _ = desktop.start_server()
        import urllib.request
        body = urllib.request.urlopen(url + "/").read()
        stop()
        print("selftest OK", len(body))
        sys.exit(0 if b"API Runner" in body or b"<html" in body.lower() else 1)
    sys.exit(desktop.main())
