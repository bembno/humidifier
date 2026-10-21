"""Persistent configuration for the humidifier web interface.

The configuration is stored as a small JSON document so that every setting
survives a reboot of the Raspberry Pi.  Writes are atomic (temporary file +
``os.replace``) and the previous revision is kept as ``config.json.bak`` so a
power cut during a save can never leave the system without a usable config.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, fields, replace
from datetime import datetime
from typing import Any, Dict, Optional

from schedule import MODES, MODE_HOUR, parse_start_time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.environ.get(
    "HUMIDIFIER_CONFIG_FILE", os.path.join(BASE_DIR, "config.json")
)

MIN_DURATION_MIN = 1
MAX_DURATION_MIN = 24 * 60
MIN_INTERVAL_MIN = 1
MAX_INTERVAL_MIN = 24 * 60
MIN_STAGE = 1
MAX_STAGE = 3


class ConfigError(ValueError):
    """Raised when a configuration value is missing or out of range."""


def now() -> datetime:
    return datetime.now()


def to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat(timespec="seconds") if value else None


def from_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@dataclass
class Config:
    """User configurable parameters of the humidifier."""

    run_duration_min: int = 15
    interval_min: int = 60
    stage: int = 1
    enabled: bool = True
    run_on_start: bool = True
    schedule_mode: str = MODE_HOUR
    start_time: str = ""
    basic_auth_enabled: bool = False
    basic_auth_user: str = "admin"
    basic_auth_password: str = "raspberry"
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_result: str = ""

    def validate(self) -> "Config":
        self.run_duration_min = _as_int(
            self.run_duration_min, "run_duration_min", MIN_DURATION_MIN, MAX_DURATION_MIN
        )
        self.interval_min = _as_int(
            self.interval_min, "interval_min", MIN_INTERVAL_MIN, MAX_INTERVAL_MIN
        )
        self.stage = _as_int(self.stage, "stage", MIN_STAGE, MAX_STAGE)
        self.enabled = bool(self.enabled)
        self.run_on_start = bool(self.run_on_start)
        if self.schedule_mode not in MODES:
            raise ConfigError(f"schedule_mode must be one of {', '.join(MODES)}")
        self.start_time = (self.start_time or "").strip()
        if self.start_time and parse_start_time(self.start_time) is None:
            raise ConfigError("start_time must be a time in the HH:MM format")
        self.basic_auth_enabled = bool(self.basic_auth_enabled)
        self.basic_auth_user = (self.basic_auth_user or "admin").strip() or "admin"
        self.basic_auth_password = self.basic_auth_password or ""
        self.last_result = self.last_result or ""
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in (data or {}).items() if k in known}
        config = cls(**clean)
        return config.validate()


def _as_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} must be a whole number")
    if number < minimum or number > maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}")
    return number


class ConfigStore:
    """Thread safe, atomic JSON configuration store."""

    def __init__(self, path: str = CONFIG_FILE) -> None:
        self._path = path
        self._lock = threading.RLock()
        self._cache: Optional[Config] = None
        self._mtime: Optional[float] = None

    @property
    def path(self) -> str:
        return self._path

    def load(self) -> Config:
        with self._lock:
            mtime = self._current_mtime()
            if self._cache is None or (mtime is not None and mtime != self._mtime):
                self._cache = self._read()
                self._mtime = mtime
            return self._cache

    def _current_mtime(self) -> Optional[float]:
        try:
            return os.path.getmtime(self._path)
        except OSError:
            return None

    def save(self, config: Config) -> Config:
        with self._lock:
            self._write(config)
            self._cache = replace(config)
            self._mtime = self._current_mtime()
            return self._cache

    def update(self, **changes: Any) -> Config:
        with self._lock:
            config = replace(self.load())
            for key, value in changes.items():
                if not hasattr(config, key):
                    raise ConfigError(f"unknown setting: {key}")
                setattr(config, key, value)
            config.validate()
            return self.save(config)

    def _read(self) -> Config:
        for candidate in (self._path, self._path + ".bak"):
            if not os.path.exists(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                if not isinstance(data, dict):
                    raise ValueError("config root must be an object")
                return Config.from_dict(data)
            except (OSError, ValueError, TypeError):
                continue
        return Config().validate()

    def _write(self, config: Config) -> None:
        directory = os.path.dirname(os.path.abspath(self._path)) or "."
        os.makedirs(directory, exist_ok=True)
        payload = json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n"
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=directory, prefix=".config-", suffix=".tmp", delete=False
        )
        try:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        os.replace(handle.name, self._path)
        try:
            with open(self._path + ".bak", "w", encoding="utf-8") as backup:
                backup.write(payload)
        except OSError:
            pass
