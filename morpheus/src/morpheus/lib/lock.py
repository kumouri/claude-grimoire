"""Cross-platform advisory file lock via O_CREAT|O_EXCL, with stale breaking.

Used to serialize writes to a single project's memory store so concurrent
sessions can't corrupt ``MEMORY.md``. A lock older than ``stale`` seconds is
assumed orphaned (crashed worker) and stolen.
"""
from __future__ import annotations

import os
import time
from pathlib import Path


class LockError(Exception):
    pass


class FileLock:
    def __init__(self, path, timeout: float = 30.0, stale: float = 600.0, poll: float = 0.1):
        self.path = Path(path)
        self.timeout = timeout
        self.stale = stale
        self.poll = poll
        self._fd = None

    def acquire(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                self._fd = fd
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                    if age > self.stale:
                        self.path.unlink(missing_ok=True)
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise LockError(f"timeout acquiring lock {self.path}")
                time.sleep(self.poll)

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None
                self.path.unlink(missing_ok=True)

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
