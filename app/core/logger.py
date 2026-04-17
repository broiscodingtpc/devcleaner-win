"""Application logger.

Writes both to stderr and to a rolling file under %APPDATA%\\WinCleaner\\logs.
Also exposes a small in-memory observer pattern so the UI can show live log
lines during a scan / cleanup run.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, List


_LOG_NAME = "wincleaner"


def app_data_dir() -> Path:
    """Return the per-user application data directory, creating it if needed."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    target = base / "WinCleaner"
    target.mkdir(parents=True, exist_ok=True)
    return target


def logs_dir() -> Path:
    target = app_data_dir() / "logs"
    target.mkdir(parents=True, exist_ok=True)
    return target


class _UIBridgeHandler(logging.Handler):
    """Fan-out log records to any registered UI observer callbacks."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self._lock = threading.Lock()
        self._observers: List[Callable[[str, str], None]] = []

    def register(self, callback: Callable[[str, str], None]) -> None:
        with self._lock:
            self._observers.append(callback)

    def unregister(self, callback: Callable[[str, str], None]) -> None:
        with self._lock:
            try:
                self._observers.remove(callback)
            except ValueError:
                pass

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            return
        with self._lock:
            observers = list(self._observers)
        for obs in observers:
            try:
                obs(record.levelname, message)
            except Exception:
                pass


_ui_bridge = _UIBridgeHandler()
_configured = False
_configure_lock = threading.Lock()


def _configure() -> None:
    global _configured
    with _configure_lock:
        if _configured:
            return
        logger = logging.getLogger(_LOG_NAME)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        fmt = logging.Formatter(
            "%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S"
        )

        stream = logging.StreamHandler(stream=sys.stderr)
        stream.setFormatter(fmt)
        logger.addHandler(stream)

        try:
            log_file = logs_dir() / f"cleanup-{datetime.now().strftime('%Y%m%d')}.log"
            rotating = RotatingFileHandler(
                log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
            )
            rotating.setFormatter(fmt)
            logger.addHandler(rotating)
        except Exception:
            pass

        _ui_bridge.setFormatter(fmt)
        logger.addHandler(_ui_bridge)

        _configured = True


def get_logger() -> logging.Logger:
    _configure()
    return logging.getLogger(_LOG_NAME)


def register_ui_observer(callback: Callable[[str, str], None]) -> None:
    _configure()
    _ui_bridge.register(callback)


def unregister_ui_observer(callback: Callable[[str, str], None]) -> None:
    _ui_bridge.unregister(callback)
