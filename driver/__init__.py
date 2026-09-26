"""JY-001 DIY-2 Humidifier Driver for Raspberry Pi.

A Python driver for controlling the JY-001 DIY-2 / 108 kHz ultrasonic humidifier
module using Raspberry Pi GPIO.

Example:
    from driver import Humidifier

    with Humidifier() as humidifier:
        humidifier.set_level(1)  # High mist
        humidifier.set_level(2)  # Medium mist
        humidifier.set_level(3)  # Low mist
        humidifier.turn_off()    # OFF
"""

from .humidifier import Humidifier, create_humidifier
from .config import (
    CONTROL_PIN,
    STATUS_PIN,
    PULSE_DURATION,
    MIST_LEVEL_HIGH,
    MIST_LEVEL_MEDIUM,
    MIST_LEVEL_LOW,
    MIST_LEVEL_OFF,
    VALID_LEVELS,
    STATUS_PIN_ACTIVE_HIGH,
    STATUS_DETECTION_TIMEOUT,
    STARTUP_PULSES_TO_OFF,
)
from .exceptions import (
    HumidifierError,
    GPIOError,
    InvalidLevelError,
    StateSyncError,
    OffDetectionTimeoutError,
    OperationInProgressError,
    HardwareError,
)

__version__ = "1.0.0"
__all__ = [
    "Humidifier",
    "create_humidifier",
    "CONTROL_PIN",
    "STATUS_PIN",
    "PULSE_DURATION",
    "MIST_LEVEL_HIGH",
    "MIST_LEVEL_MEDIUM",
    "MIST_LEVEL_LOW",
    "MIST_LEVEL_OFF",
    "VALID_LEVELS",
    "STATUS_PIN_ACTIVE_HIGH",
    "STATUS_DETECTION_TIMEOUT",
    "STARTUP_PULSES_TO_OFF",
    "HumidifierError",
    "GPIOError",
    "InvalidLevelError",
    "StateSyncError",
    "OffDetectionTimeoutError",
    "OperationInProgressError",
    "HardwareError",
]