"""Thread safe control of the physical humidifier.

The GPIO handling lives in ``driver/humidifier.py``.  It is loaded directly
from its file location so that the web service works no matter from which
directory it is started and so that the broken/legacy package initialiser in
``driver/__init__.py`` cannot interfere.

If the GPIO library is not available (for example while developing on a
laptop) the controller falls back to a simulation mode so the scheduling and
the web interface can still be exercised.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import threading
from types import ModuleType
from typing import Any, Dict, Optional

LOG = logging.getLogger("humidifier.controller")

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DRIVER_FILE = os.path.join(os.path.dirname(APP_DIR), "driver", "humidifier.py")

STAGE_LABELS: Dict[int, str] = {
    1: "1 - highest",
    2: "2 - medium",
    3: "3 - lowest",
}


class HumidifierError(RuntimeError):
    """Raised when the humidifier cannot be controlled."""


def _load_driver_module() -> ModuleType:
    if not os.path.exists(DRIVER_FILE):
        raise HumidifierError(f"GPIO driver not found: {DRIVER_FILE}")
    spec = importlib.util.spec_from_file_location("humidifier_gpio_driver", DRIVER_FILE)
    if spec is None or spec.loader is None:
        raise HumidifierError(f"Unable to load GPIO driver: {DRIVER_FILE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HumidifierController:
    """Owns the GPIO driver instance and serialises every access to it."""

    def __init__(self, simulate: Optional[bool] = None) -> None:
        self._lock = threading.RLock()
        self._driver: Optional[Any] = None
        self._stage: Optional[int] = None
        self._error: Optional[str] = None
        if simulate is None:
            simulate = os.environ.get("HUMIDIFIER_SIMULATE", "0") == "1"
        self._simulate = bool(simulate)

    @property
    def simulated(self) -> bool:
        return self._simulate

    def initialize(self) -> None:
        with self._lock:
            if self._driver is not None:
                return
            if self._simulate:
                LOG.warning("Humidifier running in simulation mode (no GPIO access)")
                return
            try:
                module = _load_driver_module()
                driver = module.HumidifierDriver(force_cleanup=True)
                driver.initialize()
            except Exception as exc:
                self._error = str(exc)
                LOG.error("Unable to initialise the GPIO driver: %s", exc)
                raise HumidifierError(str(exc)) from exc
            self._driver = driver
            self._error = None
            self._stage = None
            LOG.info("GPIO driver initialised (enable pin %s)", module.HumidifierDriver.ENABLE_PIN)

    def turn_on(self, stage: int = 1) -> None:
        with self._lock:
            self.initialize()
            if self._simulate:
                self._stage = stage
                LOG.info("SIMULATION: humidifier switched ON (stage %s)", stage)
                return
            try:
                assert self._driver is not None
                self._driver.set_stage_auto(stage)
            except Exception as exc:
                self._error = str(exc)
                LOG.error("Failed to switch the humidifier ON: %s", exc)
                raise HumidifierError(str(exc)) from exc
            self._stage = stage
            self._error = None
            LOG.info("Humidifier switched ON (stage %s - %s)", stage, STAGE_LABELS.get(stage, "?"))

    def turn_off(self) -> None:
        with self._lock:
            if self._simulate:
                if self._stage is not None:
                    LOG.info("SIMULATION: humidifier switched OFF")
                self._stage = None
                return
            if self._driver is None:
                return
            try:
                self._driver.set_off()
            except Exception as exc:
                self._error = str(exc)
                LOG.error("Failed to switch the humidifier OFF: %s", exc)
                raise HumidifierError(str(exc)) from exc
            self._stage = None
            self._error = None
            LOG.info("Humidifier switched OFF")

    def is_on(self) -> bool:
        with self._lock:
            if self._simulate:
                return self._stage is not None
            if self._driver is None:
                return False
            try:
                return not self._driver.is_off()
            except Exception as exc:
                self._error = str(exc)
                LOG.warning("Unable to read the humidifier status pin: %s", exc)
                return False

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "on": self.is_on(),
                "stage": self._stage,
                "stage_label": STAGE_LABELS.get(self._stage or 0, ""),
                "simulated": self._simulate,
                "connected": self._driver is not None or self._simulate,
                "error": self._error,
            }

    def cleanup(self) -> None:
        with self._lock:
            if self._driver is not None:
                try:
                    self._driver.cleanup()
                except Exception:
                    pass
                self._driver = None
