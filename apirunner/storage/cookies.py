"""Cookie jar (SQLite, workspace/state.db): so'rovlar orasida saqlanadi, domenlar bo'yicha boshqariladi."""
import http.cookiejar
import sqlite3
import threading
import time

from .db import connect

SCHEMA = """
CREATE TABLE IF NOT EXISTS cookies (
    domain    TEXT NOT NULL,
    path      TEXT NOT NULL DEFAULT '/',
    name      TEXT NOT NULL,
    value     TEXT NOT NULL DEFAULT '',
    expires   INTEGER,                    -- unix vaqt; NULL = sessiya cookie'si
    secure    INTEGER NOT NULL DEFAULT 0,
    httponly  INTEGER NOT NULL DEFAULT 0,
    host_only INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (domain, path, name)
);
"""
FIELDS = ("domain", "path", "name", "value", "expires", "secure", "httponly", "host_only")


def _key(c):
    return (c.domain, c.path, c.name)


class CookieStore:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        c = connect(path)
        try:
            c.executescript(SCHEMA)
            c.commit()
        finally:
            c.close()

    # ── boshqaruv (Cookie Manager) ──
    def list(self):
        with self._lock:
            c = connect(self.path)
            try:
                now = int(time.time())
                c.execute("DELETE FROM cookies WHERE expires IS NOT NULL AND expires <= ?", (now,))
                c.commit()
                return [dict(r) for r in c.execute("SELECT * FROM cookies ORDER BY domain, path, name")]
            finally:
                c.close()

    def upsert(self, d):
        domain, name = (d.get("domain") or "").strip().lower(), (d.get("name") or "").strip()
        if not domain or not name:
            raise ValueError("domain va name kerak")
        row = (domain, d.get("path") or "/", name, str(d.get("value", "")),
               int(d["expires"]) if d.get("expires") not in (None, "") else None,
               int(bool(d.get("secure"))), int(bool(d.get("httponly"))), int(bool(d.get("host_only", not domain.startswith(".")))))
        with self._lock:
            c = connect(self.path)
            try:
                with c:
                    c.execute("INSERT OR REPLACE INTO cookies(domain,path,name,value,expires,secure,httponly,host_only) VALUES (?,?,?,?,?,?,?,?)", row)
            finally:
                c.close()

    def delete(self, domain=None, path=None, name=None):
        """domain+path+name — bittasi; faqat domain — butun domen; hech narsa — hammasi. Qaytaradi: o'chirilgan soni."""
        q, args = "DELETE FROM cookies", []
        if domain is not None:
            q += " WHERE domain=?"
            args.append(domain.lower())
            if name is not None:
                q += " AND name=? AND path=?"
                args += [name, path or "/"]
        with self._lock:
            c = connect(self.path)
            try:
                with c:
                    return c.execute(q, args).rowcount
            finally:
                c.close()

    # ── engine uchun ──
    def load_jar(self):
        """Saqlangan cookie'lardan CookieJar; moslashtirishni (domen/yo'l/secure) http.cookiejar o'zi bajaradi."""
        jar = http.cookiejar.CookieJar()
        loaded = set()
        for r in self.list():
            host_only = bool(r["host_only"])
            dom = r["domain"]
            jar.set_cookie(http.cookiejar.Cookie(
                0, r["name"], r["value"], None, False, dom if host_only else (dom if dom.startswith(".") else "." + dom), not host_only,
                not host_only, r["path"], True, bool(r["secure"]), r["expires"], r["expires"] is None, None, None,
                {"HttpOnly": None} if r["httponly"] else {}))
            loaded.add((jar_domain(dom, host_only), r["path"], r["name"]))
        return jar, loaded

    def save_jar(self, jar, loaded):
        """So'rovdan keyingi jar holatini yozadi; serverda o'chirilgan (jar'da qolmagan) cookie'lar bazadan ham ketadi."""
        now = {_key(c): c for c in jar}
        with self._lock:
            c = connect(self.path)
            try:
                with c:
                    for dom, path, name in loaded - set(now):
                        c.execute("DELETE FROM cookies WHERE path=? AND name=? AND (domain=? OR domain=?)", (path, name, dom, dom.lstrip(".")))
                    for (dom, path, name), ck in now.items():
                        host_only = not ck.domain_specified
                        c.execute("INSERT OR REPLACE INTO cookies(domain,path,name,value,expires,secure,httponly,host_only) VALUES (?,?,?,?,?,?,?,?)",
                                  (dom.lower(), path, name, ck.value or "", ck.expires, int(ck.secure), int(ck.has_nonstandard_attr("HttpOnly")), int(host_only)))
            except sqlite3.Error:
                pass          # cookie yozilmasa ham so'rov natijasi yo'qolmasin
            finally:
                c.close()


def jar_domain(dom, host_only):
    return dom if host_only else (dom if dom.startswith(".") else "." + dom)
