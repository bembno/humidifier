"""Logging setup for the humidifier web service.

Logs are written to ``logs/app.log`` with rotation and are additionally kept
in a small in-memory buffer so the web interface can show the latest events
without reading the file.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import deque
from logging.handlers import RotatingFileHandler
from typing import Deque, Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

MAX_BYTES = 1024 * 1024
BACKUP_COUNT = 3
RECENT_LIMIT = 300

_RECENT: Deque[Dict[str, str]] = deque(maxlen=RECENT_LIMIT)
_RECENT_LOCK = threading.Lock()


class RecentHandler(logging.Handler):
    """Keeps the most recent log records in memory for the web interface."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            message = str(record.msg)
        entry = {
            "ts": self.format(record),
            "level": record.levelname,
            "message": message,
        }
        with _RECENT_LOCK:
            _RECENT.append(entry)

    def format(self, record: logging.LogRecord) -> str:
        return time_str(record)


def time_str(record: logging.LogRecord) -> str:
    import datetime as _dt

    return _dt.datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("humidifier")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    recent_handler = RecentHandler()
    recent_handler.setFormatter(formatter)
    logger.addHandler(recent_handler)

    return logger


def recent_events(limit: int = 100) -> List[Dict[str, str]]:
    with _RECENT_LOCK:
        items = list(_RECENT)
    if limit > 0:
        items = items[-limit:]
    return list(reversed(items))
