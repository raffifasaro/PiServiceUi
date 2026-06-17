"""Per-service log capture and tailing.

Each running service gets a reader thread that pumps its merged
stdout/stderr pipe into a size-rotated file. The UI tails that file on
demand via :func:`tail_file`.
"""
from __future__ import annotations

import logging
import os
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path


def log_path(logs_dir: Path, name: str) -> Path:
    return Path(logs_dir) / f"{name}.log"


class ServiceLogger:
    """Owns the rotating log file for one service and its reader thread."""

    def __init__(
        self,
        logs_dir: Path,
        name: str,
        max_bytes: int = 512_000,
        backups: int = 2,
    ) -> None:
        self.name = name
        self.path = log_path(logs_dir, name)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger(f"piserviceui.svc.{name}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        if not self._logger.handlers:
            handler = RotatingFileHandler(
                self.path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S")
            )
            self._logger.addHandler(handler)

        self._reader: threading.Thread | None = None

    def system(self, message: str) -> None:
        """Record a host-side note (start/stop/restart) in the log."""
        self._logger.info("[host] %s", message)

    def attach(self, proc) -> None:
        """Start pumping ``proc``'s stdout into the log file."""
        self._reader = threading.Thread(
            target=self._pump, args=(proc,), name=f"log-{self.name}", daemon=True
        )
        self._reader.start()

    def _pump(self, proc) -> None:
        stream = proc.stdout
        if stream is None:
            return
        try:
            for raw in iter(stream.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                self._logger.info(line)
        except (ValueError, OSError):
            # stream closed underneath us
            pass


def tail_file(path: Path, lines: int = 200) -> list[str]:
    """Return the last ``lines`` lines of a (possibly large) text file."""
    path = Path(path)
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 4096
            data = b""
            while size > 0 and data.count(b"\n") <= lines:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
        return data.decode("utf-8", "replace").splitlines()[-lines:]
    except OSError:
        return []
