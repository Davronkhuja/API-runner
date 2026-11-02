"""Workspace qulfi: bir jarayon ichidagi oqimlar (RLock) + jarayonlar orasida (fcntl.flock).

Ikki brauzer tab / ikki jarayon bir vaqtda yozsa, read-modify-write ketma-ket bajariladi.
"""
import os
import threading

try:
    import fcntl
except ImportError:                      # Windows: faqat oqimlararo qulf
    fcntl = None


class WorkspaceLock:
    def __init__(self, path):
        self.path = path
        self._rlock = threading.RLock()
        self._depth = 0
        self._fd = None

    def __enter__(self):
        self._rlock.acquire()
        try:
            if self._depth == 0 and fcntl is not None:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                self._fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
                fcntl.flock(self._fd, fcntl.LOCK_EX)
            self._depth += 1
        except BaseException:
            self._rlock.release()
            raise
        return self

    def __exit__(self, *exc):
        self._depth -= 1
        try:
            if self._depth == 0 and self._fd is not None:
                try:
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                finally:
                    os.close(self._fd)
                    self._fd = None
        finally:
            self._rlock.release()
        return False
