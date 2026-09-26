"""JY-001 DIY-2 Humidifier Driver for Raspberry Pi.

Controls ultrasonic humidifier module via GPIO17 (bidirectional) and GPIO27 (status input).
"""

import time
import threading
from typing import Optional

try:
    from gpiozero import DigitalOutputDevice, DigitalInputDevice
    from gpiozero.pins.pigpio import PiGPIOFactory
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False

try:
    import RPi.GPIO as GPIO
    RPi_GPIO_AVAILABLE = True
except ImportError:
    RPi_GPIO_AVAILABLE = False

from .config import (
    CONTROL_PIN,
    STATUS_PIN,
    PULSE_DURATION,
    PULSE_INTERVAL,
    MIST_LEVEL_HIGH,
    MIST_LEVEL_MEDIUM,
    MIST_LEVEL_LOW,
    MIST_LEVEL_OFF,
    VALID_LEVELS,
    STATUS_PIN_ACTIVE_HIGH,
    STATUS_DETECTION_TIMEOUT,
    STARTUP_PULSES_TO_OFF,
    MAX_SYNC_RETRIES,
)
from .exceptions import (
    GPIOError,
    InvalidLevelError,
    StateSyncError,
    OffDetectionTimeoutError,
    OperationInProgressError,
    HardwareError,
)


class Humidifier:
    """Driver for JY-001 DIY-2 ultrasonic humidifier module.

    Uses GPIO17 for control pulses (LOW output / HIGH-Z release) and
    GPIO27 for OFF-state detection.
    """

    def __init__(
        self,
        control_pin: int = CONTROL_PIN,
        status_pin: int = STATUS_PIN,
        pulse_duration: float = PULSE_DURATION,
        pulse_interval: float = PULSE_INTERVAL,
        status_active_high: bool = STATUS_PIN_ACTIVE_HIGH,
        detection_timeout: float = STATUS_DETECTION_TIMEOUT,
        startup_pulses_to_off: int = STARTUP_PULSES_TO_OFF,
        use_pigpio: bool = False,
        pigpio_host: Optional[str] = None,
        skip_sync: bool = False,
    ) -> None:
        """Initialize the humidifier driver.

        Args:
            control_pin: GPIO pin for control pulses (default: 17)
            status_pin: GPIO pin for OFF-state detection (default: 27)
            pulse_duration: Duration to hold pin LOW (seconds)
            pulse_interval: Minimum delay between pulses (seconds)
            status_active_high: True if status pin reads HIGH when OFF
            detection_timeout: Max time to wait for OFF confirmation (seconds)
            startup_pulses_to_off: Pulses needed to reach OFF from power-on
            use_pigpio: Use pigpio daemon for better timing (requires pigpio running)
            pigpio_host: Hostname for pigpio daemon (default: localhost)
        """
        self._control_pin = control_pin
        self._status_pin = status_pin
        self._pulse_duration = pulse_duration
        self._pulse_interval = pulse_interval
        self._status_active_high = status_active_high
        self._detection_timeout = detection_timeout
        self._startup_pulses_to_off = startup_pulses_to_off
        self._skip_sync = skip_sync

        self._current_level: Optional[int] = None
        self._lock = threading.Lock()
        self._operation_in_progress = False
        self._gpio_initialized = False
        self._using_gpiozero = False
        self._using_rpi_gpio = False

        self._init_gpio(use_pigpio, pigpio_host)
        if not self._skip_sync:
            self._sync_state()

    def _init_gpio(self, use_pigpio: bool, pigpio_host: Optional[str]) -> None:
        """Initialize GPIO pins using gpiozero or RPi.GPIO.
        
        GPIO17 (control) starts in HIGH-Z (input) mode.
        GPIO27 (status) is always input.
        """
        if use_pigpio and GPIOZERO_AVAILABLE:
            try:
                factory = PiGPIOFactory(host=pigpio_host) if pigpio_host else PiGPIOFactory()
                # Start control pin in HIGH-Z (input) mode
                self._control = DigitalInputDevice(self._control_pin, pin_factory=factory)
                self._status = DigitalInputDevice(
                    self._status_pin,
                    pull_up=not self._status_active_high,
                    pin_factory=factory,
                )
                self._using_gpiozero = True
                self._gpio_initialized = True
                return
            except Exception as e:
                raise GPIOError(f"Failed to initialize gpiozero with pigpio: {e}")

        if GPIOZERO_AVAILABLE:
            try:
                # Start control pin in HIGH-Z (input) mode
                self._control = DigitalInputDevice(self._control_pin)
                self._status = DigitalInputDevice(
                    self._status_pin,
                    pull_up=not self._status_active_high,
                )
                self._using_gpiozero = True
                self._gpio_initialized = True
                return
            except Exception as e:
                raise GPIOError(f"Failed to initialize gpiozero: {e}")

        if RPi_GPIO_AVAILABLE:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                # GPIO17 starts as input (HIGH-Z)
                GPIO.setup(self._control_pin, GPIO.IN)
                # GPIO27 is input with appropriate pull
                GPIO.setup(self._status_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP if not self._status_active_high else GPIO.PUD_DOWN)
                self._using_rpi_gpio = True
                self._gpio_initialized = True
                return
            except Exception as e:
                raise GPIOError(f"Failed to initialize RPi.GPIO: {e}")

        raise GPIOError("No GPIO library available. Install gpiozero or RPi.GPIO")

    def _set_control_low(self) -> None:
        """Set control pin to LOW (switch from HIGH-Z to output LOW)."""
        if self._using_gpiozero:
            self._control.close()
            from gpiozero import DigitalOutputDevice
            self._control = DigitalOutputDevice(
                self._control_pin,
                active_high=True,
                initial_value=False,
            )
        elif self._using_rpi_gpio:
            GPIO.setup(self._control_pin, GPIO.OUT, initial=GPIO.LOW)
        else:
            raise GPIOError("GPIO not initialized")

    def _release_control_high_z(self) -> None:
        """Release control pin to HIGH-Z (input mode)."""
        if self._using_gpiozero:
            self._control.close()
            from gpiozero import DigitalInputDevice
            self._control = DigitalInputDevice(self._control_pin)
        elif self._using_rpi_gpio:
            GPIO.setup(self._control_pin, GPIO.IN)
        else:
            raise GPIOError("GPIO not initialized")

    

    def _read_status(self) -> bool:
        """Read status pin. Returns True if humidifier is OFF."""
        if self._using_gpiozero:
            value = self._status.value
        elif self._using_rpi_gpio:
            value = GPIO.input(self._status_pin)
        else:
            raise GPIOError("GPIO not initialized")

        return value == 1 if self._status_active_high else value == 0

    def _generate_pulse(self) -> None:
        """Generate a single control pulse: LOW for pulse_duration, then return to HIGH-Z."""
        self._set_control_low()
        time.sleep(self._pulse_duration)
        self._release_control_high_z()
        time.sleep(self._pulse_interval)
        # Keep in HIGH-Z after pulse (don't restore output)

    def _wait_for_off_state(self) -> bool:
        """Wait for OFF state detection on status pin.

        Returns:
            True if OFF state detected, False if timeout.
        """
        start_time = time.time()
        while time.time() - start_time < self._detection_timeout:
            if self._read_status():
                return True
            time.sleep(0.05)
        return False

    def _sync_state(self) -> None:
        """Synchronize driver state with hardware by pulsing to known OFF state."""
        for attempt in range(MAX_SYNC_RETRIES):
            try:
                for _ in range(self._startup_pulses_to_off):
                    self._generate_pulse()

                if self._wait_for_off_state():
                    self._current_level = MIST_LEVEL_OFF
                    return

                time.sleep(0.5)
            except Exception:
                if attempt == MAX_SYNC_RETRIES - 1:
                    raise
                time.sleep(0.5)

        raise StateSyncError("Failed to synchronize with humidifier after maximum retries")

    def _calculate_pulses_needed(self, target_level: int) -> int:
        """Calculate number of pulses needed to reach target level from current.

        Assumes level cycle: 1 -> 2 -> 3 -> 4(OFF) -> 1 -> ...
        """
        if self._current_level is None:
            return self._startup_pulses_to_off + (target_level - 1) % 4

        if self._current_level == target_level:
            return 0

        current = self._current_level
        pulses = 0
        while current != target_level:
            current = current + 1 if current < 4 else 1
            pulses += 1
        return pulses

    def set_level(self, level: int) -> None:
        """Set mist level (1=High, 2=Medium, 3=Low).

        Args:
            level: Mist level (1, 2, or 3)

        Raises:
            InvalidLevelError: If level is not 1, 2, or 3
            OperationInProgressError: If another operation is in progress
            StateSyncError: If state synchronization fails
        """
        if level not in (MIST_LEVEL_HIGH, MIST_LEVEL_MEDIUM, MIST_LEVEL_LOW):
            raise InvalidLevelError(f"Invalid mist level: {level}. Must be 1, 2, or 3")

        with self._lock:
            if self._operation_in_progress:
                raise OperationInProgressError("Control operation already in progress")

            self._operation_in_progress = True
            try:
                pulses_needed = self._calculate_pulses_needed(level)

                for _ in range(pulses_needed):
                    self._generate_pulse()

                self._current_level = level

            finally:
                self._operation_in_progress = False

    def turn_off(self) -> None:
        """Turn humidifier OFF (level 4).

        Raises:
            OperationInProgressError: If another operation is in progress
            OffDetectionTimeoutError: If OFF state not detected within timeout
        """
        with self._lock:
            if self._operation_in_progress:
                raise OperationInProgressError("Control operation already in progress")

            self._operation_in_progress = True
            try:
                if self._current_level == MIST_LEVEL_OFF:
                    if not self._read_status():
                        raise HardwareError("Driver thinks OFF but hardware reports ON")
                    return

                pulses_needed = self._calculate_pulses_needed(MIST_LEVEL_OFF)

                for _ in range(pulses_needed):
                    self._generate_pulse()

                if not self._wait_for_off_state():
                    raise OffDetectionTimeoutError(
                        f"OFF state not detected within {self._detection_timeout}s"
                    )

                self._current_level = MIST_LEVEL_OFF

            finally:
                self._operation_in_progress = False

    def get_level(self) -> Optional[int]:
        """Get current mist level.

        Returns:
            Current level (1, 2, 3, 4) or None if unknown
        """
        return self._current_level

    def is_off(self) -> bool:
        """Check if humidifier is OFF by reading status pin.

        Returns:
            True if humidifier is OFF, False otherwise
        """
        return self._read_status()

    def close(self) -> None:
        """Clean up GPIO resources - set both pins to HIGH-Z (input)."""
        with self._lock:
            if self._using_gpiozero:
                try:
                    # Ensure control pin is in HIGH-Z before closing
                    self._control.close()
                    from gpiozero import DigitalInputDevice
                    self._control = DigitalInputDevice(self._control_pin)
                    self._control.close()
                    self._status.close()
                except Exception:
                    pass
            elif self._using_rpi_gpio:
                try:
                    # Set both pins to input (HIGH-Z) before cleanup
                    GPIO.setup(self._control_pin, GPIO.IN)
                    GPIO.setup(self._status_pin, GPIO.IN)
                    GPIO.cleanup([self._control_pin, self._status_pin])
                except Exception:
                    pass
            self._gpio_initialized = False
            self._current_level = None

    def __enter__(self) -> "Humidifier":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def create_humidifier(**kwargs) -> Humidifier:
    """Factory function to create a Humidifier instance.

    Args:
        **kwargs: Arguments passed to Humidifier.__init__

    Returns:
        Configured Humidifier instance
    """
    return Humidifier(**kwargs)